from __future__ import annotations

import os
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.models import (
    Agent,
    AgentVersion,
    Artifact,
    ArtifactJob,
    ArtifactVersion,
    Template,
    TemplateOutput,
    User,
    Visibility,
    Work,
)
from app.schemas.artifacts import (
    ArtifactListItem,
    ArtifactVersionOut,
    ArtifactView,
    ChainNode,
    MasterInstance,
    MasterPage,
    McpCredentialNeed,
    RecentAction,
)
from app.schemas.works import WorkCreate
from app.services import artifact_connections as conn_svc
from app.services import artifact_jobs as jobs_svc
from app.services import mcp_catalog
from app.services import runs as run_svc
from app.services import works as work_svc

settings = get_settings()

# Wenige Iterationen = spürbar schneller (v.a. lokales qwen auf CPU); der Loop
# stoppt ohnehin früher bei STATUS: DONE.
_ADJUST_MAX_ITERATIONS = 2
_ADJUST_MAX_COST = 1.0

# Schritt 3: Fähigkeit, sich selbst zeitgesteuert zu aktualisieren. Wenn der Nutzer
# eine wiederkehrende Aufgabe wünscht (z.B. "jeden Morgen"), hinterlässt der Agent
# GENAU EINEN solchen HTML-Kommentar; der Server wandelt ihn in einen Zeitplan und
# entfernt ihn aus der Seite:
_SCHEDULE_CAPABILITY = (
    "Wiederkehrende Selbst-Aktualisierung: Wenn (und nur wenn) der Nutzer eine "
    "regelmäßige/zeitgesteuerte Aufgabe wünscht, füge GENAU EINEN HTML-Kommentar in "
    "die Seite ein: <!-- SCHEDULE: <hourly|daily|weekly> | <kurze Anweisung> -->. "
    "Sonst keinen solchen Kommentar.\n\n"
)


def build_scope_guard(purpose: str) -> str:
    """Leitplanke: bindet die Instanz an die im Agent/Template definierte Aufgabe.

    Off-Topic-Anfragen werden höflich abgelehnt, die Seite bleibt unverändert.
    Reine Funktion → direkt testbar.
    """
    purpose = (purpose or "").strip() or "die im Template definierte Aufgabe"
    return (
        "WICHTIG — Aufgaben-Grenze (Guardrail):\n"
        "Du handelst AUSSCHLIESSLICH innerhalb dieser Aufgabe:\n"
        f"{purpose}\n"
        "Anfragen außerhalb dieser Aufgabe lehnst du höflich ab "
        "(\"Dafür ist dieser Agent nicht gedacht.\") und gibst die Seite UNVERÄNDERT zurück. "
        "Du nimmst KEINE neuen Aufgaben außerhalb der obigen Beschreibung an.\n\n"
    )


def build_adjust_initial(mode: str, purpose: str, current_page: str, instruction: str) -> str:
    """Baut die Initial-Nachricht für einen Timer-Lauf je nach Modus.

    Stellt die verbindliche Systemzeit voran — auch geplante Läufe (»diese Woche«,
    »morgen«) müssen „jetzt" aus der App-Uhr beziehen, nicht aus Modell-Annahme."""
    from app.core import clock

    when = clock.time_context()
    guard = build_scope_guard(purpose)
    if mode == "reminder":
        # KEIN Scope-Guard: Der Reminder wurde vom Nutzer bei der Einrichtung genehmigt;
        # zur Laufzeit gibt es niemanden zum Rückfragen. Ein enger Agenten-Zweck darf die
        # Zustellung NICHT als "off-topic" ablehnen — sonst kommt statt der Nachricht eine
        # Absage ("Dafür ist dieser Agent nicht gedacht.").
        ctx = (purpose or "").strip()
        ctx_line = f"Zur Einordnung — du bist: {ctx}\n\n" if ctx else ""
        return (
            when
            + ctx_line
            + "Dies ist eine vom Nutzer EINGERICHTETE, wiederkehrende Nachrichten-Aufgabe. "
            "Liefere als Antwort GENAU die gewünschte Nachricht als REINEN TEXT "
            "(kein HTML, kein Codeblock, keine Seite, keine STATUS-Zeile). "
            "KEINE Ablehnung, KEINE Rückfrage, KEINE Meta-Erklärung — gib direkt den "
            "Nachrichtentext aus für:\n\n"
            f"{instruction}"
        )
    return (
        when
        + guard
        + _SCHEDULE_CAPABILITY
        + "Hier ist die aktuelle Seite:\n\n"
        f"{current_page}\n\n"
        f"Anpassung: {instruction}\n\n"
        "Gib die KOMPLETTE aktualisierte Seite als zusammenhängenden Codeblock + STATUS-Zeile aus."
    )


async def _load_agent_purpose(db: AsyncSession, agent_id: UUID) -> str:
    """Zweck/erlaubte Aufgaben der Instanz = Rolle + System-Prompt des Agenten."""
    agent = await db.get(Agent, agent_id)
    if agent is None:
        return ""
    parts: list[str] = []
    if agent.role:
        parts.append(agent.role)
    if agent.current_version_id is not None:
        v = await db.get(AgentVersion, agent.current_version_id)
        if v and v.system_prompt:
            parts.append(v.system_prompt)
    return "\n".join(parts)


def _file_path(owner_id: UUID, artifact_id: UUID) -> str:
    folder = os.path.join(settings.media_root, "artifacts", str(owner_id))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{artifact_id}.html")


def _write_file(owner_id: UUID, artifact_id: UUID, content: str) -> str:
    path = _file_path(owner_id, artifact_id)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


async def create_instance(
    db: AsyncSession,
    *,
    owner_id: UUID,
    agent_id: UUID,
    title: str,
    output_type: str,
    template_id: UUID | None = None,
    inputs: dict | None = None,
    output_template: str = "",
    output_mode: str = "hinzufuegen",
) -> Artifact:
    """Legt IMMER eine neue Instanz (Kontext) an — kein Get-or-Create (Phase 5d)."""
    art = Artifact(
        owner_id=owner_id,
        agent_id=agent_id,
        template_id=template_id,
        inputs=inputs or {},
        title=title or "Artefakt",
        output_type=TemplateOutput(output_type),
        visibility=Visibility.PRIVATE,
        output_template=output_template,
        output_mode=output_mode,
    )
    db.add(art)
    await db.commit()
    await db.refresh(art)
    return art


async def record_version(
    db: AsyncSession,
    *,
    artifact_id: UUID,
    content: str,
    prompt: str,
    run_id: UUID | None,
    data: dict | None = None,
) -> ArtifactVersion | None:
    art = await db.get(Artifact, artifact_id)
    if art is None:
        return None
    count = len(
        (
            await db.execute(
                select(ArtifactVersion.id).where(ArtifactVersion.artifact_id == art.id)
            )
        ).all()
    )
    version = ArtifactVersion(
        artifact_id=art.id,
        version_no=count + 1,
        content=content,
        data=data,
        prompt=prompt,
        run_id=run_id,
    )
    db.add(version)
    await db.flush()
    art.current_version_id = version.id
    art.file_path = _file_path(art.owner_id, art.id)
    await db.commit()
    await db.refresh(version)
    # Datei NACH dem DB-Commit schreiben: die DB (artifact_versions.content) ist die
    # Quelle der Wahrheit; ein fehlgeschlagener Schreibvorgang lässt sich neu ableiten
    # und führt nicht zu einer Datei, die der DB voraus ist.
    _write_file(art.owner_id, art.id, content)
    return version


async def record_version_placed(
    db, *, artifact_id, content: str, prompt: str, run_id,
):
    """Schreibt die neue Ganzseiten-Ausgabe gemäß Artifact.output_mode fest (platziert
    sie als Abschnitt/Tab statt zu überschreiben, wenn ein Modus gesetzt ist)."""
    from app.services import output_placement
    art = await db.get(Artifact, artifact_id)
    if art is None:
        return None
    # Fallback = neuer Default (nach Migration 0032 hat keine Zeile mehr NULL/leer).
    mode = getattr(art, "output_mode", "hinzufuegen") or "hinzufuegen"
    if mode == "ueberschreiben":
        return await record_version(db, artifact_id=artifact_id, content=content,
                                    prompt=prompt, run_id=run_id)
    # aktuellen Inhalt + slots-data laden
    cur_content, cur_data = "", None
    if art.current_version_id is not None:
        v = await db.get(ArtifactVersion, art.current_version_id)
        if v is not None:
            cur_content, cur_data = (v.content or ""), v.data
    # design_id wie in canvas_slots._save
    design_id = ""
    if art.template_id is not None:
        tpl = await db.get(Template, art.template_id)
        design_id = (tpl.config or {}).get("html_template_id", "") if tpl else ""
    html, data = output_placement.apply(mode, current_data=cur_data,
                                        current_content=cur_content, new_output=content,
                                        design_id=design_id)
    return await record_version(db, artifact_id=artifact_id, content=html, prompt=prompt,
                                run_id=run_id, data=data)


async def get_version(db, artifact_id, owner_id, version_id):
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != owner_id:
        return None
    v = await db.get(ArtifactVersion, version_id)
    if v is None or v.artifact_id != artifact_id:
        return None
    return v


async def restore_version(db, artifact_id, owner_id, version_id):
    v = await get_version(db, artifact_id, owner_id, version_id)
    if v is None:
        return None
    # record_version committet bereits — kein zweites commit (sonst Ghost-Commit-Gefahr).
    return await record_version(db, artifact_id=artifact_id, content=v.content,
                                prompt=f"Wiederhergestellt v{v.version_no}", run_id=None,
                                data=v.data)


async def _versions(db: AsyncSession, artifact_id: UUID) -> list[ArtifactVersion]:
    stmt = (
        select(ArtifactVersion)
        .where(ArtifactVersion.artifact_id == artifact_id)
        .order_by(ArtifactVersion.version_no.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_view(
    db: AsyncSession, artifact_id: UUID, requester: User
) -> ArtifactView | None:
    art = await db.get(Artifact, artifact_id)
    if art is None:
        return None
    if art.owner_id != requester.id and art.visibility not in (
        Visibility.PUBLIC,
        Visibility.UNLISTED,
    ):
        return None
    versions = await _versions(db, art.id)
    current = next((v for v in versions if v.id == art.current_version_id), None)

    # Agent-/Vorlagen-Bild für den Chat-Dialog: Vorlage zuerst, sonst Agent-Avatar.
    icon: str | None = None
    if art.template_id is not None:
        tpl = await db.get(Template, art.template_id)
        icon = tpl.image_url if tpl else None
    if not icon:
        agent = await db.get(Agent, art.agent_id)
        icon = agent.avatar_url if agent else None

    art_jobs = []
    if art.owner_id == requester.id:
        art_jobs = await jobs_svc.list_for_artifact(db, art.id, requester.id) or []

    # Aufgelaufene Abrechnungskosten dieser Instanz (Charges sind negativ -> negieren).
    from decimal import Decimal

    from sqlalchemy import func

    from app.db.models import WalletLedger

    _spent = (await db.execute(
        select(func.coalesce(func.sum(WalletLedger.amount_usd), 0)).where(
            WalletLedger.artifact_id == art.id, WalletLedger.kind == "charge"
        )
    )).scalar_one()
    cost_total = -Decimal(_spent)

    publish_targets: list[str] = []
    content_mode: str = "html"
    html_template_id: str = ""
    if art.template_id is not None:
        tpl_cfg = await db.get(Template, art.template_id)
        if tpl_cfg is not None:
            publish_targets = (tpl_cfg.config or {}).get("publish_targets") or []
            content_mode = (tpl_cfg.config or {}).get("content_mode", "html")
            html_template_id = (tpl_cfg.config or {}).get("html_template_id", "")

    mcp_credentials: list[McpCredentialNeed] = []
    if art.template_id is not None and art.owner_id == requester.id:
        tpl_mcp = await db.get(Template, art.template_id)
        for sid in (tpl_mcp.config or {}).get("mcp_servers") or []:
            entry = await mcp_catalog.get(db, sid)
            if entry is None or not entry.enabled or not entry.requires_credential:
                continue
            conn = await conn_svc.get_connection(db, art.id, art.owner_id, f"mcp:{sid}")
            mcp_credentials.append(McpCredentialNeed(
                server_id=entry.server_id, name=entry.name,
                secret_label=entry.secret_label,
                configured=bool(conn and conn.secret_encrypted),
            ))

    # Externe Live-URL (WordPress): nach dem ersten Veröffentlichen kennen wir die
    # post_id → Beitrags-URL; vorher die Seiten-Startseite. Nur für den Eigentümer.
    external_url: str | None = None
    if art.owner_id == requester.id and "wordpress" in publish_targets:
        wp = await conn_svc.get_connection(db, art.id, art.owner_id, "wordpress")
        site = str((wp.config or {}).get("site_url", "")).rstrip("/") if wp else ""
        if site:
            pid = (wp.config or {}).get("post_id")
            external_url = f"{site}/?p={pid}" if pid else site

    # Bewertung des Agenten dieser Instanz: Aggregat + eigene Bewertung des Anfragenden.
    # Inline (ohne agents-Service-Import), um Import-Zyklen zu vermeiden.
    from app.db.models import Rating

    _ravg, _rcnt = (await db.execute(
        select(func.coalesce(func.avg(Rating.stars), 0), func.count(Rating.id))
        .where(Rating.agent_id == art.agent_id)
    )).first() or (0, 0)
    _mine = (await db.execute(
        select(Rating.stars).where(
            Rating.agent_id == art.agent_id, Rating.user_id == requester.id
        )
    )).scalar()

    from app.services import chains
    _chain_path = [ChainNode(**n) for n in await chains.chain_path(db, art.id)]

    return ArtifactView(
        id=art.id,
        owner_id=art.owner_id,
        agent_id=art.agent_id,
        template_id=art.template_id,
        inputs=art.inputs or {},
        title=art.title,
        output_type=art.output_type,
        visibility=art.visibility,
        image_url=icon,
        current_content=current.content if current else "",
        current_version_no=current.version_no if current else None,
        versions=[ArtifactVersionOut.model_validate(v) for v in versions],
        jobs=art_jobs,
        publish_targets=publish_targets,
        mcp_credentials=mcp_credentials,
        content_mode=content_mode,
        html_template_id=html_template_id,
        output_template=art.output_template or "",
        external_url=external_url,
        updated_at=art.updated_at,
        cost_total_usd=cost_total,
        is_owner=art.owner_id == requester.id,
        my_stars=int(_mine or 0),
        agent_rating_avg=float(_ravg or 0),
        agent_rating_count=int(_rcnt or 0),
        chain_next_id=art.next_artifact_id,
        chain_auto=art.chain_auto,
        chain_path=_chain_path,
        output_mode=art.output_mode,
    )


async def set_output_mode(db, artifact_id, owner_id, mode: str) -> str | None:
    from app.services import output_commands
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != owner_id:
        return None   # Aufrufer → 404 (fremd/fehlend nicht als Erfolg tarnen)
    art.output_mode = mode if output_commands.is_mode(mode) else "ueberschreiben"
    await db.commit()
    return art.output_mode


async def public_html(
    db: AsyncSession, artifact_id: UUID, viewer: User | None = None
) -> str | None:
    art = await db.get(Artifact, artifact_id)
    if art is None or art.current_version_id is None:
        return None
    vis = art.visibility
    if vis in (Visibility.PUBLIC, Visibility.UNLISTED):
        pass  # für jeden sichtbar
    elif vis == Visibility.FRIENDS:
        if viewer is None:
            return None
        if viewer.id != art.owner_id:
            from app.services import friends

            if not await friends.are_friends(db, art.owner_id, viewer.id):
                return None
    else:  # PRIVATE
        if viewer is None or viewer.id != art.owner_id:
            return None
    v = await db.get(ArtifactVersion, art.current_version_id)
    return v.content if v else None


async def master_page(
    db: AsyncSession, owner_id: UUID, viewer: User | None
) -> MasterPage | None:
    """Master-Seite eines Nutzers: alle Instanz-Ausgaben für einen Ergebnis-Viewer.

    Der Eigentümer sieht ALLE seine Instanzen (inkl. PRIVATE/FRIENDS); Fremde/anonyme
    Betrachter nur PUBLIC/UNLISTED. Nur Instanzen mit einer aktuellen Version werden
    geliefert (sonst gibt es kein Ergebnis zu zeigen). Sortierung: updated_at desc.
    """
    owner = await db.get(User, owner_id)
    if owner is None:
        return None
    is_owner = viewer is not None and viewer.id == owner_id

    stmt = (
        select(Artifact)
        .where(
            Artifact.owner_id == owner_id,
            Artifact.current_version_id.is_not(None),
        )
        .order_by(Artifact.updated_at.desc())
    )
    if not is_owner:
        stmt = stmt.where(
            Artifact.visibility.in_((Visibility.PUBLIC, Visibility.UNLISTED))
        )
    arts = list((await db.execute(stmt)).scalars().all())

    # Instanzen mit mindestens einer aktiven zeitgesteuerten Aufgabe (für das Uhr-Icon).
    scheduled_ids: set[UUID] = set()
    if arts:
        from app.db.models import ArtifactJob
        rows = (await db.execute(
            select(ArtifactJob.artifact_id).where(
                ArtifactJob.artifact_id.in_([a.id for a in arts]),
                ArtifactJob.status == "active",
            )
        )).scalars().all()
        scheduled_ids = {r for r in rows if r}

    instances: list[MasterInstance] = []
    for art in arts:
        cur = await db.get(ArtifactVersion, art.current_version_id)
        if cur is None:
            continue
        # Icon: Vorlage zuerst, sonst Agent-Avatar (wie get_view).
        icon: str | None = None
        if art.template_id is not None:
            tpl = await db.get(Template, art.template_id)
            icon = tpl.image_url if tpl else None
        if not icon:
            agent = await db.get(Agent, art.agent_id)
            icon = agent.avatar_url if agent else None
        instances.append(
            MasterInstance(
                id=art.id,
                title=art.title,
                image_url=icon,
                updated_at=art.updated_at,
                html=cur.content or "",
                scheduled=art.id in scheduled_ids,
            )
        )

    return MasterPage(
        owner_id=owner.id,
        owner_name=owner.name,
        is_owner=is_owner,
        instances=instances,
    )


async def list_mine(db: AsyncSession, user: User) -> list[ArtifactListItem]:
    stmt = (
        select(Artifact).where(Artifact.owner_id == user.id).order_by(Artifact.updated_at.desc())
    )
    arts = list((await db.execute(stmt)).scalars().all())

    # Aktiver wiederkehrender Job liefert das Cadence-Badge; offene Jobs den Zähler.
    job_rows = (
        await db.execute(
            select(ArtifactJob.artifact_id, ArtifactJob.cadence).where(
                ArtifactJob.owner_id == user.id,
                ArtifactJob.status == "active",
                ArtifactJob.trigger_kind == "recurring",
            )
        )
    ).all()
    cadence_by_artifact = {aid: cad for aid, cad in job_rows if cad}
    job_count_by_artifact = await jobs_svc.active_counts(db, user.id)

    # Vorlagen-Bilder gebündelt (für das Instanz-Icon im Dashboard).
    tpl_ids = {art.template_id for art in arts if art.template_id is not None}
    tpl_image: dict[UUID, str | None] = {}
    if tpl_ids:
        trows = (
            await db.execute(
                select(Template.id, Template.image_url).where(Template.id.in_(tpl_ids))
            )
        ).all()
        tpl_image = {tid: img for tid, img in trows}

    out: list[ArtifactListItem] = []
    for art in arts:
        cur = (
            await db.get(ArtifactVersion, art.current_version_id)
            if art.current_version_id
            else None
        )
        # Modell/Provider des Agenten der Instanz + ob der eigene Key greift.
        model: str | None = None
        uses_own_key = False
        agent = await db.get(Agent, art.agent_id)
        if agent and agent.current_version_id:
            av = await db.get(AgentVersion, agent.current_version_id)
            if av:
                model = av.model
                provider = av.provider
                if provider == "anthropic":
                    uses_own_key = bool(user.anthropic_key_encrypted)
                elif provider == "openai":
                    uses_own_key = bool(user.openai_key_encrypted)
        icon = tpl_image.get(art.template_id) if art.template_id else None
        if not icon:
            icon = agent.avatar_url if agent else None
        recent = (
            await db.execute(
                select(ArtifactVersion.prompt, ArtifactVersion.created_at)
                .where(ArtifactVersion.artifact_id == art.id)
                .order_by(ArtifactVersion.created_at.desc())
                .limit(3)
            )
        ).all()
        recent_actions = [
            RecentAction(prompt=p or "", created_at=c) for p, c in recent if (p or "").strip()
        ]
        out.append(
            ArtifactListItem(
                id=art.id,
                owner_id=art.owner_id,
                agent_id=art.agent_id,
                template_id=art.template_id,
                inputs=art.inputs or {},
                title=art.title,
                agent_name=(agent.name if agent else ""),
                visibility=art.visibility,
                image_url=icon,
                current_version_no=cur.version_no if cur else None,
                preview_html=(cur.content or None) if cur else None,
                updated_at=art.updated_at,
                schedule_cadence=cadence_by_artifact.get(art.id),
                job_count=job_count_by_artifact.get(art.id, 0),
                recent_actions=recent_actions,
                model=model,
                uses_own_key=uses_own_key,
            )
        )
    return out


async def adjust(
    db: AsyncSession,
    artifact_id: UUID,
    requester_id: UUID,
    instruction: str,
    *,
    notify_owner: bool = False,
    notify_chat: bool = False,
    mode: str = "update",
) -> UUID | None:
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != requester_id:
        return None
    current = ""
    if art.current_version_id is not None:
        v = await db.get(ArtifactVersion, art.current_version_id)
        current = v.content if v else ""

    purpose = await _load_agent_purpose(db, art.agent_id)
    initial = build_adjust_initial(mode, purpose, current, instruction)
    requester = await db.get(User, requester_id)
    if requester is None:
        return None
    payload = WorkCreate(
        title=art.title,
        goal=instruction,
        expected_outcome="",
        initial_message=initial,
        mode="single",
        visibility=Visibility.PRIVATE,
        agents=[{"agent_id": art.agent_id, "role_in_work": ""}],
    )
    work = await work_svc.create_work(db, requester, payload)
    work_orm = await db.get(Work, work.id)
    work_orm.loop_config = {
        "enabled": True,
        "max_iterations": 1 if mode == "reminder" else _ADJUST_MAX_ITERATIONS,
        "job_mode": mode,
        "max_cost_usd": _ADJUST_MAX_COST,
        "output_type": art.output_type.value,
        "success_criteria": None,
        # Ziel-Instanz: der Worker schreibt die neue Version in genau dieses Artefakt.
        "artifact_id": str(art.id),
        # Bei geplanten Updates: Eigentümer nach der neuen Version benachrichtigen.
        "notify_owner": notify_owner,
        # Phase 2c: nach der neuen Version zusätzlich einen Eintrag in den Instanz-Chat schreiben.
        "notify_chat": notify_chat,
    }
    await db.commit()

    run = await run_svc.create_run(db, work.id, requester_id)
    if run is None:
        raise RuntimeError(f"run creation failed for work {work.id}")
    from app.workers import execute_run

    execute_run.send(str(run.id))
    return run.id


async def delete_artifact(db: AsyncSession, artifact_id: UUID, requester: User) -> bool:
    """Löscht eine Instanz samt abhängiger Zeilen. Nur der Eigentümer darf löschen.

    Versionen/Jobs/Messages/Dateien hängen per ON DELETE CASCADE an `artifacts`; der alte
    `artifact_schedules`-Eintrag (falls vorhanden) ebenfalls. Daher genügt das Löschen
    des Artefakt-Rows — zusätzlich wird der Datei-Ordner auf der Platte best-effort entfernt.
    """
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != requester.id:
        return False
    import shutil

    folder = os.path.join(
        settings.media_root, "artifacts", str(art.owner_id), str(art.id)
    )
    shutil.rmtree(folder, ignore_errors=True)
    await db.delete(art)
    await db.commit()
    return True
