"""Öffentliches „WordPress-Inhalts-Agent"-Template (GOA), publish_targets=["wordpress"].
Kopiert GOA's System-Key auf den Agenten. Idempotent."""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import select

from app.db.models import Agent, Template, Visibility
from app.db.session import SessionLocal
from app.schemas.templates import AgentTemplateCreate
from app.services.templates import create_agent_template
from scripts._seed_owner import resolve_seed_owner

TITLE = "WordPress Content Agent"
PROMPT = (
    "You help the user create content (e.g. blog posts) and publish it on THEIR "
    "own WordPress site. Ask about topic, style and length, and "
    "create the post as an HTML page. When the user is satisfied, offer to publish it "
    "to their WordPress site (tool wordpress_publish) — ask "
    "briefly for confirmation first and whether it should be a draft or immediately "
    "visible. The user sets up the WordPress credentials on the right under 'Connection'."
)


async def main() -> None:
    async with SessionLocal() as db:
        goa = await resolve_seed_owner(db)
        exists = (await db.execute(
            select(Template).where(Template.owner_id == goa.id, Template.title == TITLE)
        )).scalars().first()
        if exists is not None:
            print("existiert bereits — nichts zu tun.")
            return
        out = await create_agent_template(
            db, goa,
            AgentTemplateCreate(
                name=TITLE,
                description="Creates content and publishes it on your WordPress site.",
                prompt=PROMPT, model="claude-haiku-4-5", price=1.0, category="Software",
                visibility=Visibility.PUBLIC, html_template_id="classic",
                publish_targets=["wordpress"],
            ),
        )
        tpl = await db.get(Template, out.id)
        agent_ids = (tpl.config or {}).get("agent_ids") or []
        if agent_ids and goa.anthropic_key_encrypted:
            agent = await db.get(Agent, UUID(str(agent_ids[0])))
            if agent is not None:
                agent.api_key_encrypted = goa.anthropic_key_encrypted
                await db.commit()
        print(f"✓ angelegt: {TITLE}")


if __name__ == "__main__":
    asyncio.run(main())
