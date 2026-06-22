from __future__ import annotations

import base64
import inspect
import io

import pytest
from PIL import Image

from app.services import avatar_styles, avatars


def _png_b64(size: tuple[int, int] = (10, 10)) -> str:
    """Kleines, gültiges PNG als Base64 — steht für die OpenAI-`b64_json`-Antwort."""
    buf = io.BytesIO()
    Image.new("RGBA", size, (10, 20, 30, 255)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ---- Stil-Registry ---------------------------------------------------------


def test_style_fragment_known_returns_prompt():
    assert "photoreal" in avatar_styles.fragment("fotorealistisch").lower()
    assert "anime" in avatar_styles.fragment("anime").lower()


def test_style_fragment_unknown_and_empty_fall_back_to_default():
    default = avatar_styles.fragment("fotorealistisch")
    assert avatar_styles.fragment("gibt-es-nicht") == default
    assert avatar_styles.fragment("") == default


def test_list_styles_unique_ids_with_groups():
    styles = avatar_styles.list_styles()
    assert len(styles) > 30
    ids = [s["id"] for s in styles]
    assert len(ids) == len(set(ids))  # eindeutige ids
    for s in styles:
        assert s["id"] and s["label"] and s["group"] and s["prompt"]


# ---- Beschreibung via OpenAI, nicht lokal ----------------------------------


def test_service_does_not_use_local_ollama():
    """Beschreibung läuft über OpenAI — kein Ollama/lokales Modell mehr im Service."""
    src = inspect.getsource(avatars).lower()
    assert "ollama" not in src


# ---- Service ---------------------------------------------------------------


async def test_generate_avatar_uses_describe_and_style(monkeypatch, tmp_path):
    monkeypatch.setattr(avatars.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(avatars.settings, "media_root", str(tmp_path))

    async def fake_describe(n, d, s):
        return "a friendly travel robot holding a map"

    monkeypatch.setattr(avatars, "_describe", fake_describe)

    captured: dict[str, str] = {}

    async def fake_b64(prompt: str) -> str:
        captured["p"] = prompt
        return _png_b64()

    monkeypatch.setattr(avatars, "_generate_b64", fake_b64)

    url = await avatars.generate_avatar(
        "Reiseplaner", "plant Reisen", "sei hilfreich", style="fotorealistisch"
    )
    assert url.startswith("/media/avatars/") and url.endswith(".png")
    assert "travel robot" in captured["p"]  # Beschreibung fliesst ein
    assert "photoreal" in captured["p"].lower()  # gewaehlter Stil fliesst ein
    img = Image.open(tmp_path / "avatars" / url.split("/")[-1])
    assert img.format == "PNG" and img.size == (200, 200)


async def test_generate_avatar_hint_skips_describe(monkeypatch, tmp_path):
    monkeypatch.setattr(avatars.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(avatars.settings, "media_root", str(tmp_path))

    async def boom(n, d, s):
        raise AssertionError("Hinweis vorhanden → keine Beschreibungs-Generierung")

    monkeypatch.setattr(avatars, "_describe", boom)

    captured: dict[str, str] = {}

    async def fake_b64(prompt: str) -> str:
        captured["p"] = prompt
        return _png_b64()

    monkeypatch.setattr(avatars, "_generate_b64", fake_b64)

    url = await avatars.generate_avatar(
        "Helfer", "x", "y", hint="a blue dragon with a sword", style="anime"
    )
    assert url.endswith(".png")
    assert "blue dragon" in captured["p"]
    assert "anime" in captured["p"].lower()


async def test_generate_avatar_describe_error_uses_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(avatars.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(avatars.settings, "media_root", str(tmp_path))

    async def boom(n, d, s):
        raise RuntimeError("openai chat down")

    monkeypatch.setattr(avatars, "_describe", boom)

    captured: dict[str, str] = {}

    async def fake_b64(prompt: str) -> str:
        captured["p"] = prompt
        return _png_b64()

    monkeypatch.setattr(avatars, "_generate_b64", fake_b64)

    url = await avatars.generate_avatar("Reiseplaner", "plant Reisen", "", style="")
    assert url.endswith(".png")
    assert "Reiseplaner" in captured["p"]  # Fallback-Beschreibung aus den Feldern


async def test_generate_avatar_no_key_raises_valueerror(monkeypatch):
    monkeypatch.setattr(avatars.settings, "openai_api_key", "")
    with pytest.raises(ValueError):
        await avatars.generate_avatar("Helfer", "", "")


# ---- Endpoint --------------------------------------------------------------


async def test_styles_endpoint_lists_styles(client):
    r = await client.get("/avatars/styles")
    assert r.status_code == 200, r.text
    items = r.json()
    ids = [s["id"] for s in items]
    assert "fotorealistisch" in ids
    assert all({"id", "label", "group"} <= set(s) for s in items)


async def test_generate_endpoint_returns_url(client, monkeypatch, tmp_path):
    monkeypatch.setattr(avatars.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(avatars.settings, "media_root", str(tmp_path))

    async def fake_describe(n, d, s):
        return "a robot"

    monkeypatch.setattr(avatars, "_describe", fake_describe)

    async def fake_b64(prompt: str) -> str:
        return _png_b64()

    monkeypatch.setattr(avatars, "_generate_b64", fake_b64)

    r = await client.post(
        "/avatars/generate", json={"name": "Helfer", "style": "pixar-stil"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("/media/avatars/")


async def test_generate_endpoint_passes_hint_and_style(client, monkeypatch, tmp_path):
    monkeypatch.setattr(avatars.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(avatars.settings, "media_root", str(tmp_path))

    async def boom(n, d, s):
        raise AssertionError("Hinweis vorhanden → keine Beschreibungs-Generierung")

    monkeypatch.setattr(avatars, "_describe", boom)

    captured: dict[str, str] = {}

    async def fake_b64(prompt: str) -> str:
        captured["p"] = prompt
        return _png_b64()

    monkeypatch.setattr(avatars, "_generate_b64", fake_b64)

    r = await client.post(
        "/avatars/generate",
        json={"name": "Helfer", "hint": "a red robot with a wrench", "style": "cyberpunk"},
    )
    assert r.status_code == 200, r.text
    assert "red robot" in captured["p"]
    assert "cyberpunk" in captured["p"].lower()


async def test_generate_endpoint_empty_name_422(client):
    r = await client.post("/avatars/generate", json={"name": ""})
    assert r.status_code == 422, r.text


async def test_generate_endpoint_no_key_400(client, monkeypatch):
    monkeypatch.setattr(avatars.settings, "openai_api_key", "")
    r = await client.post("/avatars/generate", json={"name": "Helfer"})
    assert r.status_code == 400, r.text


async def test_generate_endpoint_openai_error_502(client, monkeypatch, tmp_path):
    monkeypatch.setattr(avatars.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(avatars.settings, "media_root", str(tmp_path))

    async def fake_describe(n, d, s):
        return "a robot"

    monkeypatch.setattr(avatars, "_describe", fake_describe)

    async def boom(prompt: str) -> str:
        raise RuntimeError("openai rate limit")

    monkeypatch.setattr(avatars, "_generate_b64", boom)
    r = await client.post("/avatars/generate", json={"name": "Helfer"})
    assert r.status_code == 502, r.text
