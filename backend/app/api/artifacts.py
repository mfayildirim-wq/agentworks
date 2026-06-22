from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, OptionalUser
from app.db.models import Agent, Artifact, Template, User, Visibility
from app.db.session import get_db
from app.schemas.artifacts import (
    AdjustRequest,
    AdjustResponse,
    ArtifactFileOut,
    ArtifactListItem,
    ArtifactMessageOut,
    ArtifactView,
    ChainSetIn,
    ChatRequest,
    ConnectionOut,
    ConnectionPut,
    LayoutPut,
    MasterPage,
    OutputModeIn,
    PublishResult,
    ScheduleOut,
    SchedulePut,
    SharedArtifactOut,
    SlotPut,
)
from app.services import friends as friends_svc
from app.services import artifact_chat as chat_svc
from app.services import artifact_connections as conn_svc
from app.services import artifact_files as files_svc
from app.services import artifact_schedules as sched_svc
from app.services import artifacts as svc
from app.services import canvas_slots
from app.services import chains
from app.services import connection_registry
from app.services import mcp_catalog
from app.services import sftp_publish

router = APIRouter(prefix="/artifacts", tags=["artifacts"])
public_router = APIRouter(tags=["artifacts-public"])

_CSP = (
    "default-src 'none'; script-src 'none'; img-src 'self' https: data:;"
    " style-src 'unsafe-inline'; font-src https: data:"
)


@router.get("", response_model=list[ArtifactListItem])
async def list_mine(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return await svc.list_mine(db, user)


@router.get("/shared", response_model=list[SharedArtifactOut])
async def shared_with_me(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Instanzen meiner bestätigten Freunde mit Sichtbarkeit friends/public."""
    from sqlalchemy import select

    friend_ids = [u.id for u in await friends_svc.list_friends(db, user.id)]
    if not friend_ids:
        return []
    rows = (
        await db.execute(
            select(Artifact)
            .where(
                Artifact.owner_id.in_(friend_ids),
                Artifact.visibility.in_((Visibility.FRIENDS, Visibility.PUBLIC)),
                Artifact.current_version_id.is_not(None),
            )
            .order_by(Artifact.updated_at.desc())
            .limit(100)
        )
    ).scalars().all()

    out: list[SharedArtifactOut] = []
    for art in rows:
        # Icon: Vorlage zuerst, sonst Agent-Avatar (wie get_view).
        icon: str | None = None
        if art.template_id is not None:
            tpl = await db.get(Template, art.template_id)
            icon = tpl.image_url if tpl else None
        if not icon:
            agent = await db.get(Agent, art.agent_id)
            icon = agent.avatar_url if agent else None
        owner = await db.get(User, art.owner_id)
        out.append(
            SharedArtifactOut(
                artifact_id=art.id,
                title=art.title,
                icon=icon,
                owner_name=owner.name if owner else "",
                visibility=art.visibility.value,
                updated_at=art.updated_at,
            )
        )
    return out


@router.get("/public", response_model=list[SharedArtifactOut])
async def public_instances(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Alle öffentlichen Instanzen + die friends-Instanzen meiner bestätigten Freunde."""
    from sqlalchemy import and_, or_, select

    friend_ids = [u.id for u in await friends_svc.list_friends(db, user.id)]
    vis_cond = Artifact.visibility == Visibility.PUBLIC
    if friend_ids:
        vis_cond = or_(
            vis_cond,
            and_(Artifact.owner_id.in_(friend_ids), Artifact.visibility == Visibility.FRIENDS),
        )
    rows = (
        await db.execute(
            select(Artifact)
            .where(Artifact.current_version_id.is_not(None), vis_cond)
            .order_by(Artifact.updated_at.desc())
            .limit(200)
        )
    ).scalars().all()

    out: list[SharedArtifactOut] = []
    for art in rows:
        icon: str | None = None
        template_title: str | None = None
        if art.template_id is not None:
            tpl = await db.get(Template, art.template_id)
            if tpl is not None:
                icon = tpl.image_url
                template_title = tpl.title
        if not icon:
            agent = await db.get(Agent, art.agent_id)
            icon = agent.avatar_url if agent else None
        owner = await db.get(User, art.owner_id)
        out.append(
            SharedArtifactOut(
                artifact_id=art.id,
                title=art.title,
                icon=icon,
                owner_name=owner.name if owner else "",
                visibility=art.visibility.value,
                updated_at=art.updated_at,
                template_title=template_title,
            )
        )
    return out


@router.get("/{artifact_id}", response_model=ArtifactView)
async def get_one(artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    view = await svc.get_view(db, artifact_id, user)
    if view is None:
        raise HTTPException(404, "not found")
    return view


@router.delete("/{artifact_id}", status_code=204)
async def delete_one(artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    if not await svc.delete_artifact(db, artifact_id, user):
        raise HTTPException(404, "not found or forbidden")
    return Response(status_code=204)


@router.post("/{artifact_id}/adjust", response_model=AdjustResponse, status_code=201)
async def adjust(
    artifact_id: UUID,
    payload: AdjustRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    run_id = await svc.adjust(db, artifact_id, user.id, payload.instruction)
    if run_id is None:
        raise HTTPException(404, "not found or forbidden")
    return AdjustResponse(run_id=run_id)


@router.post("/{artifact_id}/chat", status_code=202)
async def chat(
    artifact_id: UUID,
    payload: ChatRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Dialog-Turn: speichert die Nachricht und stößt den Agenten an (asynchron)."""
    ok = await chat_svc.post_chat_message(
        db, artifact_id, user.id, payload.message, payload.file_ids
    )
    if not ok:
        raise HTTPException(404, "not found or forbidden")
    return {"ok": True}


@router.post("/{artifact_id}/start", status_code=202)
async def start(artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Init-Turn beim ersten Öffnen (Begrüßung), idempotent."""
    ok = await chat_svc.start_turn(db, artifact_id, user.id)
    if not ok:
        raise HTTPException(404, "not found or forbidden")
    return {"ok": True}


@router.get("/{artifact_id}/messages", response_model=list[ArtifactMessageOut])
async def messages(artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    msgs = await chat_svc.list_chat_messages(db, artifact_id, user.id)
    if msgs is None:
        raise HTTPException(404, "not found or forbidden")
    return msgs


@router.post("/{artifact_id}/files", response_model=list[ArtifactFileOut], status_code=201)
async def upload_files(
    artifact_id: UUID,
    user: CurrentUser,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    saved = await files_svc.save_files(db, artifact_id, user.id, files)
    if saved is None:
        raise HTTPException(404, "not found or forbidden")
    return saved


@router.get("/{artifact_id}/files", response_model=list[ArtifactFileOut])
async def list_files(
    artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    rows = await files_svc.list_files(db, artifact_id, user.id)
    if rows is None:
        raise HTTPException(404, "not found or forbidden")
    return rows


@router.delete("/{artifact_id}/files/{file_id}", status_code=204)
async def delete_file(
    artifact_id: UUID,
    file_id: UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    ok = await files_svc.delete_file(db, artifact_id, file_id, user.id)
    if not ok:
        raise HTTPException(404, "not found or forbidden")
    return Response(status_code=204)


@router.get("/{artifact_id}/schedule", response_model=ScheduleOut | None)
async def get_schedule(artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    sched = await sched_svc.get(db, artifact_id, user.id)
    return sched_svc.to_out(sched) if sched is not None else None


@router.put("/{artifact_id}/schedule", response_model=ScheduleOut)
async def put_schedule(
    artifact_id: UUID,
    payload: SchedulePut,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    sched = await sched_svc.upsert(
        db,
        artifact_id,
        user.id,
        cadence=payload.cadence,
        refresh_instruction=payload.refresh_instruction,
        enabled=payload.enabled,
        completion_mode=payload.completion_mode,
        end_at=payload.end_at,
    )
    if sched is None:
        raise HTTPException(404, "not found or forbidden")
    return sched_svc.to_out(sched)


@router.delete("/{artifact_id}/schedule", status_code=204)
async def delete_schedule(
    artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    if not await sched_svc.delete(db, artifact_id, user.id):
        raise HTTPException(404, "not found or forbidden")
    return Response(status_code=204)


@router.post("/{artifact_id}/schedule/resume", response_model=ScheduleOut)
async def resume_schedule(
    artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    sched = await sched_svc.resume(db, artifact_id, user.id)
    if sched is None:
        raise HTTPException(404, "not found or forbidden")
    return sched_svc.to_out(sched)


@router.get("/{artifact_id}/connections", response_model=list[ConnectionOut])
async def list_connections(artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    rows = await conn_svc.list_connections(db, artifact_id, user.id)
    return [conn_svc.to_safe_out(c) for c in rows]


@router.put("/{artifact_id}/connections/{kind}", response_model=ConnectionOut)
async def put_connection(
    artifact_id: UUID, kind: str, payload: ConnectionPut,
    user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    valid = connection_registry.is_valid(kind)
    if not valid and kind.startswith("mcp:"):
        entry = await mcp_catalog.get(db, kind[4:])
        valid = entry is not None and entry.enabled and entry.requires_credential
    if not valid:
        raise HTTPException(400, f"unbekannter Verbindungstyp: {kind}")
    conn = await conn_svc.upsert_connection(
        db, artifact_id, user.id, kind=kind, config=payload.config, secret=payload.secret,
    )
    if conn is None:
        raise HTTPException(404, "not found or forbidden")
    return conn_svc.to_safe_out(conn)


@router.get("/{artifact_id}/slots")
async def get_slots(artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    data = await canvas_slots.get_slots(db, artifact_id, user.id)
    if data is None:
        raise HTTPException(404, "not found or forbidden")
    return data


@router.put("/{artifact_id}/slots/{slot_id}")
async def put_slot(
    artifact_id: UUID, slot_id: str, payload: SlotPut,
    user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    data = await canvas_slots.upsert_slot(
        db, artifact_id, user.id, slot_id=slot_id, title=payload.title,
        body=payload.body, type=payload.type, order=payload.order,
    )
    if data is None:
        raise HTTPException(404, "not found or forbidden")
    return data


@router.delete("/{artifact_id}/slots/{slot_id}")
async def delete_slot(
    artifact_id: UUID, slot_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    data = await canvas_slots.remove_slot(db, artifact_id, user.id, slot_id)
    if data is None:
        raise HTTPException(404, "not found or forbidden")
    return data


@router.put("/{artifact_id}/layout")
async def put_layout(
    artifact_id: UUID, payload: LayoutPut, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    try:
        data = await canvas_slots.set_layout(db, artifact_id, user.id, payload.layout)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if data is None:
        raise HTTPException(404, "not found or forbidden")
    return data


@router.post("/{artifact_id}/publish", response_model=PublishResult)
async def publish_artifact(
    artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    ok, message = await sftp_publish.publish_artifact(db, artifact_id, user.id)
    return PublishResult(ok=ok, message=message)


@router.put("/{artifact_id}/visibility", response_model=dict)
async def set_visibility(
    artifact_id: UUID, body: dict, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    val = (body or {}).get("visibility")
    if val not in ("private", "friends", "public"):
        raise HTTPException(400, "ungültige Sichtbarkeit")
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != user.id:
        raise HTTPException(404, "not found")
    art.visibility = Visibility(val)
    await db.commit()
    return {"ok": True, "visibility": val}


@router.put("/{artifact_id}/chain")
async def set_chain(
    artifact_id: UUID, body: ChainSetIn, user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    ok, reason = await chains.set_chain(
        db, artifact_id, user.id, next_id=body.next_artifact_id, auto=body.auto
    )
    if not ok:
        raise HTTPException(403 if reason == "forbidden" else 400, reason or "ungültig")
    return {"ok": True}


@router.post("/{artifact_id}/forward")
async def forward_chain(
    artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != user.id:
        raise HTTPException(403, "forbidden")
    run_id = await chains.forward(db, artifact_id)
    if run_id is None:
        raise HTTPException(400, "Kein nächster Schritt gesetzt.")
    return {"run_id": run_id, "next_artifact_id": art.next_artifact_id}


@router.put("/{artifact_id}/output-mode")
async def set_output_mode(
    artifact_id: UUID, body: OutputModeIn, user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    mode = await svc.set_output_mode(db, artifact_id, user.id, body.mode)
    if mode is None:
        raise HTTPException(404, "not found or forbidden")
    return {"mode": mode}


@router.get("/{artifact_id}/commands")
async def output_commands_list(
    artifact_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != user.id:
        raise HTTPException(404, "not found")
    from app.services import output_commands
    result = list(output_commands.kinds("page"))
    if art.template_id is not None:
        tpl = await db.get(Template, art.template_id)
        for c in ((tpl.config or {}).get("commands", []) if tpl else []):
            result.append({
                "key": c["key"],
                "label": c["label"],
                "kind": "template",
                "mode": c["mode"],
                "instruction": c["instruction"],
            })
    return result


@router.get("/{artifact_id}/versions/{version_id}")
async def get_version(artifact_id: UUID, version_id: UUID, user: CurrentUser,
                      db: AsyncSession = Depends(get_db)):
    v = await svc.get_version(db, artifact_id, user.id, version_id)
    if v is None:
        raise HTTPException(404, "not found")
    return {"version_no": v.version_no, "content": v.content,
            "created_at": v.created_at, "prompt": v.prompt}


@router.post("/{artifact_id}/versions/{version_id}/restore")
async def restore_version(artifact_id: UUID, version_id: UUID, user: CurrentUser,
                          db: AsyncSession = Depends(get_db)):
    new = await svc.restore_version(db, artifact_id, user.id, version_id)
    if new is None:
        raise HTTPException(404, "not found")
    return {"ok": True}


@public_router.get("/users/{user_id}/master", response_model=MasterPage)
async def master_page(
    user_id: str, viewer: OptionalUser, db: AsyncSession = Depends(get_db)
):
    """Master-Seite (Ergebnis-Viewer) eines Nutzers.

    `user_id == "me"` erfordert Login (401 ohne gültiges Token) und nutzt den
    eingeloggten Nutzer als Eigentümer. Sonst wird `user_id` als UUID geparst
    (ungültig → 404); der optional eingeloggte Nutzer ist der Betrachter, der
    nur PUBLIC/UNLISTED-Instanzen sieht (außer er ist selbst der Eigentümer).
    """
    if user_id == "me":
        if viewer is None:
            raise HTTPException(401, "login required")
        owner_id = viewer.id
    else:
        try:
            owner_id = UUID(user_id)
        except (ValueError, AttributeError):
            raise HTTPException(404, "not found") from None
    page = await svc.master_page(db, owner_id, viewer)
    if page is None:
        raise HTTPException(404, "not found")
    return page


@public_router.get("/p/{artifact_id}")
async def public_page(
    artifact_id: UUID, viewer: OptionalUser, db: AsyncSession = Depends(get_db)
):
    html = await svc.public_html(db, artifact_id, viewer=viewer)
    if html is None:
        raise HTTPException(404, "not found")
    return Response(content=html, media_type="text/html", headers={"Content-Security-Policy": _CSP})
