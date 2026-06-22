"""Agent-Verkettung: eine Instanz feuert die nächste mit ihrem (verdichteten) Output."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Agent, Artifact, ArtifactVersion, Template
from app.services import artifacts as artifacts_svc
from app.services import chat_summary

MAX_CHAIN_HOPS = 20
OUTPUT_CAP = 12_000
SUMMARIZE_THRESHOLD = 1_500


async def _walk_forward_reaches(db: AsyncSession, start_id: UUID, target_id: UUID) -> bool:
    """True, wenn der Vorwärts-Pfad ab `target_id` `start_id` erreicht (würde einen Zyklus
    schließen). Kein Hop-Limit — das `seen`-Set garantiert Terminierung auch bei einem
    (theoretisch) schon vorhandenen Zyklus, sodass auch lange Ketten korrekt geprüft werden."""
    cur: UUID | None = target_id
    seen: set[UUID] = set()
    while cur is not None:
        if cur == start_id:
            return True
        if cur in seen:
            return False
        seen.add(cur)
        art = await db.get(Artifact, cur)
        cur = art.next_artifact_id if art else None
    return False


async def set_chain(db: AsyncSession, artifact_id: UUID, owner_id: UUID, *,
                    next_id: UUID | None, auto: bool) -> tuple[bool, str]:
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != owner_id:
        return (False, "forbidden")
    if next_id is not None:
        if next_id == artifact_id:
            return (False, "self")
        nxt = await db.get(Artifact, next_id)
        if nxt is None or nxt.owner_id != owner_id:
            return (False, "foreign")
        if await _walk_forward_reaches(db, artifact_id, next_id):
            return (False, "cycle")
    art.next_artifact_id = next_id
    art.chain_auto = auto
    await db.commit()
    return (True, "")


async def _node_icon(db: AsyncSession, art: Artifact) -> str | None:
    if art.template_id is not None:
        tpl = await db.get(Template, art.template_id)
        if tpl and tpl.image_url:
            return tpl.image_url
    agent = await db.get(Agent, art.agent_id)
    return agent.avatar_url if agent else None


async def chain_path(db: AsyncSession, artifact_id: UUID,
                     max_hops: int = MAX_CHAIN_HOPS) -> list[dict]:
    art = await db.get(Artifact, artifact_id)
    if art is None:
        return []
    head = art
    seen = {head.id}
    for _ in range(max_hops):
        pred = (await db.execute(
            select(Artifact).where(Artifact.next_artifact_id == head.id,
                                   Artifact.owner_id == art.owner_id))).scalars().first()
        if pred is None or pred.id in seen:
            break
        head = pred; seen.add(head.id)
    out: list[dict] = []
    cur: Artifact | None = head
    walked = {head.id}
    for _ in range(max_hops):
        if cur is None:
            break
        out.append({"id": cur.id, "title": cur.title,
                    "image_url": await _node_icon(db, cur),
                    "is_self": cur.id == artifact_id})
        nxt_id = cur.next_artifact_id
        if nxt_id is None or nxt_id in walked:
            break
        walked.add(nxt_id)
        cur = await db.get(Artifact, nxt_id)
    return out


async def forward(db: AsyncSession, source_artifact_id: UUID) -> UUID | None:
    src = await db.get(Artifact, source_artifact_id)
    if src is None or src.next_artifact_id is None:
        return None
    content = ""
    if src.current_version_id is not None:
        v = await db.get(ArtifactVersion, src.current_version_id)
        content = (v.content or "") if v else ""
    if not content:
        payload = ""
    elif len(content) <= SUMMARIZE_THRESHOLD:
        payload = content
    else:
        payload = await chat_summary.summarize_output(src.title, content[:OUTPUT_CAP]) \
                  or content[:OUTPUT_CAP]
    if payload:
        instruction = (f"Eingabe von »{src.title}« (vorheriger Agent in der Kette):\n\n"
                       f"{payload}\n\nVerarbeite diese Eingabe gemäß deiner Aufgabe und "
                       f"aktualisiere deine Seite.")
    else:
        instruction = (f"Der vorherige Agent »{src.title}« hat keinen Inhalt geliefert. "
                       f"Aktualisiere deine Seite gemäß deiner Aufgabe.")
    return await artifacts_svc.adjust(db, src.next_artifact_id, src.owner_id, instruction,
                                      notify_owner=True, notify_chat=True)
