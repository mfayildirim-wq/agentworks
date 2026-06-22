from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_runtime.pricing import cost as cost_fn

from app.db.models import (
    Agent,
    AgentVersion,
    User,
    Visibility,
    Work,
    WorkAgent,
)
from app.schemas.works import WorkCreate, WorkOut, WorkAgentOut


async def create_work(db: AsyncSession, user: User, payload: WorkCreate) -> WorkOut:
    work = Work(
        owner_id=user.id,
        title=payload.title,
        goal=payload.goal,
        expected_outcome=payload.expected_outcome,
        initial_message=payload.initial_message,
        mode=payload.mode,
        visibility=payload.visibility,
        max_turns=payload.max_turns,
        max_tokens=payload.max_tokens,
    )
    db.add(work)
    await db.flush()
    for idx, wa in enumerate(payload.agents):
        agent = await db.get(Agent, wa.agent_id)
        if agent is None:
            raise ValueError(f"agent {wa.agent_id} not found")
        if agent.visibility in (Visibility.PRIVATE, Visibility.DRAFT) and agent.owner_id != user.id:
            raise PermissionError(f"agent {wa.agent_id} not accessible")
        db.add(
            WorkAgent(
                work_id=work.id,
                agent_id=agent.id,
                agent_version_id=agent.current_version_id,
                role_in_work=wa.role_in_work,
                handoff_targets=[str(t) for t in wa.handoff_targets],
                order_idx=idx,
            )
        )
    await db.commit()
    return (await get_work(db, work.id, user))  # type: ignore[return-value]


async def get_work(db: AsyncSession, work_id: UUID, user: User) -> WorkOut | None:
    stmt = (
        select(Work)
        .options(selectinload(Work.work_agents))
        .where(Work.id == work_id)
    )
    work = (await db.execute(stmt)).scalar_one_or_none()
    if work is None:
        return None
    if work.visibility in (Visibility.PRIVATE, Visibility.DRAFT) and work.owner_id != user.id:
        return None
    return await _to_out(db, work)


async def list_works(
    db: AsyncSession,
    user: User,
    *,
    mine: bool = False,
    public_only: bool = False,
) -> list[WorkOut]:
    stmt = select(Work).options(selectinload(Work.work_agents))
    if mine:
        stmt = stmt.where(Work.owner_id == user.id)
    elif public_only:
        stmt = stmt.where(Work.visibility == Visibility.PUBLIC)
    else:
        stmt = stmt.where(
            or_(Work.visibility == Visibility.PUBLIC, Work.owner_id == user.id)
        )
    stmt = stmt.order_by(Work.created_at.desc())
    works = (await db.execute(stmt)).scalars().unique().all()
    return [await _to_out(db, w) for w in works]


async def copy_work(db: AsyncSession, work_id: UUID, user: User) -> WorkOut | None:
    src = await get_work(db, work_id, user)
    if src is None:
        return None
    payload = WorkCreate(
        title=f"Copy: {src.title}",
        goal=src.goal,
        expected_outcome=src.expected_outcome,
        initial_message=src.initial_message,
        mode=src.mode,
        visibility=Visibility.PRIVATE,
        max_turns=src.max_turns,
        max_tokens=src.max_tokens,
        agents=[
            {
                "agent_id": wa.agent_id,
                "role_in_work": wa.role_in_work,
                "handoff_targets": wa.handoff_targets,
            }
            for wa in src.agents
        ],
    )
    return await create_work(db, user, payload)


async def _to_out(db: AsyncSession, work: Work) -> WorkOut:
    # Lade Agent-Namen + Modelle
    agent_ids = [wa.agent_id for wa in work.work_agents]
    agents_map: dict[UUID, tuple[str, str]] = {}
    estimated = 0.0
    if agent_ids:
        stmt = (
            select(Agent, AgentVersion)
            .join(AgentVersion, AgentVersion.id == Agent.current_version_id)
            .where(Agent.id.in_(agent_ids))
        )
        for agent, version in (await db.execute(stmt)).all():
            agents_map[agent.id] = (agent.name, version.model)
            # Heuristik: 2k tokens-in + 1k tokens-out pro Agent
            estimated += cost_fn(version.model, 2_000, 1_000)

    return WorkOut(
        id=work.id,
        owner_id=work.owner_id,
        title=work.title,
        goal=work.goal,
        expected_outcome=work.expected_outcome,
        initial_message=work.initial_message,
        mode=work.mode,
        visibility=work.visibility,
        max_turns=work.max_turns,
        max_tokens=work.max_tokens,
        estimated_cost_usd=round(estimated, 4),
        agents=[
            WorkAgentOut(
                agent_id=wa.agent_id,
                role_in_work=wa.role_in_work,
                handoff_targets=[UUID(t) for t in (wa.handoff_targets or [])],
                name=agents_map.get(wa.agent_id, ("?", "?"))[0],
                model=agents_map.get(wa.agent_id, ("?", "?"))[1],
            )
            for wa in sorted(work.work_agents, key=lambda x: x.order_idx)
        ],
        created_at=work.created_at,
        updated_at=work.updated_at,
    )


async def can_access_work(db: AsyncSession, work_id: UUID, user: User) -> Work | None:
    work = await db.get(Work, work_id)
    if work is None:
        return None
    if work.visibility in (Visibility.PRIVATE, Visibility.DRAFT) and work.owner_id != user.id:
        return None
    return work
