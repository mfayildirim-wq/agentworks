from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AdminUser, CurrentUser
from app.db.session import get_db
from app.schemas.mcp import McpServerCreate, McpServerOut, McpServerUpdate
from app.services import mcp_catalog

router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])


@router.get("", response_model=list[McpServerOut])
async def list_servers(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return [mcp_catalog.to_out(s) for s in await mcp_catalog.list_all(db)]


@router.post("", response_model=McpServerOut, status_code=201)
async def create_server(body: McpServerCreate, admin: AdminUser, db: AsyncSession = Depends(get_db)):
    if await mcp_catalog.get(db, body.server_id) is not None:
        raise HTTPException(409, "server_id existiert bereits")
    try:
        s = await mcp_catalog.create(
            db, server_id=body.server_id, name=body.name, description=body.description,
            transport=body.transport, url=body.url, requires_credential=body.requires_credential,
            updated_by=admin.email,
            auth_header=body.auth_header, auth_value_template=body.auth_value_template,
            secret_label=body.secret_label,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return mcp_catalog.to_out(s)


@router.put("/{server_id}", response_model=McpServerOut)
async def update_server(server_id: str, body: McpServerUpdate, admin: AdminUser, db: AsyncSession = Depends(get_db)):
    try:
        s = await mcp_catalog.update(db, server_id, updated_by=admin.email, **body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if s is None:
        raise HTTPException(404, "unbekannt")
    return mcp_catalog.to_out(s)


@router.delete("/{server_id}", status_code=204)
async def delete_server(server_id: str, admin: AdminUser, db: AsyncSession = Depends(get_db)):
    if not await mcp_catalog.delete(db, server_id):
        raise HTTPException(404, "unbekannt")
    return Response(status_code=204)
