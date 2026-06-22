"""DB-gestützter, vom Admin verwalteter MCP-Server-Katalog.

Nur hier (und enabled) gelistete Server dürfen an Agenten gehängt werden — nie
beliebige URLs. Enthält KEINE Geheimnisse; Zugangsdaten leben pro Instanz in
artifact_connections (verschlüsselt)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import McpServer


def _validate_auth_template(template: str) -> None:
    """Template muss genau den Platzhalter {secret} enthalten (für .format(secret=...))."""
    import string
    fields = [name for _, name, _, _ in string.Formatter().parse(template) if name is not None]
    if fields != ["secret"]:
        raise ValueError("auth_value_template muss genau {secret} enthalten")


async def list_all(db: AsyncSession) -> list[McpServer]:
    rows = await db.execute(select(McpServer).order_by(McpServer.name))
    return list(rows.scalars().all())


async def get(db: AsyncSession, server_id: str) -> McpServer | None:
    rows = await db.execute(select(McpServer).where(McpServer.server_id == server_id))
    return rows.scalars().first()


async def is_valid(db: AsyncSession, server_id: str) -> bool:
    s = await get(db, server_id)
    return s is not None and s.enabled


async def create(
    db: AsyncSession, *, server_id: str, name: str, description: str,
    transport: str, url: str, requires_credential: bool, updated_by: str | None,
    auth_header: str = "Authorization",
    auth_value_template: str = "Bearer {secret}",
    secret_label: str = "Token / API-Key",
) -> McpServer:
    if requires_credential:
        _validate_auth_template(auth_value_template)
    s = McpServer(
        server_id=server_id, name=name, description=description, transport=transport,
        url=url, requires_credential=requires_credential, enabled=True, updated_by=updated_by,
        auth_header=auth_header, auth_value_template=auth_value_template, secret_label=secret_label,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def update(db: AsyncSession, server_id: str, *, updated_by: str | None, **fields) -> McpServer | None:
    s = await get(db, server_id)
    if s is None:
        return None
    if fields.get("auth_value_template") is not None:
        _validate_auth_template(fields["auth_value_template"])
    for key in (
        "name", "description", "transport", "url", "requires_credential", "enabled",
        "auth_header", "auth_value_template", "secret_label",
    ):
        if key in fields and fields[key] is not None:
            setattr(s, key, fields[key])
    s.updated_by = updated_by
    await db.commit()
    await db.refresh(s)
    return s


async def delete(db: AsyncSession, server_id: str) -> bool:
    s = await get(db, server_id)
    if s is None:
        return False
    await db.delete(s)
    await db.commit()
    return True


def to_out(s: McpServer) -> dict:
    return {
        "server_id": s.server_id, "name": s.name, "description": s.description,
        "transport": s.transport, "url": s.url,
        "requires_credential": s.requires_credential, "enabled": s.enabled,
        "auth_header": s.auth_header,
        "auth_value_template": s.auth_value_template,
        "secret_label": s.secret_label,
    }
