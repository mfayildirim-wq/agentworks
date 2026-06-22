"""Seed-Script: legt Demo-User + 6 Beispiel-Agenten + ein Beispiel-Work an.

Verwendung: `python -m scripts.seed` (im backend/ Verzeichnis, .venv aktiv)
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.models import (
    Agent,
    AgentSkill,
    AgentVersion,
    User,
    Visibility,
)
from app.db.session import SessionLocal


DEMO_AGENTS = [
    {
        "name": "Business-Ideen-Agent",
        "domain": "business",
        "role": "Ideengeber",
        "description": "Generiert validierbare Geschäftsideen anhand von Markt-Inputs.",
        "system_prompt": "Du erzeugst 3 konkrete Geschäftsideen mit Zielgruppe, Pain-Point und MVP-Pfad.",
        "skills": ["ideation", "business", "strategy"],
        "model": "claude-sonnet-4-6",
    },
    {
        "name": "Research-Agent",
        "domain": "research",
        "role": "Recherche",
        "description": "Recherchiert Quellen und fasst zusammen.",
        "system_prompt": "Du recherchierst gewissenhaft. Gib Quellen an.",
        "skills": ["research", "summarization"],
        "model": "claude-sonnet-4-6",
    },
    {
        "name": "Kritiker-Agent",
        "domain": "quality",
        "role": "Kritiker",
        "description": "Spielt Advocatus Diaboli und deckt Schwächen auf.",
        "system_prompt": "Du suchst maximal kritisch Schwächen, Annahmen und Risiken.",
        "skills": ["critique", "risk"],
        "model": "claude-sonnet-4-6",
    },
    {
        "name": "SEO-Agent",
        "domain": "marketing",
        "role": "SEO",
        "description": "Optimiert Texte und Strukturen für Suchmaschinen.",
        "system_prompt": "Du optimierst Inhalte SEO-konform.",
        "skills": ["seo", "content"],
        "model": "claude-haiku-4-5",
    },
    {
        "name": "Code-Review-Agent",
        "domain": "software",
        "role": "Reviewer",
        "description": "Reviewt Diffs auf Bugs und Style.",
        "system_prompt": "Du prüfst Code auf Bugs, Tests, Lesbarkeit.",
        "skills": ["code-review", "security"],
        "model": "claude-sonnet-4-6",
    },
    {
        "name": "Finanz-Agent",
        "domain": "finance",
        "role": "Finanzanalyst",
        "description": "Erstellt einfache Finanzpläne und Pricing-Modelle.",
        "system_prompt": "Du baust einfache Finanzmodelle in Markdown-Tabellen.",
        "skills": ["finance", "pricing"],
        "model": "claude-sonnet-4-6",
    },
]


async def run() -> None:
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.google_sub == "demo"))).scalar_one_or_none()
        if user is None:
            user = User(google_sub="demo", email="demo@agentworks.local", name="Demo User")
            db.add(user)
            await db.flush()

        for spec in DEMO_AGENTS:
            existing = (
                await db.execute(
                    select(Agent).where(Agent.owner_id == user.id, Agent.name == spec["name"])
                )
            ).scalar_one_or_none()
            if existing:
                continue
            agent = Agent(
                owner_id=user.id,
                name=spec["name"],
                description=spec["description"],
                role=spec["role"],
                domain=spec["domain"],
                visibility=Visibility.PUBLIC,
                price_per_run=0.5,
            )
            db.add(agent)
            await db.flush()
            v = AgentVersion(
                agent_id=agent.id,
                system_prompt=spec["system_prompt"],
                model=spec["model"],
            )
            db.add(v)
            await db.flush()
            agent.current_version_id = v.id
            for s in spec["skills"]:
                db.add(AgentSkill(agent_id=agent.id, skill=s))
        await db.commit()
        print(f"Seeded {len(DEMO_AGENTS)} agents for user {user.email}")


if __name__ == "__main__":
    asyncio.run(run())
