"""Bilderzeugung für Agenten (OpenAI gpt-image-1). Speichert das volle PNG unter
/media/generated und gibt die öffentliche URL zurück. Defensiv: bei Fehler/kein Key None."""
from __future__ import annotations

import base64
import uuid
from pathlib import Path

from app.core.settings import get_settings

settings = get_settings()


async def generate(prompt: str) -> str | None:
    if not settings.openai_api_key:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp = await client.images.generate(
            model="gpt-image-1", prompt=(prompt or "")[:4000],
            size="1024x1024", quality="low", n=1)
        b64 = resp.data[0].b64_json
        folder = Path(settings.media_root) / "generated"
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}.png"
        (folder / name).write_bytes(base64.b64decode(b64))
        return f"/media/generated/{name}"
    except Exception:
        return None
