from __future__ import annotations

import random
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.models import (
    Agent,
    AgentVersion,
    Artifact,
    RunMode,
    Template,
    TemplateOutput,
    TemplateRun,
    User,
    Visibility,
    Work,
)
from app.schemas.templates import (
    AgentTemplateCreate,
    AgentTemplateUpdate,
    InstantiateResponse,
    PublicTemplateOut,
    TemplateConfig,
    TemplateCreate,
    TemplateOut,
    TemplateUpdate,
)
from app.schemas.works import WorkCreate
from app.services import html_templates
from app.services import roles
from app.services import template_summary
from app.services import runs as run_svc
from app.services import works as work_svc

# Feste Kategorie-Liste (UI + API); jede Agent-Vorlage muss genau eine davon wählen.
TEMPLATE_CATEGORIES = (
    "Everyday", "Planner", "Software", "Tech", "Timer",
    "Work", "Finance", "Education", "Travel", "Health",
    "Marketing", "Legal", "Creative", "Data", "Communication",
    "Entertainment", "Household", "Knowledge", "Sports", "Other",
)


def _effective_visibility(user, requested):
    return roles.effective_visibility(user, requested)


async def create_template(db: AsyncSession, user: User, payload: TemplateCreate) -> TemplateOut:
    tpl = Template(
        owner_id=user.id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        visibility=_effective_visibility(user, payload.visibility),
        input_schema=[f.model_dump() for f in payload.input_schema],
        output_type=payload.output_type,
        mode=payload.mode,
        config=payload.config.model_dump(mode="json"),
        max_iterations=payload.max_iterations,
        max_cost_usd=payload.max_cost_usd,
        success_criteria=payload.success_criteria,
        image_url=payload.image_url,
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return TemplateOut.model_validate(tpl)


# Icon-Auswahl (Emoji) für Agent-Vorlagen ohne eigenes Bild. Im image_url als
# "emoji:<zeichen>" gespeichert; das Frontend rendert es groß. AI-Bild kommt später.
ICON_CHOICES = [
    "🧑‍💻", "👨‍💼", "👩‍💼", "🧑‍🔬", "👨‍🔬", "👩‍🔬", "🧑‍🏫", "👨‍🏫", "👩‍🏫", "🧑‍⚕️",
    "👨‍⚕️", "👩‍⚕️", "🧑‍🍳", "👨‍🍳", "👩‍🍳", "🧑‍🔧", "👷", "🕵️", "🧑‍✈️", "🧑‍🎨",
    "🧑‍⚖️", "🧑‍🌾", "🧑‍🏭", "🤓",
]


def random_icon() -> str:
    return "emoji:" + random.choice(ICON_CHOICES)


def _validate_commands(commands) -> None:
    """Template-eigene „/"-Funktionen prüfen: gültiger Modus, kein System-Key, eindeutig.

    `commands` ist eine Liste von TemplateCommand (Pydantic). Key-Slug + Längen werden
    bereits vom Schema erzwungen; hier kommen die fachlichen Regeln dazu."""
    from app.services import output_commands

    seen: set[str] = set()
    for c in commands:
        if not output_commands.is_mode(c.mode):
            raise ValueError(f"Unbekannter Ausgabe-Modus: {c.mode}")
        if output_commands.is_system_key(c.key):
            raise ValueError(f"Reservierter System-Befehl: /{c.key}")
        if c.key in seen:
            raise ValueError(f"Doppelter Befehl: /{c.key}")
        seen.add(c.key)


def _provider_for(model: str) -> str:
    """Provider grob aus dem Modellnamen ableiten (Nutzer wählt nur das Modell)."""
    m = (model or "").lower()
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    return "ollama"


async def create_agent_template(
    db: AsyncSession, user: User, payload: AgentTemplateCreate
) -> TemplateOut:
    """Einheitliche „Agent-Vorlage": legt Agent (+Version) und umhüllendes Template
    atomar an. Der Prompt ist zugleich System-Prompt des Agenten und prompt_template
    des Templates."""
    if not html_templates.is_valid(payload.html_template_id):
        raise ValueError(
            "Bitte eine HTML-Vorlage wählen."
            if not payload.html_template_id
            else "Unbekannte HTML-Vorlage."
        )
    if payload.category not in TEMPLATE_CATEGORIES:
        raise ValueError(f"Unbekannte Kategorie: {payload.category}")
    from app.services import mcp_catalog

    for sid in payload.mcp_servers:
        if not await mcp_catalog.is_valid(db, sid):
            raise ValueError(f"Unbekannter MCP-Server: {sid}")
    from app.services import connection_registry

    for tgt in payload.publish_targets:
        if not connection_registry.is_valid(tgt):
            raise ValueError(f"Unbekanntes Veröffentlichungs-Ziel: {tgt}")
    if payload.content_mode not in ("html", "slots"):
        raise ValueError(f"Unbekannter content_mode: {payload.content_mode}")
    from app.services import output_commands
    if payload.default_output_mode and not output_commands.is_mode(payload.default_output_mode):
        raise ValueError(f"Unbekannter Ausgabe-Modus: {payload.default_output_mode}")
    _validate_commands(payload.commands)
    agent = Agent(
        owner_id=user.id,
        name=payload.name,
        description=payload.description,
        role="",
        domain="",
        visibility=_effective_visibility(user, payload.visibility),
        price_per_run=payload.price,
    )
    db.add(agent)
    await db.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version=1,
        system_prompt=payload.prompt,
        model=payload.model,
        provider=_provider_for(payload.model),
    )
    db.add(version)
    await db.flush()
    agent.current_version_id = version.id

    config = TemplateConfig(
        agent_ids=[agent.id],
        prompt_template=payload.prompt,
        html_template_id=payload.html_template_id,
        mcp_servers=payload.mcp_servers,
        publish_targets=payload.publish_targets,
        content_mode=payload.content_mode,
        default_output_mode=payload.default_output_mode,
        commands=payload.commands,
    )
    try:
        gen_desc = await template_summary.summarize_prompt(payload.prompt)
    except Exception:
        gen_desc = ""
    tpl = Template(
        owner_id=user.id,
        title=payload.name,
        description=gen_desc,
        category=payload.category,
        visibility=_effective_visibility(user, payload.visibility),
        input_schema=[],
        output_type=TemplateOutput.HTML,
        mode=RunMode.SINGLE,
        config=config.model_dump(mode="json"),
        max_iterations=3,  # schlank: schnellere Erst-Generierung (v.a. lokales qwen)
        max_cost_usd=payload.price,
        image_url=payload.image_url or random_icon(),
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return TemplateOut.model_validate(tpl)


async def update_agent_template(
    db: AsyncSession, template_id: UUID, user: User, payload: AgentTemplateUpdate
) -> TemplateOut | None:
    """Bearbeitet eine Agent-Vorlage: Template-Felder + primärer Agent (Prompt/Modell/Preis)."""
    tpl = await db.get(Template, template_id)
    if tpl is None or tpl.owner_id != user.id:
        return None
    if payload.name is not None:
        tpl.title = payload.name
    if payload.category is not None:
        if payload.category not in TEMPLATE_CATEGORIES:
            raise ValueError(f"Unbekannte Kategorie: {payload.category}")
        tpl.category = payload.category
    if payload.visibility is not None:
        tpl.visibility = _effective_visibility(user, payload.visibility)
    if payload.image_url is not None:
        tpl.image_url = payload.image_url or None
    if payload.price is not None:
        tpl.max_cost_usd = payload.price
    if payload.prompt is not None:
        cfg = dict(tpl.config or {})
        cfg["prompt_template"] = payload.prompt
        tpl.config = cfg
        try:
            gen = await template_summary.summarize_prompt(payload.prompt)
        except Exception:
            gen = ""
        if gen:
            tpl.description = gen
    if payload.html_template_id is not None:
        if not html_templates.is_valid(payload.html_template_id):
            raise ValueError(
                "Bitte eine HTML-Vorlage wählen."
                if not payload.html_template_id
                else "Unbekannte HTML-Vorlage."
            )
        cfg = dict(tpl.config or {})
        cfg["html_template_id"] = payload.html_template_id
        tpl.config = cfg
    if payload.mcp_servers is not None:
        from app.services import mcp_catalog

        for sid in payload.mcp_servers:
            if not await mcp_catalog.is_valid(db, sid):
                raise ValueError(f"Unbekannter MCP-Server: {sid}")
        cfg = dict(tpl.config or {})
        cfg["mcp_servers"] = payload.mcp_servers
        tpl.config = cfg
    if payload.content_mode is not None:
        if payload.content_mode not in ("html", "slots"):
            raise ValueError(f"Unbekannter content_mode: {payload.content_mode}")
        cfg = dict(tpl.config or {})
        cfg["content_mode"] = payload.content_mode
        tpl.config = cfg
    if payload.default_output_mode is not None:
        from app.services import output_commands
        if payload.default_output_mode and not output_commands.is_mode(payload.default_output_mode):
            raise ValueError(f"Unbekannter Ausgabe-Modus: {payload.default_output_mode}")
        cfg = dict(tpl.config or {})
        cfg["default_output_mode"] = payload.default_output_mode
        tpl.config = cfg
    if payload.commands is not None:
        _validate_commands(payload.commands)
        cfg = dict(tpl.config or {})
        cfg["commands"] = [c.model_dump() for c in payload.commands]
        tpl.config = cfg

    ids = (tpl.config or {}).get("agent_ids") or []
    if ids:
        aid = ids[0] if isinstance(ids[0], UUID) else UUID(str(ids[0]))
        agent = await db.get(Agent, aid)
        if agent and agent.owner_id == user.id:
            if payload.price is not None:
                agent.price_per_run = payload.price
            if agent.current_version_id:
                av = await db.get(AgentVersion, agent.current_version_id)
                if av:
                    if payload.prompt is not None:
                        av.system_prompt = payload.prompt
                    if payload.model is not None:
                        av.model = payload.model
                        av.provider = _provider_for(payload.model)
    await db.commit()
    await db.refresh(tpl)
    return TemplateOut.model_validate(tpl)


async def _primary_agent_model(db: AsyncSession, tpl: Template) -> str | None:
    """Modell des primären Agenten (config.agent_ids[0]) auflösen; None wenn nicht da."""
    ids = (tpl.config or {}).get("agent_ids") or []
    if not ids:
        return None
    aid = ids[0] if isinstance(ids[0], UUID) else UUID(str(ids[0]))
    agent = await db.get(Agent, aid)
    if agent is None or agent.current_version_id is None:
        return None
    av = await db.get(AgentVersion, agent.current_version_id)
    return av.model if av else None


async def get_template(db: AsyncSession, template_id: UUID, user: User) -> TemplateOut | None:
    tpl = await db.get(Template, template_id)
    if tpl is None:
        return None
    if tpl.visibility in (Visibility.PRIVATE, Visibility.DRAFT) and tpl.owner_id != user.id:
        return None
    out = TemplateOut.model_validate(tpl)
    out.model = await _primary_agent_model(db, tpl)
    # Kennzahlen (Slice 3)
    ids = (tpl.config or {}).get("agent_ids") or []
    if ids:
        aid = ids[0]; aid = aid if isinstance(aid, UUID) else UUID(str(aid))
        from app.services import agents as agents_svc
        avg, cnt = (await agents_svc._ratings_map(db, [aid])).get(aid, (0.0, 0))
        out.avg_stars = avg; out.ratings_count = cnt
    out.works_count = int((await db.execute(
        select(func.count(Artifact.id)).where(Artifact.template_id == tpl.id))).scalar() or 0)
    return out


async def list_templates(
    db: AsyncSession,
    user: User,
    *,
    category: str | None = None,
    mine: bool = False,
    public_only: bool = False,
) -> list[TemplateOut]:
    stmt = select(Template)
    if mine:
        stmt = stmt.where(Template.owner_id == user.id)
    elif public_only:
        stmt = stmt.where(Template.visibility == Visibility.PUBLIC)
    else:
        stmt = stmt.where(
            or_(Template.visibility == Visibility.PUBLIC, Template.owner_id == user.id)
        )
    if category:
        stmt = stmt.where(Template.category == category)
    stmt = stmt.order_by(Template.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [TemplateOut.model_validate(t) for t in rows]


async def list_public_templates(
    db: AsyncSession, *, category: str | None = None, sort: str = "popular",
    q: str | None = None, owner_id: UUID | None = None,
) -> list[PublicTemplateOut]:
    """Tokenfrei: alle öffentlichen Templates, angereichert um Modell, Sterne, works und
    Ersteller. `owner_id` filtert auf die Vorlagen eines bestimmten Erstellers.

    `sort="popular"` (Default) sortiert nach (works_count, avg_stars) absteigend;
    sonst bleibt die `created_at desc`-Reihenfolge (newest)."""
    from app.services import agents as agents_svc

    stmt = select(Template).where(Template.visibility == Visibility.PUBLIC)
    if owner_id is not None:
        stmt = stmt.where(Template.owner_id == owner_id)
    if category:
        stmt = stmt.where(Template.category == category)
    stmt = stmt.order_by(Template.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()

    if q and q.strip():
        ql = q.strip().lower()
        rows = [
            t for t in rows
            if ql in (t.title or "").lower()
            or ql in (t.description or "").lower()
            or ql in ((t.config or {}).get("prompt_template") or "").lower()
        ]

    def _first_agent_id(tpl: Template) -> UUID | None:
        ids = (tpl.config or {}).get("agent_ids") or []
        if not ids:
            return None
        first = ids[0]
        return first if isinstance(first, UUID) else UUID(str(first))

    tids = [t.id for t in rows]

    # Modelle in einer Abfrage auflösen (kein N+1): Agent → aktuelle Version → model.
    wanted = {aid for t in rows if (aid := _first_agent_id(t)) is not None}
    models: dict[UUID, str] = {}
    if wanted:
        arows = (
            await db.execute(
                select(Agent.id, AgentVersion.model)
                .join(AgentVersion, Agent.current_version_id == AgentVersion.id)
                .where(Agent.id.in_(wanted))
            )
        ).all()
        models = {aid: model for aid, model in arows}

    # Sterne der primären Agenten in EINER Abfrage (kein N+1).
    ratings = await agents_svc._ratings_map(db, list(wanted))

    # Ersteller (Name + Avatar) in EINER Abfrage (kein N+1).
    creators: dict[UUID, tuple[str, str | None]] = {}
    owner_ids = {t.owner_id for t in rows}
    if owner_ids:
        creators = {
            uid: (name or "", avatar)
            for uid, name, avatar in (
                await db.execute(
                    select(User.id, User.name, User.avatar_url).where(User.id.in_(owner_ids))
                )
            ).all()
        }

    # works-Zähler in EINER gruppierten Abfrage (kein N+1).
    works: dict[UUID, int] = {}
    if tids:
        works = {
            tid: n
            for tid, n in (
                await db.execute(
                    select(Artifact.template_id, func.count(Artifact.id))
                    .where(Artifact.template_id.in_(tids))
                    .group_by(Artifact.template_id)
                )
            ).all()
        }

    out: list[PublicTemplateOut] = []
    for t in rows:
        aid = _first_agent_id(t)
        avg, cnt = ratings.get(aid, (0.0, 0)) if aid is not None else (0.0, 0)
        out.append(
            PublicTemplateOut(
                id=t.id,
                title=t.title,
                description=t.description,
                category=t.category,
                image_url=t.image_url,
                output_type=t.output_type,
                model=models.get(aid) if aid is not None else None,
                price=t.max_cost_usd,
                avg_stars=avg,
                ratings_count=cnt,
                works_count=works.get(t.id, 0),
                creator_id=t.owner_id,
                creator_name=creators.get(t.owner_id, ("", None))[0],
                creator_avatar=creators.get(t.owner_id, ("", None))[1],
            )
        )

    if sort == "popular":
        out.sort(key=lambda x: (x.works_count, x.avg_stars), reverse=True)
    return out


async def update_template(
    db: AsyncSession, template_id: UUID, user: User, payload: TemplateUpdate
) -> TemplateOut | None:
    tpl = await db.get(Template, template_id)
    if tpl is None or tpl.owner_id != user.id:
        return None
    data = payload.model_dump(exclude_unset=True)
    # JSONB-Felder explizit JSON-serialisieren: config.agent_ids ist list[UUID] →
    # der python-mode-Dump enthielte UUID-Objekte, die der JSONB-Encoder nicht kennt
    # (TypeError). mode="json" wandelt UUIDs in Strings (analog create_template).
    if data.get("config") is not None:
        data["config"] = payload.config.model_dump(mode="json")
    if data.get("input_schema") is not None:
        data["input_schema"] = [f.model_dump() for f in payload.input_schema]
    # Sichtbarkeits-Gating: normale User dürfen ein Template nicht auf public/unlisted
    # heben (sonst Privilege-Escalation über den generischen PATCH-Pfad).
    if "visibility" in data:
        data["visibility"] = _effective_visibility(user, data["visibility"])
    # Enum-/Skalarfelder bleiben als Python-Objekte (setattr auf Enum-Spalten erwartet
    # Enum-Member, keine rohen Strings) — daher NICHT den ganzen Dump auf mode="json".
    for key, value in data.items():
        setattr(tpl, key, value)
    await db.commit()
    await db.refresh(tpl)
    return TemplateOut.model_validate(tpl)


async def delete_template(db: AsyncSession, template_id: UUID, user: User) -> bool:
    tpl = await db.get(Template, template_id)
    if tpl is None or tpl.owner_id != user.id:
        return False
    await db.delete(tpl)
    await db.commit()
    return True


def render_prompt(template_str: str, inputs: dict) -> str:
    out = template_str
    for key, value in inputs.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out


def _instance_title(template_title: str, input_schema: list[dict], inputs: dict) -> str:
    """Sprechenden Instanz-Titel bauen (Phase 5d), z. B. "Reiseplaner - Istanbul".

    Konvention: das erste Pflichtfeld (sonst das erste Feld) speist den Titel-Zusatz.
    Ohne brauchbaren Wert bleibt es beim reinen Template-Titel.
    """
    # Explizite Bezeichnung (Agent-Vorlagen ohne Eingabe-Schema) ist der Instanz-Name selbst.
    label = inputs.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    fields = input_schema or []
    key_field = next((f for f in fields if f.get("required")), fields[0] if fields else None)
    if key_field:
        value = inputs.get(key_field.get("key"))
        if value not in (None, ""):
            return f"{template_title} - {value}"
    return template_title


async def instantiate(
    db: AsyncSession,
    template_id: UUID,
    user: User,
    inputs: dict,
    output_template: str = "",
) -> InstantiateResponse | None:
    tpl = await db.get(Template, template_id)
    if tpl is None:
        return None
    if tpl.visibility in (Visibility.PRIVATE, Visibility.DRAFT) and tpl.owner_id != user.id:
        return None

    # Effektive Ausgabevorlage: explizit gewaehlt, sonst zufaellige prepared-Vorlage.
    ot = output_template
    if not ot:
        import random

        from app.services import page_templates

        prepared = page_templates.list_all()
        ot = f"prepared:{random.choice(prepared)['name']}" if prepared else "agent"

    # Pflicht-Eingaben prüfen
    missing = [
        f["key"]
        for f in (tpl.input_schema or [])
        if f.get("required") and (inputs.get(f["key"]) in (None, ""))
    ]
    if missing:
        raise ValueError(f"missing required inputs: {', '.join(missing)}")

    cfg = tpl.config or {}
    goal = render_prompt(cfg.get("prompt_template", ""), inputs)

    work_payload = WorkCreate(
        title=tpl.title,
        goal=goal,
        expected_outcome="",
        initial_message=goal,
        mode=tpl.mode,
        visibility=Visibility.PRIVATE,
        agents=[{"agent_id": UUID(a), "role_in_work": ""} for a in cfg.get("agent_ids", [])],
    )
    # Hinweis: create_work/create_run committen jeweils einzeln (keine gemeinsame
    # Transaktion). Schlägt ein späterer Schritt fehl, bleibt ggf. ein verwaister
    # (privater, run-loser) Work zurück — bewusst akzeptiert für die 5a-Strukturphase.
    work = await work_svc.create_work(db, user, work_payload)

    # Pro-Instanz-Artefakt (Phase 5d) für (Anwender, primärer Agent) anlegen — jede
    # Instanziierung erzeugt einen eigenen Kontext mit eigener id/Seite/URL.
    # Primärer Agent = erster agent_id.
    agent_ids = cfg.get("agent_ids", [])
    artifact_id: UUID | None = None
    if agent_ids:
        from app.services import artifacts as artifact_svc

        # Best-effort: scheitert die Anlage, legt der Worker die Instanz beim ersten
        # record_version nicht mehr an (5d kennt kein Get-or-Create) — die Instanziierung
        # darf daran trotzdem nicht scheitern; der Nutzer landet dann auf der Work-Seite.
        try:
            art = await artifact_svc.create_instance(
                db,
                owner_id=user.id,
                agent_id=UUID(agent_ids[0]),
                title=_instance_title(tpl.title, tpl.input_schema or [], inputs),
                output_type=tpl.output_type.value,
                template_id=tpl.id,
                inputs=inputs,
                output_template=ot,
                output_mode=(tpl.config or {}).get("default_output_mode") or "hinzufuegen",
            )
            artifact_id = art.id
        except Exception:
            logger.exception("artifact-instance-create-failed", work_id=str(work.id))
            await db.rollback()

    # Ziel-Loop-Konfiguration aus dem Template auf den erzeugten Work schreiben (Phase 5b);
    # die Ziel-Instanz (artifact_id) kommt für den Worker hier herein (Phase 5d).
    work_orm = await db.get(Work, work.id)
    if work_orm is not None:
        work_orm.loop_config = {
            "enabled": True,
            "max_iterations": tpl.max_iterations,
            "max_cost_usd": tpl.max_cost_usd,
            "output_type": tpl.output_type.value,
            "success_criteria": tpl.success_criteria,
            "artifact_id": str(artifact_id) if artifact_id is not None else None,
        }
        await db.commit()

    trun = TemplateRun(template_id=tpl.id, user_id=user.id, inputs=inputs, work_id=work.id)
    db.add(trun)
    await db.commit()
    await db.refresh(trun)

    # Konversationelle Instanzen: KEIN Auto-Generierungslauf mehr. Würde der alte
    # GoalLoop hier starten, machte das Modell aus dem „stell Fragen"-Prompt eine
    # HTML-Fragebogen-Seite im Canvas. Der Canvas entsteht jetzt ausschließlich aus
    # dem Dialog (Chat-Turns); das Begrüßungs-Greeting stößt das Frontend via /start an.
    return InstantiateResponse(
        template_run_id=trun.id,
        work_id=work.id,
        run_id=None,
        artifact_id=artifact_id,
    )


async def request_publication(db, template_id, user) -> bool:
    tpl = await db.get(Template, template_id)
    if tpl is None or tpl.owner_id != user.id:
        return False
    if tpl.visibility != Visibility.PRIVATE or tpl.publish_status == "pending":
        return False
    tpl.publish_status = "pending"
    tpl.publish_note = ""
    await db.commit()
    return True


async def list_publication_requests(db) -> list[dict]:
    from app.db.models import User as _U
    rows = (await db.execute(select(Template).where(Template.publish_status == "pending")
                             .order_by(Template.created_at.asc()))).scalars().all()
    out = []
    for t in rows:
        owner = await db.get(_U, t.owner_id)
        out.append({"id": t.id, "title": t.title, "category": t.category,
                    "owner_name": owner.name if owner else "", "created_at": t.created_at})
    return out


async def approve_publication(db, template_id) -> bool:
    tpl = await db.get(Template, template_id)
    if tpl is None:
        return False
    tpl.visibility = Visibility.PUBLIC; tpl.publish_status = ""; tpl.publish_note = ""
    await db.commit(); return True


async def reject_publication(db, template_id, note="") -> bool:
    tpl = await db.get(Template, template_id)
    if tpl is None:
        return False
    tpl.publish_status = "rejected"; tpl.publish_note = note or ""
    await db.commit(); return True
