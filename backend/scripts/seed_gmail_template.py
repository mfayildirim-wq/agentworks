"""Seed: öffentliches Template „Gmail" (OAuth-Verbindung pro Instanz).

Legt idempotent ein öffentliches Template (Besitzer GOA) an, das pro Instanz eine
Gmail-OAuth-Verbindung nutzt und die nativen Tools `gmail_search`/`gmail_send`
über `publish_targets=["gmail"]` erhält. Muster wie `seed_google_calendar_template.py`;
GOA-System-Key wird auf den Agenten kopiert.

Lauf im Container:  python -m scripts.seed_gmail_template
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import select

from app.db.models import Agent, Template, Visibility
from app.db.session import SessionLocal
from app.schemas.templates import AgentTemplateCreate, AgentTemplateUpdate
from app.services import connection_registry
from app.services.templates import create_agent_template, update_agent_template
from scripts._seed_owner import resolve_seed_owner

TITLE = "Gmail"
PUBLISH_TARGET = "gmail"
PROMPT = (
    "You are an email assistant with access to the user's Gmail inbox. "
    "Read and search messages (tool gmail_search, Gmail search syntax supported) "
    "and summarize them on request. Compose emails (recipient, subject, body) and "
    "send them (tool gmail_send) ONLY after the user's explicit confirmation — "
    "show the draft first and ask explicitly before you send. If there is no "
    "connection yet, point the user to click 'Connect with Google' in the "
    "Connections tab on the right."
)


async def main() -> None:
    # Sicherstellen, dass gmail als publish_target valide ist (sonst lehnt
    # create_agent_template ab). Bricht früh und klar ab, falls die Registry-Art fehlt.
    if not connection_registry.is_valid(PUBLISH_TARGET):
        raise SystemExit(f"Registry-Art '{PUBLISH_TARGET}' fehlt — connection_registry erweitern.")

    async with SessionLocal() as db:
        goa = await resolve_seed_owner(db)
        exists = (
            await db.execute(
                select(Template).where(Template.owner_id == goa.id, Template.title == TITLE)
            )
        ).scalars().first()
        if exists is not None:
            await update_agent_template(
                db, exists.id, goa,
                AgentTemplateUpdate(content_mode="slots", prompt=PROMPT),
            )
            print(f"Template '{TITLE}' aktualisiert.")
            return
        out = await create_agent_template(
            db, goa,
            AgentTemplateCreate(
                name=TITLE,
                description="Reads, searches and composes emails in your Gmail (connect per instance).",
                prompt=PROMPT,
                model="claude-haiku-4-5", price=1.0, category="Everyday",
                visibility=Visibility.PUBLIC, html_template_id="classic",
                publish_targets=[PUBLISH_TARGET], content_mode="slots",
            ),
        )
        tpl = await db.get(Template, out.id)
        agent_ids = (tpl.config or {}).get("agent_ids") or []
        if agent_ids and goa.anthropic_key_encrypted:
            agent = await db.get(Agent, UUID(str(agent_ids[0])))
            if agent is not None:
                agent.api_key_encrypted = goa.anthropic_key_encrypted
                await db.commit()
        print(f"✓ Template angelegt: {TITLE}")


if __name__ == "__main__":
    asyncio.run(main())
