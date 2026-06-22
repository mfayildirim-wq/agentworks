from __future__ import annotations

import os
import re
import uuid
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.models import Artifact, ArtifactFile

settings = get_settings()

# Bilder (direkt einbettbar) + gängige Dokumente. Der Agent entscheidet, was damit passiert.
_ALLOWED = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
_MAX_BYTES = 25 * 1024 * 1024


def _folder(owner_id: UUID, artifact_id: UUID) -> str:
    folder = os.path.join(settings.media_root, "artifacts", str(owner_id), str(artifact_id))
    os.makedirs(folder, exist_ok=True)
    return folder


def _disk_path(url: str) -> str:
    """Wandelt einen /media/…-URL in den Plattenpfad unter media_root um.

    Härtet gegen Pfad-Traversal: der aufgelöste Pfad muss unter media_root bleiben.
    """
    if not url.startswith("/media/"):
        raise ValueError(f"unerwartetes URL-Format: {url!r}")
    root = os.path.normpath(settings.media_root)
    resolved = os.path.normpath(os.path.join(root, url[len("/media/"):]))
    if resolved != root and not resolved.startswith(root + os.sep):
        raise ValueError(f"URL verlässt media_root: {url!r}")
    return resolved


async def save_files(
    db: AsyncSession, artifact_id: UUID, owner_id: UUID, files: list[UploadFile]
) -> list[ArtifactFile] | None:
    """Speichert Dateien neben der HTML der Instanz und legt je eine Zeile an.
    `None`, wenn die Instanz nicht existiert oder nicht dem Anfragenden gehört."""
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != owner_id:
        return None
    if not files:
        raise HTTPException(400, "Keine Dateien hochgeladen.")
    # Pass 1: alles validieren + lesen, bevor irgendetwas auf die Platte geht
    # (sonst lägen bei Ablehnung einer späteren Datei verwaiste Dateien herum).
    prepared: list[tuple[UploadFile, str, bytes]] = []
    for f in files:
        ext = _ALLOWED.get((f.content_type or "").lower())
        if ext is None:
            raise HTTPException(400, f"Nicht unterstützter Typ: {f.content_type}")
        data = await f.read()
        if len(data) > _MAX_BYTES:
            raise HTTPException(400, "Datei zu groß (max 25 MB).")
        prepared.append((f, ext, data))

    # Pass 2: auf die Platte schreiben + Zeilen anlegen
    saved: list[ArtifactFile] = []
    for f, ext, data in prepared:
        name = f"{uuid.uuid4().hex}{ext}"
        with open(os.path.join(_folder(owner_id, artifact_id), name), "wb") as fh:
            fh.write(data)
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", (f.filename or name))[:255]
        row = ArtifactFile(
            artifact_id=artifact_id,
            owner_id=owner_id,
            filename=safe_name,
            url=f"/media/artifacts/{owner_id}/{artifact_id}/{name}",
            content_type=(f.content_type or "")[:100],
            size=len(data),
        )
        db.add(row)
        saved.append(row)
    await db.commit()
    for r in saved:
        await db.refresh(r)
    return saved


async def list_files(
    db: AsyncSession, artifact_id: UUID, owner_id: UUID
) -> list[ArtifactFile] | None:
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != owner_id:
        return None
    rows = await db.execute(
        select(ArtifactFile)
        .where(ArtifactFile.artifact_id == artifact_id)
        .order_by(ArtifactFile.created_at)
    )
    return list(rows.scalars().all())


async def delete_file(
    db: AsyncSession, artifact_id: UUID, file_id: UUID, owner_id: UUID
) -> bool:
    row = await db.get(ArtifactFile, file_id)
    if row is None or row.owner_id != owner_id or row.artifact_id != artifact_id:
        return False
    try:
        os.remove(_disk_path(row.url))
    except (OSError, ValueError):
        pass  # Platte best-effort; DB ist die Wahrheit
    await db.delete(row)
    await db.commit()
    return True


_MAX_DOC_CHARS = 15_000


async def attachments_context(
    db: AsyncSession, artifact_id: UUID, file_ids: list[UUID]
) -> str:
    """Baut den Kontextblock für angehängte Dateien DIESER Instanz.

    - Dokumente (PDF/DOCX/TXT/MD/CSV): extrahierter Klartext inline (gekürzt auf
      _MAX_DOC_CHARS Zeichen) — so liest jedes Modell den Inhalt, ohne Tools/Vision.
    - Bilder: URL + Hinweis, dass sie per <img src="…"> in die Seite eingebaut werden
      können. Leerer String, wenn keine gültigen Dateien dabei sind.
    Enthält bewusst KEINE Verhaltensvorschrift — was der Agent tut, bestimmt der Dialog.
    """
    if not file_ids:
        return ""
    rows = await db.execute(
        select(ArtifactFile).where(
            ArtifactFile.artifact_id == artifact_id, ArtifactFile.id.in_(file_ids)
        )
    )
    files = list(rows.scalars().all())
    if not files:
        return ""

    from app.services.file_text import extract_text

    parts: list[str] = []
    for f in files:
        if (f.content_type or "").startswith("image/"):
            parts.append(
                f'- Bild „{f.filename}": {f.url} '
                f'(du kannst es per <img src="{f.url}"> in die Seite einbauen)'
            )
            continue
        disk = _disk_path(f.url)  # Security-Guard (Pfad-Traversal) — ValueError NICHT schlucken
        try:
            with open(disk, "rb") as fh:
                data = fh.read()
            text = extract_text(f.filename, data)
        except Exception:  # noqa: BLE001 — Extraktion ist best-effort (pypdf/docx werfen diverse Typen)
            text = ""
        if text.strip():
            clipped = text[:_MAX_DOC_CHARS]
            if len(text) > _MAX_DOC_CHARS:
                clipped += "\n… [gekürzt]"
            parts.append(f'- Dokument „{f.filename}" — Inhalt:\n{clipped}')
        else:
            parts.append(f'- Datei „{f.filename}" ({f.content_type}): {f.url} (kein Text lesbar)')

    return "\n\nAngehängte Dateien:\n" + "\n".join(parts)
