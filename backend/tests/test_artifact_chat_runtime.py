"""Tests für den Vision-Pfad des Dialog-Turn-Completers."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from app.db.session import SessionLocal
from app.services import artifact_chat_runtime as rt
from app.services import artifact_files as files_svc


def test_safe_name_valid_python_identifier_and_ascii():
    # AutoGen verlangt einen gültigen Python-Identifier (kein "-", keine führende
    # Ziffer) UND ASCII (Anthropic). Umlaute + Bindestriche → "_".
    out = rt._safe_name("Tägliches Themen-Briefing")
    assert out == "T_gliches_Themen_Briefing"
    assert out.isascii()
    assert out.isidentifier()


def test_safe_name_leading_digit_prefixed():
    out = rt._safe_name("2025 Report")
    assert out.isidentifier()
    assert out == "a_2025_Report"


def test_safe_name_empty_falls_back():
    assert rt._safe_name("") == "agent"
    assert rt._safe_name("äöü") == "___"


async def _seed_owner_and_artifact(db, client):
    from sqlalchemy import select

    from app.db.models import User
    from app.services import artifacts as art_svc

    owner = (await db.execute(select(User))).scalars().first()
    resp = await client.post("/agents", json={"name": "Vision-Agent"})
    assert resp.status_code == 201, resp.text
    agent_id = UUID(resp.json()["id"])
    art = await art_svc.create_instance(
        db, owner_id=owner.id, agent_id=agent_id, title="X", output_type="html"
    )
    return owner, art


def _png_bytes() -> bytes:
    from PIL import Image as PILImage
    import io

    buf = io.BytesIO()
    PILImage.new("RGB", (1, 1), (255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def test_build_user_message_text_only():
    msg = rt._build_user_message("hallo", [])
    assert type(msg).__name__ == "TextMessage"
    assert msg.content == "hallo"


def test_build_user_message_multimodal(tmp_path):
    p = tmp_path / "x.png"
    p.write_bytes(_png_bytes())
    msg = rt._build_user_message("schau dir das an", [str(p)])
    assert type(msg).__name__ == "MultiModalMessage"
    assert len(msg.content) == 2  # Text + 1 Bild


@pytest.mark.asyncio
async def test_make_completer_returns_complete_and_meta(client):
    await client.get("/artifacts")  # stellt sicher: User existiert
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        complete, meta = await rt.make_completer(db, art.id)
        assert callable(complete)
        assert meta.owner_id == owner.id
        assert isinstance(meta.model, str) and meta.model
        assert meta.tokens_in == 0 and meta.tokens_out == 0


@pytest.mark.asyncio
async def test_latest_turn_image_paths_returns_only_images(client, tmp_path, monkeypatch):
    import io as _io

    from starlette.datastructures import Headers, UploadFile

    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        img = UploadFile(
            file=_io.BytesIO(_png_bytes()), filename="foto.png",
            headers=Headers({"content-type": "image/png"}),
        )
        doc = UploadFile(
            file=_io.BytesIO(b"text"), filename="brief.txt",
            headers=Headers({"content-type": "text/plain"}),
        )
        saved = await files_svc.save_files(db, art.id, owner.id, [img, doc])
        from app.db.models import ArtifactMessage

        db.add(
            ArtifactMessage(
                artifact_id=art.id, role="user", content="x",
                file_ids=[str(s.id) for s in saved],
            )
        )
        await db.commit()
        paths = await rt._latest_turn_image_paths(db, art.id)
        assert len(paths) == 1
        assert Path(paths[0]).name.endswith(".png")


@pytest.mark.asyncio
async def test_mcp_tools_loaded_for_template_allowlist(client, tmp_path, monkeypatch):
    import contextlib
    from contextlib import AsyncExitStack

    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")

    captured = {}

    @contextlib.asynccontextmanager
    async def fake_session(url, transport="sse", headers=None, timeout=15.0):
        captured["url"] = url
        yield ["MCP_TOOL"]

    monkeypatch.setattr(rt, "load_mcp_tools_session", fake_session)

    async with SessionLocal() as db:
        from sqlalchemy import select
        from app.db.models import User, Template
        from app.schemas.templates import AgentTemplateCreate
        from app.services import mcp_catalog
        from app.services.templates import create_agent_template, instantiate

        owner = (await db.execute(select(User))).scalars().first()
        if not await mcp_catalog.get(db, "demo-everything"):
            await mcp_catalog.create(db, server_id="demo-everything", name="Demo", description="",
                transport="streamable_http", url="http://mcp-demo:8080/mcp",
                requires_credential=False, updated_by="t")
        tpl = await create_agent_template(
            db, owner,
            AgentTemplateCreate(category="Everyday", 
                name="MCP-Wire-Test", prompt="Nutze das Demo-MCP.",
                model="claude-haiku-4-5", html_template_id="classic",
                mcp_servers=["demo-everything"],
            ),
        )
        inst = await instantiate(db, tpl.id, owner, {"label": "wire"})
        async with AsyncExitStack() as stack:
            tools = await rt._mcp_tools_for_artifact(db, inst.artifact_id, stack)
        assert "MCP_TOOL" in tools
        assert captured["url"] == "http://mcp-demo:8080/mcp"


async def _seed_mcp_instance(db, client, *, server_id, requires_credential):
    """Legt (falls nötig) einen Katalog-Server an und instanziiert ein Template,
    das genau diesen Server per Allowlist erlaubt. Liefert (owner, artifact)."""
    from sqlalchemy import select

    from app.db.models import Artifact, User
    from app.schemas.templates import AgentTemplateCreate
    from app.services import mcp_catalog
    from app.services.templates import create_agent_template, instantiate

    owner = (await db.execute(select(User))).scalars().first()
    if not await mcp_catalog.get(db, server_id):
        await mcp_catalog.create(
            db, server_id=server_id, name="Seed", description="",
            transport="streamable_http", url="http://mcp-seed:8080/mcp",
            requires_credential=requires_credential,
            auth_header="Authorization", auth_value_template="Bearer {secret}",
            secret_label="T", updated_by="t",
        )
    tpl = await create_agent_template(
        db, owner,
        AgentTemplateCreate(category="Everyday", 
            name=f"Cred-Wire-{server_id}", prompt="Nutze das MCP.",
            model="claude-haiku-4-5", html_template_id="classic",
            mcp_servers=[server_id],
        ),
    )
    inst = await instantiate(db, tpl.id, owner, {"label": "wire"})
    art = await db.get(Artifact, inst.artifact_id)
    return owner, art


@pytest.mark.asyncio
async def test_mcp_credentialed_server_passes_auth_header(client, tmp_path, monkeypatch):
    import contextlib
    from contextlib import AsyncExitStack

    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")

    captured = {}

    @contextlib.asynccontextmanager
    async def fake_loader(url, transport, headers=None, timeout=15.0):
        captured["headers"] = headers
        yield ["MCP_TOOL"]

    monkeypatch.setattr(rt, "load_mcp_tools_session", fake_loader)

    async with SessionLocal() as db:
        from app.services import artifact_connections

        owner, art = await _seed_mcp_instance(
            db, client, server_id="cred-notion", requires_credential=True
        )
        await artifact_connections.upsert_connection(
            db, art.id, art.owner_id, kind="mcp:cred-notion", config={}, secret="tok-123"
        )
        async with AsyncExitStack() as stack:
            tools = await rt._mcp_tools_for_artifact(db, art.id, stack)
        assert "MCP_TOOL" in tools
        assert captured["headers"] == {"Authorization": "Bearer tok-123"}


@pytest.mark.asyncio
async def test_mcp_credentialed_server_without_connection_skipped(client, tmp_path, monkeypatch):
    import contextlib
    from contextlib import AsyncExitStack

    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")

    called = {"n": 0}

    @contextlib.asynccontextmanager
    async def fake_loader(url, transport, headers=None, timeout=15.0):
        called["n"] += 1
        yield ["MCP_TOOL"]

    monkeypatch.setattr(rt, "load_mcp_tools_session", fake_loader)

    async with SessionLocal() as db:
        owner, art = await _seed_mcp_instance(
            db, client, server_id="notion-nocon", requires_credential=True
        )
        async with AsyncExitStack() as stack:
            tools = await rt._mcp_tools_for_artifact(db, art.id, stack)
        assert tools == []
        assert called["n"] == 0


@pytest.mark.asyncio
async def test_mcp_credentialed_server_corrupt_token_skipped(client, tmp_path, monkeypatch):
    import contextlib
    from contextlib import AsyncExitStack

    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")

    called = {"n": 0}

    @contextlib.asynccontextmanager
    async def fake_loader(url, transport, headers=None, timeout=15.0):
        called["n"] += 1
        yield ["MCP_TOOL"]

    monkeypatch.setattr(rt, "load_mcp_tools_session", fake_loader)

    async with SessionLocal() as db:
        from app.services import artifact_connections

        owner, art = await _seed_mcp_instance(
            db, client, server_id="cred-corrupt", requires_credential=True
        )
        await artifact_connections.upsert_connection(
            db, art.id, art.owner_id, kind="mcp:cred-corrupt", config={}, secret="tok-123"
        )
        conn = await artifact_connections.get_connection(
            db, art.id, art.owner_id, "mcp:cred-corrupt"
        )
        conn.secret_encrypted = "not-a-valid-fernet-token"  # decrypt() schlägt fehl
        await db.commit()

        async with AsyncExitStack() as stack:
            tools = await rt._mcp_tools_for_artifact(db, art.id, stack)
        assert tools == []  # defekter Token → Server übersprungen
        assert called["n"] == 0  # Turn nicht abgebrochen, Loader nie aufgerufen


@pytest.mark.asyncio
async def test_mcp_credential_free_server_passes_no_header(client, tmp_path, monkeypatch):
    import contextlib
    from contextlib import AsyncExitStack

    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")

    captured = {"headers": "unset"}

    @contextlib.asynccontextmanager
    async def fake_loader(url, transport, headers=None, timeout=15.0):
        captured["headers"] = headers
        yield ["MCP_TOOL"]

    monkeypatch.setattr(rt, "load_mcp_tools_session", fake_loader)

    async with SessionLocal() as db:
        owner, art = await _seed_mcp_instance(
            db, client, server_id="free-srv", requires_credential=False
        )
        async with AsyncExitStack() as stack:
            tools = await rt._mcp_tools_for_artifact(db, art.id, stack)
        assert "MCP_TOOL" in tools
        assert captured["headers"] is None


@pytest.mark.asyncio
async def test_publish_tool_attached_only_for_publish_templates(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        from sqlalchemy import select
        from app.db.models import User
        from app.schemas.templates import AgentTemplateCreate
        from app.services.templates import create_agent_template, instantiate

        owner = (await db.execute(select(User))).scalars().first()
        tpl = await create_agent_template(
            db, owner,
            AgentTemplateCreate(category="Everyday", 
                name="Pub-Tool-Test", prompt="Baue eine Seite.",
                model="claude-haiku-4-5", html_template_id="classic",
                publish_targets=["sftp"],
            ),
        )
        inst = await instantiate(db, tpl.id, owner, {"label": "pt"})
        tools = await rt._publish_tools_for_artifact(db, inst.artifact_id)
        names = [getattr(t, "__name__", "") for t in tools]
        assert "publish_site" in names


@pytest.mark.asyncio
async def test_publish_tool_absent_without_flag(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        from sqlalchemy import select
        from app.db.models import User
        from app.schemas.templates import AgentTemplateCreate
        from app.services.templates import create_agent_template, instantiate

        owner = (await db.execute(select(User))).scalars().first()
        tpl = await create_agent_template(
            db, owner,
            AgentTemplateCreate(category="Everyday", 
                name="No-Pub", prompt="x", model="claude-haiku-4-5",
                html_template_id="classic",
            ),
        )
        inst = await instantiate(db, tpl.id, owner, {"label": "np"})
        assert await rt._publish_tools_for_artifact(db, inst.artifact_id) == []


@pytest.mark.asyncio
async def test_slot_tools_attached_in_slots_mode(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        from sqlalchemy import select
        from app.db.models import Artifact, User
        from app.schemas.templates import AgentTemplateCreate
        from app.services.templates import create_agent_template, instantiate

        owner = (await db.execute(select(User))).scalars().first()

        tpl_slots = await create_agent_template(
            db, owner,
            AgentTemplateCreate(category="Everyday", 
                name="Slots-Mode-Test", prompt="Pflege die Seite in Slots.",
                model="claude-haiku-4-5", html_template_id="classic",
                content_mode="slots",
            ),
        )
        inst_slots = await instantiate(db, tpl_slots.id, owner, {"label": "sm"})

        tpl_html = await create_agent_template(
            db, owner,
            AgentTemplateCreate(category="Everyday", 
                name="Html-Mode-Test", prompt="Baue eine HTML-Seite.",
                model="claude-haiku-4-5", html_template_id="classic",
            ),
        )
        inst_html = await instantiate(db, tpl_html.id, owner, {"label": "hm"})

        # Altlast-Pfad: ohne output_template entscheidet das Template-config content_mode.
        art_slots0 = await db.get(Artifact, inst_slots.artifact_id)
        art_html0 = await db.get(Artifact, inst_html.artifact_id)
        art_slots0.output_template = ""
        art_html0.output_template = ""
        await db.commit()

        assert await rt._content_mode_for(db, inst_slots.artifact_id) == "slots"
        assert await rt._content_mode_for(db, inst_html.artifact_id) == "html"

        art_slots = await db.get(Artifact, inst_slots.artifact_id)
        from app.services.agent_tools import slot_tools

        names = [
            getattr(t, "__name__", "")
            for t in slot_tools(artifact_id=art_slots.id, owner_id=art_slots.owner_id)
        ]
        assert "update_slot" in names


async def _seed_output_template_instance(db, client, *, name, output_template):
    """Instanz mit gesetztem output_template (legacy template ohne content_mode)."""
    from sqlalchemy import select

    from app.db.models import Artifact, User
    from app.schemas.templates import AgentTemplateCreate
    from app.services.templates import create_agent_template, instantiate

    owner = (await db.execute(select(User))).scalars().first()
    tpl = await create_agent_template(
        db, owner,
        AgentTemplateCreate(category="Everyday", name=name, prompt="x",
                            model="claude-haiku-4-5", html_template_id="classic"),
    )
    inst = await instantiate(db, tpl.id, owner, {"label": "ot"})
    art = await db.get(Artifact, inst.artifact_id)
    art.output_template = output_template
    await db.commit()
    return owner, art


@pytest.mark.asyncio
async def test_output_mode_prepared_returns_slots_with_placeholders(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_output_template_instance(
            db, client, name="OT-Prepared", output_template="prepared:journal"
        )
        mode, placeholders = await rt._output_mode_for(db, art.id)
        assert mode == "slots"
        keys = {p["key"] for p in placeholders}
        assert "title" in keys and "intro" in keys

        from app.services.artifact_chat import prepared_slot_note

        note = prepared_slot_note(placeholders)
        assert "title" in note and "intro" in note and "update_slot" in note

        from app.services.agent_tools import slot_tools

        names = [getattr(t, "__name__", "")
                 for t in slot_tools(artifact_id=art.id, owner_id=art.owner_id)]
        assert "update_slot" in names


@pytest.mark.asyncio
async def test_output_mode_agent_is_html_no_slots(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_output_template_instance(
            db, client, name="OT-Agent", output_template="agent"
        )
        mode, placeholders = await rt._output_mode_for(db, art.id)
        assert mode == "html"
        assert placeholders == []

        from app.services.artifact_chat import CANVAS_CONTRACT, build_turn_system_prompt

        prompt = build_turn_system_prompt("p", None, content_mode=mode)
        assert CANVAS_CONTRACT in prompt


@pytest.mark.asyncio
async def test_output_mode_slots_design_is_free_slots(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_output_template_instance(
            db, client, name="OT-Slots", output_template="slots:magazine"
        )
        mode, placeholders = await rt._output_mode_for(db, art.id)
        assert mode == "slots"
        assert placeholders == []  # freie Slots, keine festen Keys

        from app.services.artifact_chat import build_turn_system_prompt

        prompt = build_turn_system_prompt("p", None, content_mode=mode)
        assert "feste Abschnitte" not in prompt


@pytest.mark.asyncio
async def test_wordpress_tool_attached_for_wp_template(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        from sqlalchemy import select
        from app.db.models import User
        from app.schemas.templates import AgentTemplateCreate
        from app.services.templates import create_agent_template, instantiate
        owner = (await db.execute(select(User))).scalars().first()
        tpl = await create_agent_template(db, owner,
            AgentTemplateCreate(category="Everyday", name="WP-Tool", prompt="x", model="claude-haiku-4-5",
                                html_template_id="classic", publish_targets=["wordpress"]))
        inst = await instantiate(db, tpl.id, owner, {"label": "wp"})
        names = [getattr(t, "__name__", "") for t in await rt._publish_tools_for_artifact(db, inst.artifact_id)]
        assert "wordpress_publish" in names
