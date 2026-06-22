from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_runtime.spec import AgentSpec, LoopConfig, RunMode, WorkSpec

from app.core import crypto
from app.core.settings import get_settings
from app.db.models import (
    Agent,
    AgentVersion,
    Message,
    RunStatus,
    User,
    Visibility,
    Work,
    WorkRun,
)

settings = get_settings()


async def create_run(db: AsyncSession, work_id: UUID, user_id: UUID) -> WorkRun | None:
    work = await db.get(Work, work_id)
    if work is None:
        return None
    if work.visibility in (Visibility.PRIVATE, Visibility.DRAFT) and work.owner_id != user_id:
        return None
    run = WorkRun(work_id=work_id, status=RunStatus.PENDING)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def build_work_spec(db: AsyncSession, run_id: UUID) -> WorkSpec:
    run = await db.get(WorkRun, run_id)
    if run is None:
        raise LookupError(f"run {run_id} not found")
    stmt = (
        select(Work)
        .options(selectinload(Work.work_agents))
        .where(Work.id == run.work_id)
    )
    work = (await db.execute(stmt)).scalar_one()
    owner = await db.get(User, work.owner_id)

    agent_ids = [wa.agent_id for wa in sorted(work.work_agents, key=lambda x: x.order_idx)]
    agent_rows = (await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))).scalars().all()
    by_id_agent = {a.id: a for a in agent_rows}
    version_ids = [wa.agent_version_id for wa in work.work_agents if wa.agent_version_id]
    version_rows = (
        (await db.execute(select(AgentVersion).where(AgentVersion.id.in_(version_ids))))
        .scalars()
        .all()
    )
    by_id_version = {v.id: v for v in version_rows}

    from app.services import model_pricing
    from app.services import rag as rag_svc
    from app.services import system_keys

    specs: list[AgentSpec] = []
    for wa in sorted(work.work_agents, key=lambda x: x.order_idx):
        a = by_id_agent[wa.agent_id]
        v = by_id_version.get(wa.agent_version_id) if wa.agent_version_id else None
        if v is None:
            v_rows = (
                (await db.execute(select(AgentVersion).where(AgentVersion.agent_id == a.id)))
                .scalars()
                .all()
            )
            v = max(v_rows, key=lambda x: x.version) if v_rows else None
        if v is None:
            raise ValueError(f"agent {a.id} has no version")

        retrieved = await rag_svc.retrieve(db, a.id, work.goal or work.title, k=4)
        system_prompt = v.system_prompt
        if retrieved:
            system_prompt = (
                v.system_prompt
                + "\n\n## Wissenskontext (RAG)\n"
                + "\n---\n".join(retrieved)
            )

        # Provider aus dem Modell ableiten (Modell = Wahrheitsquelle) — kein Fehlrouting
        # bei veraltetem provider-Feld (z.B. "ollama" + Cloud-Modell).
        prov = await model_pricing.provider_for(db, v.model) or getattr(v, "provider", "anthropic")
        # Instanz-Läufe laufen über den System-Key (DB-GOA, .env-Fallback);
        # ein agent-eigener Key (Template-Autor) hat weiter Vorrang.
        api_key = (
            crypto.decrypt(a.api_key_encrypted)
            if a.api_key_encrypted
            else await system_keys.system_key_for(db, prov)
        )
        specs.append(
            AgentSpec(
                id=a.id,
                name=a.name,
                description=a.description,
                role=a.role,
                system_prompt=system_prompt,
                model=v.model,
                provider=prov,
                api_key=api_key,
                temperature=v.temperature,
                tools=v.tools or [],
                handoff_targets=[UUID(t) for t in (wa.handoff_targets or [])],
            )
        )

    loop = None
    if work.loop_config and work.loop_config.get("enabled"):
        loop = LoopConfig(
            enabled=True,
            max_iterations=work.loop_config.get("max_iterations", 8),
            max_cost_usd=work.loop_config.get("max_cost_usd", 1.0),
            output_type=work.loop_config.get("output_type", "html"),
            success_criteria=work.loop_config.get("success_criteria"),
        )

    return WorkSpec(
        id=work.id,
        run_id=run.id,
        title=work.title,
        goal=work.goal,
        expected_outcome=work.expected_outcome,
        mode=RunMode(work.mode.value),
        agents=specs,
        initial_message=work.initial_message or work.goal,
        max_turns=work.max_turns,
        max_tokens=work.max_tokens,
        metadata={"workflow_graph": work.workflow_graph or {}},
        loop=loop,
    )


async def list_messages(db: AsyncSession, run_id: UUID) -> list[Message]:
    stmt = select(Message).where(Message.run_id == run_id).order_by(Message.ts.asc())
    return list((await db.execute(stmt)).scalars().all())
