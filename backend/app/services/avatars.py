"""KI-Avatar-Generierung für Agent-Vorlagen.

Zweistufig, vollständig über OpenAI: (1) ein Text-Modell (`gpt-4o-mini`) formuliert aus
Name/Beschreibung/Prompt der Vorlage eine knappe englische Bildbeschreibung einer **Figur**
(Mensch/Tier/Roboter) mit dem zur Aufgabe passenden **Werkzeug**; (2) `gpt-image-1` erzeugt
daraus ein Bild im vom Nutzer gewählten **Stil** (siehe `avatar_styles`). Das Bild wird auf
200×200 skaliert und als PNG unter `{media_root}/avatars/` abgelegt.

Gibt der Nutzer einen Freitext-Hinweis (`hint`) an, ersetzt dieser die Beschreibungsstufe.
Fällt die Beschreibungsstufe aus, greift eine simpel zusammengesetzte Fallback-Beschreibung
aus den Feldern — das Generieren soll daran nie scheitern. Fehlt der OpenAI-Key, ist das ein
echter Konfigurationsfehler (`ValueError` → Endpoint 400).
"""

from __future__ import annotations

import base64
import io
import uuid
from pathlib import Path

from fastapi.concurrency import run_in_threadpool
from PIL import Image

from app.core.settings import get_settings
from app.services import avatar_styles

settings = get_settings()

_DESCRIBE_MODEL = "gpt-4o-mini"

_DESCRIBE_SYSTEM = (
    "You design character avatars for AI agents. Given an agent's name, description and "
    "system prompt, reply with ONE short English sentence describing a single character — "
    "a person, an animal, or a robot — that personifies this agent and is holding or using "
    "the tools relevant to its task (e.g. a travel-planner robot holding a map and a "
    "suitcase; a chef cat holding a whisk and a pan). Describe only the character and its "
    "tools, no background, no art style, no text in the image. Reply with the sentence only."
)

# Komposition/Rahmung, stil-unabhängig (der Look kommt aus avatar_styles.fragment).
_BASE_SUFFIX = (
    ", single character, centered portrait composition, clean simple background, "
    "no text, no words, no watermark"
)


async def _describe(name: str, description: str, system_prompt: str) -> str:
    """Knappe englische Figur-Beschreibung via OpenAI-Text-Modell."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=_DESCRIBE_MODEL,
        messages=[
            {"role": "system", "content": _DESCRIBE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Name: {name}\nDescription: {description}\n"
                    f"System prompt: {system_prompt[:1500]}"
                ),
            },
        ],
        max_tokens=120,
    )
    return (resp.choices[0].message.content or "").strip()


def _fallback_description(name: str, description: str, system_prompt: str) -> str:
    """Direkt aus den Feldern gebaute Figur-Beschreibung, wenn die Beschreibungsstufe ausfällt."""
    who = " — ".join(p for p in (name, description) if p and p.strip()) or "an assistant"
    return (
        f"A friendly character mascot representing {who}, "
        "shown holding the tools relevant to its task"
    )


async def _describe_safe(name: str, description: str, system_prompt: str) -> str:
    try:
        out = await _describe(name, description, system_prompt)
        if out:
            return out
    except Exception:  # noqa: BLE001 — Beschreibungsstufe aus/leer → Fallback, kein harter Fehler
        pass
    return _fallback_description(name, description, system_prompt)


async def _generate_b64(prompt: str) -> str:
    """OpenAI `gpt-image-1` → Base64-PNG (`b64_json`)."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
        quality="low",
        n=1,
    )
    return resp.data[0].b64_json


def _save_png(b64: str) -> str:
    """Base64-PNG → 200×200 RGBA-PNG unter media_root/avatars, gibt /media-URL zurück."""
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
    img = img.resize((200, 200), Image.LANCZOS)
    folder = Path(settings.media_root) / "avatars"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.png"
    img.save(folder / name, format="PNG")
    return f"/media/avatars/{name}"


async def generate_avatar(
    name: str, description: str, system_prompt: str, hint: str = "", style: str = ""
) -> str:
    """Erzeugt ein 200×200-Avatar-PNG und gibt dessen `/media/...`-URL zurück.

    Ist `hint` gesetzt, steuert dieser Freitext die Figur direkt (Beschreibungsstufe
    übersprungen); sonst beschreibt OpenAI die Figur aus Name/Beschreibung/Prompt.
    `style` wählt den Look (siehe `avatar_styles`; unbekannt/leer → Default).

    `ValueError` wenn kein OpenAI-Key konfiguriert ist. OpenAI-Fehler werden
    durchgereicht (Endpoint → 502).
    """
    if not settings.openai_api_key:
        raise ValueError("Kein OpenAI-Key konfiguriert.")
    if hint.strip():
        base = hint.strip()
    else:
        base = await _describe_safe(name, description, system_prompt)
    prompt = f"{base}, {avatar_styles.fragment(style)}{_BASE_SUFFIX}"
    b64 = await _generate_b64(prompt)
    return await run_in_threadpool(_save_png, b64)
