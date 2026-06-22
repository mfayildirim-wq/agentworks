from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import crypto
from app.db.models import Agent, AgentSkill, AgentVersion, Rating, User, Visibility, Work, WorkAgent
from app.schemas.agents import AgentCreate, AgentOut, AgentUpdate, AgentWorkRef
from app.services import roles


def compose_system_prompt(
    role: str, domain: str, skills: list[str], description: str
) -> str:
    """Erzeugt deterministisch einen System-Prompt aus Profil-Bausteinen."""
    who = role.strip() or "ein hilfreicher Agent"
    parts: list[str] = []
    if domain.strip():
        parts.append(f"Du bist {who} im Bereich {domain.strip()}.")
    else:
        parts.append(f"Du bist {who}.")
    if skills:
        parts.append("Deine Fähigkeiten: " + ", ".join(skills) + ".")
    if description.strip():
        parts.append(description.strip())
    parts.append(
        "Arbeite fokussiert und nutze deine Fähigkeiten, um die Aufgabe bestmöglich zu erfüllen."
    )
    return " ".join(parts)


async def list_agents(
    db: AsyncSession,
    user: User,
    *,
    query: str | None = None,
    skill: str | None = None,
    domain: str | None = None,
    model: str | None = None,
    mine: bool = False,
) -> list[AgentOut]:
    stmt = select(Agent).options(
        selectinload(Agent.skills), selectinload(Agent.versions)
    )
    conds = []
    if mine:
        conds.append(Agent.owner_id == user.id)
    else:
        conds.append(or_(Agent.visibility == Visibility.PUBLIC, Agent.owner_id == user.id))
    if query:
        like = f"%{query.lower()}%"
        conds.append(
            or_(
                func.lower(Agent.name).like(like),
                func.lower(Agent.role).like(like),
                func.lower(Agent.description).like(like),
            )
        )
    stmt = stmt.where(and_(*conds)).order_by(Agent.created_at.desc())
    result = await db.execute(stmt)
    agents = list(result.scalars().unique())

    if model:
        agents = [
            a for a in agents if _current_version(a) and _current_version(a).model == model
        ]

    ratings = await _ratings_map(db, [a.id for a in agents])
    return [_to_out(a, ratings) for a in agents]


async def get_agent(db: AsyncSession, agent_id: UUID, user: User) -> AgentOut | None:
    # populate_existing: mit expire_on_commit=False würde sonst nach einem Update
    # das gecachte Agent-Objekt (alte skills/versions) zurückkommen.
    stmt = (
        select(Agent)
        .options(selectinload(Agent.skills), selectinload(Agent.versions))
        .where(Agent.id == agent_id)
        .execution_options(populate_existing=True)
    )
    agent = (await db.execute(stmt)).scalar_one_or_none()
    if agent is None:
        return None
    if agent.visibility in (Visibility.PRIVATE, Visibility.DRAFT) and agent.owner_id != user.id:
        return None
    ratings = await _ratings_map(db, [agent.id])
    return _to_out(agent, ratings)


async def create_agent(db: AsyncSession, user: User, payload: AgentCreate) -> AgentOut:
    agent = Agent(
        owner_id=user.id,
        name=payload.name,
        description=payload.description,
        role=payload.role,
        domain=payload.domain,
        avatar_url=payload.avatar_url,
        visibility=roles.effective_visibility(user, payload.visibility),
        price_per_run=payload.price_per_run,
        api_key_encrypted=crypto.encrypt(payload.api_key) if payload.api_key else None,
    )
    db.add(agent)
    await db.flush()
    skills_clean = list(dict.fromkeys(payload.skills))
    system_prompt = payload.system_prompt or compose_system_prompt(
        payload.role, payload.domain, skills_clean, payload.description
    )
    version = AgentVersion(
        agent_id=agent.id,
        version=1,
        system_prompt=system_prompt,
        model=payload.model,
        provider=payload.provider,
        temperature=payload.temperature,
        tools=payload.tools,
    )
    db.add(version)
    await db.flush()
    agent.current_version_id = version.id
    for skill in skills_clean:
        db.add(AgentSkill(agent_id=agent.id, skill=skill))
    await db.commit()
    return (await get_agent(db, agent.id, user))  # type: ignore[return-value]


async def update_agent(
    db: AsyncSession, agent_id: UUID, user: User, payload: AgentUpdate
) -> AgentOut | None:
    stmt = select(Agent).options(
        selectinload(Agent.skills), selectinload(Agent.versions)
    ).where(Agent.id == agent_id)
    agent = (await db.execute(stmt)).scalar_one_or_none()
    if agent is None or agent.owner_id != user.id:
        return None

    for field in ("description", "role", "domain", "price_per_run", "avatar_url"):
        value = getattr(payload, field)
        if value is not None:
            setattr(agent, field, value)
    # Sichtbarkeit gegated: normale User dürfen einen Agenten nicht öffentlich machen.
    if payload.visibility is not None:
        agent.visibility = roles.effective_visibility(user, payload.visibility)

    if payload.api_key is not None:
        agent.api_key_encrypted = crypto.encrypt(payload.api_key) if payload.api_key else None

    profile_changed = any(
        getattr(payload, f) is not None for f in ("system_prompt", "role", "domain", "description")
    ) or payload.skills is not None
    needs_new_version = profile_changed or any(
        getattr(payload, f) is not None for f in ("model", "temperature", "tools", "provider")
    )
    if needs_new_version:
        current = _current_version(agent)
        eff_skills = (
            list(dict.fromkeys(payload.skills))
            if payload.skills is not None
            else sorted(s.skill for s in agent.skills)
        )
        gen_prompt = compose_system_prompt(
            agent.role, agent.domain, eff_skills, agent.description
        )
        new = AgentVersion(
            agent_id=agent.id,
            version=(current.version + 1) if current else 1,
            system_prompt=payload.system_prompt or gen_prompt,
            model=payload.model or (current.model if current else "claude-haiku-4-5"),
            provider=payload.provider or (current.provider if current else "anthropic"),
            temperature=payload.temperature
            if payload.temperature is not None
            else (current.temperature if current else 0.7),
            tools=payload.tools
            if payload.tools is not None
            else (current.tools if current else []),
        )
        db.add(new)
        await db.flush()
        agent.current_version_id = new.id

    if payload.skills is not None:
        await db.execute(
            AgentSkill.__table__.delete().where(AgentSkill.agent_id == agent.id)
        )
        for skill in dict.fromkeys(payload.skills):
            db.add(AgentSkill(agent_id=agent.id, skill=skill))

    await db.commit()
    return await get_agent(db, agent.id, user)


async def delete_agent(db: AsyncSession, agent_id: UUID, user: User) -> bool:
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.owner_id != user.id:
        return False
    await db.delete(agent)
    await db.commit()
    return True


def _current_version(agent: Agent) -> AgentVersion | None:
    if not agent.versions:
        return None
    if agent.current_version_id:
        for v in agent.versions:
            if v.id == agent.current_version_id:
                return v
    return max(agent.versions, key=lambda v: v.version)


async def _ratings_map(db: AsyncSession, agent_ids: list[UUID]) -> dict[UUID, tuple[float, int]]:
    if not agent_ids:
        return {}
    stmt = (
        select(Rating.agent_id, func.avg(Rating.stars), func.count(Rating.id))
        .where(Rating.agent_id.in_(agent_ids))
        .group_by(Rating.agent_id)
    )
    return {
        row[0]: (float(row[1] or 0), int(row[2] or 0))
        for row in (await db.execute(stmt)).all()
    }


async def rate_agent(db, agent_id, user_id, stars: int, comment: str = "") -> Rating | None:
    if not (1 <= int(stars) <= 5):
        return None
    # Nur wer eine Instanz dieses Agenten besitzt, darf ihn bewerten (kein Drive-by-Rating).
    from app.db.models import Artifact

    owns = (await db.execute(
        select(Artifact.id).where(
            Artifact.agent_id == agent_id, Artifact.owner_id == user_id
        ).limit(1)
    )).first()
    if owns is None:
        return None
    existing = (await db.execute(select(Rating).where(
        Rating.agent_id == agent_id, Rating.user_id == user_id))).scalars().first()
    if existing is not None:
        existing.stars = int(stars); existing.comment = comment or ""
        await db.commit(); await db.refresh(existing); return existing
    r = Rating(agent_id=agent_id, user_id=user_id, stars=int(stars), comment=comment or "")
    db.add(r); await db.commit(); await db.refresh(r); return r


async def list_reviews(db, agent_id, limit: int = 50) -> list[dict]:
    rows = (await db.execute(
        select(Rating.stars, Rating.comment, Rating.created_at, User.name)
        .join(User, Rating.user_id == User.id)
        .where(Rating.agent_id == agent_id,
               func.length(func.trim(Rating.comment)) > 0)
        .order_by(Rating.created_at.desc()).limit(limit))).all()
    return [{"stars": s, "comment": c, "created_at": ts, "user_name": (n or "Nutzer")}
            for s, c, ts, n in rows]


async def list_agent_works(
    db: AsyncSession, agent_id: UUID, user: User
) -> list[AgentWorkRef]:
    stmt = (
        select(Work.id, Work.title, Work.image_url)
        .join(WorkAgent, WorkAgent.work_id == Work.id)
        .where(WorkAgent.agent_id == agent_id)
        .where(or_(Work.visibility == Visibility.PUBLIC, Work.owner_id == user.id))
        .order_by(Work.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [AgentWorkRef(id=r[0], title=r[1], image_url=r[2]) for r in rows]


def _to_out(agent: Agent, ratings: dict[UUID, tuple[float, int]]) -> AgentOut:
    v = _current_version(agent)
    avg, cnt = ratings.get(agent.id, (0.0, 0))
    return AgentOut(
        id=agent.id,
        owner_id=agent.owner_id,
        name=agent.name,
        description=agent.description,
        role=agent.role,
        domain=agent.domain,
        avatar_url=agent.avatar_url,
        visibility=agent.visibility,
        price_per_run=agent.price_per_run,
        model=v.model if v else "claude-haiku-4-5",
        provider=v.provider if v else "anthropic",
        has_api_key=bool(agent.api_key_encrypted),
        temperature=v.temperature if v else 0.7,
        system_prompt=v.system_prompt if v else "",
        tools=v.tools if v else [],
        skills=sorted(s.skill for s in agent.skills),
        rating_avg=avg,
        rating_count=cnt,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )
