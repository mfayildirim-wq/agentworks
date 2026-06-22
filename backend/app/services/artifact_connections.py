from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.db.models import Artifact, ArtifactConnection


async def get_connection(
    db: AsyncSession, artifact_id: UUID, owner_id: UUID, kind: str
) -> ArtifactConnection | None:
    rows = await db.execute(
        select(ArtifactConnection).where(
            ArtifactConnection.artifact_id == artifact_id,
            ArtifactConnection.owner_id == owner_id,
            ArtifactConnection.kind == kind,
        )
    )
    return rows.scalars().first()


async def list_connections(
    db: AsyncSession, artifact_id: UUID, owner_id: UUID
) -> list[ArtifactConnection]:
    rows = await db.execute(
        select(ArtifactConnection).where(
            ArtifactConnection.artifact_id == artifact_id,
            ArtifactConnection.owner_id == owner_id,
        )
    )
    return list(rows.scalars().all())


async def upsert_connection(
    db: AsyncSession,
    artifact_id: UUID,
    owner_id: UUID,
    *,
    kind: str,
    config: dict,
    secret: str,
) -> ArtifactConnection | None:
    """Legt die Verbindung (artifact_id, kind) an/aktualisiert sie. Leeres `secret` bei
    Update behält das bisherige. None, wenn die Instanz fremd/fehlt."""
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != owner_id:
        return None
    conn = await get_connection(db, artifact_id, owner_id, kind)
    if conn is None:
        conn = ArtifactConnection(
            artifact_id=artifact_id, owner_id=owner_id, kind=kind,
            config=config, secret_encrypted=crypto.encrypt(secret or ""),
        )
        db.add(conn)
    else:
        conn.config = {**(conn.config or {}), **config}
        if secret:
            conn.secret_encrypted = crypto.encrypt(secret)
    await db.commit()
    await db.refresh(conn)
    return conn


def to_safe_out(conn: ArtifactConnection) -> dict:
    """Sichere Darstellung — OHNE Geheimnis."""
    return {"kind": conn.kind, "config": conn.config or {}, "configured": True}
