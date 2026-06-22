from __future__ import annotations

import os
import uuid

from fastapi import HTTPException, UploadFile

from app.core.settings import get_settings

settings = get_settings()

_ALLOWED = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
_MAX_BYTES = 2 * 1024 * 1024


async def save_upload(file: UploadFile, kind: str = "avatars") -> str:
    ext = _ALLOWED.get((file.content_type or "").lower())
    if ext is None:
        raise HTTPException(400, f"Nicht unterstützter Typ: {file.content_type}")
    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(400, "Datei zu groß (max 2 MB).")
    folder = os.path.join(settings.media_root, kind)
    os.makedirs(folder, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(folder, name), "wb") as fh:
        fh.write(data)
    return f"/media/{kind}/{name}"


async def list_free_avatars(db) -> list[str]:
    """Avatar-Dateien im media/avatars-Ordner, die KEINER Vorlage und keinem Agenten
    zugeordnet sind (manuelle Zuordnung durch den Nutzer). Wiederverwendbar für
    verwaiste wie hochgeladene Bilder, die noch frei im Ordner liegen."""
    from sqlalchemy import select

    from app.db.models import Agent, Template

    folder = os.path.join(settings.media_root, "avatars")
    try:
        files = sorted(
            f for f in os.listdir(folder)
            if not f.startswith(".") and os.path.isfile(os.path.join(folder, f))
        )
    except FileNotFoundError:
        return []
    all_urls = [f"/media/avatars/{f}" for f in files]
    assigned: set[str] = set()
    for col in (Template.image_url, Agent.avatar_url):
        rows = (await db.execute(select(col).where(col.like("/media/avatars/%")))).scalars().all()
        assigned.update(r for r in rows if r)
    return [u for u in all_urls if u not in assigned]
