"""Öffentliches „Webseite-Ersteller"-Template (System-User GOA), publish_targets=["sftp"].
Kopiert GOA's System-Key auf den Agenten (wie seed_alltag_templates). Idempotent."""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import select

from app.db.models import Agent, Template, Visibility
from app.db.session import SessionLocal
from app.schemas.templates import AgentTemplateCreate
from app.services.templates import create_agent_template
from scripts._seed_owner import resolve_seed_owner

TITLE = "Website Builder (to your server, FTP)"
PROMPT = (
    "From the dialog you build a simple, beautiful website (e.g. a personal one-pager: "
    "introduction, contact, links). Ask about name, purpose, content and style. When "
    "the user is satisfied, point out that they can upload the page to their OWN server "
    "(SFTP) — via the 'Publish' button on the right, or by asking you to do it "
    "(ask briefly for confirmation first)."
)


async def main() -> None:
    async with SessionLocal() as db:
        goa = await resolve_seed_owner(db)
        exists = (
            await db.execute(
                select(Template).where(Template.owner_id == goa.id, Template.title == TITLE)
            )
        ).scalars().first()
        if exists is not None:
            print("existiert bereits — nichts zu tun.")
            return
        out = await create_agent_template(
            db, goa,
            AgentTemplateCreate(
                name=TITLE, description="Builds a website and publishes it via SFTP.",
                prompt=PROMPT, model="claude-haiku-4-5", price=1.0, category="Software",
                visibility=Visibility.PUBLIC, html_template_id="classic",
                publish_targets=["sftp"],
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
