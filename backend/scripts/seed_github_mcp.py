"""Seed: GitHub als erster ECHTER Token-MCP (Klasse A — Remote, Header-Auth).

Legt idempotent an:
1. Katalog-Eintrag `github` → GitHubs gehosteter Remote-MCP, Auth per
   `Authorization: Bearer <PAT>` (streamable_http) — kein Eigen-Hosting.
2. Öffentliches Template „GitHub-Assistent" (Besitzer GOA), Claude, mcp_servers=[github],
   GOA-System-Key auf den Agenten kopiert (wie seed_alltag_templates / seed_mcp_demo_template).

Lauf im Container:  python -m scripts.seed_github_mcp
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import select

from app.db.models import Agent, Template, Visibility
from app.db.session import SessionLocal
from app.schemas.templates import AgentTemplateCreate, AgentTemplateUpdate
from app.services import mcp_catalog
from app.services.templates import create_agent_template, update_agent_template
from scripts._seed_owner import resolve_seed_owner

SERVER_ID = "github"
SERVER_URL = "https://api.githubcopilot.com/mcp/"

TITLE = "GitHub Assistant"
PROMPT = (
    "You are a GitHub assistant with access to the user's GitHub MCP tools. "
    "Help manage issues, pull requests and repositories through dialog. "
    "Build the results as SECTIONS (slots) of the page: use the update_slot tool — "
    "e.g. a slot 'uebersicht' for a summary and one slot 'repo:<name>' per "
    "repository. Create a SEPARATE slot 'repo:<name>' for each repository — do not put "
    "everything into a single 'uebersicht' slot. Update existing slots via the same slot_id "
    "instead of creating everything anew — that way the page GROWS instead of being "
    "overwritten. Ask briefly before write GitHub actions (creating an issue, commenting). If "
    "no GitHub token is set yet, point the user to save a GitHub Personal Access Token in the "
    "Connections panel on the right."
)


async def main() -> None:
    async with SessionLocal() as db:
        goa = await resolve_seed_owner(db)

        # 1) Catalog entry (idempotent)
        entry = await mcp_catalog.get(db, SERVER_ID)
        if entry is None:
            await mcp_catalog.create(
                db,
                server_id=SERVER_ID,
                name="GitHub",
                description="GitHub's hosted remote MCP — issues, PRs, repos. Auth via Personal Access Token.",
                transport="streamable_http",
                url=SERVER_URL,
                requires_credential=True,
                updated_by=goa.email,
                auth_header="Authorization",
                auth_value_template="Bearer {secret}",
                secret_label="GitHub Personal Access Token",
            )
            print(f"✓ Catalog entry created: {SERVER_ID} → {SERVER_URL}")
        else:
            print(f"Catalog entry {SERVER_ID} already exists — skipped.")

        # 2) Template (idempotent by title for the owner)
        exists = (
            await db.execute(
                select(Template).where(Template.owner_id == goa.id, Template.title == TITLE)
            )
        ).scalars().first()
        if exists is not None:
            # Bestehende Vorlage auf Slots-Modus + neuen Prompt heben (idempotent).
            await update_agent_template(
                db, exists.id, goa,
                AgentTemplateUpdate(content_mode="slots", prompt=PROMPT),
            )
            print(f"Template '{TITLE}' aktualisiert → content_mode=slots.")
            return
        out = await create_agent_template(
            db, goa,
            AgentTemplateCreate(
                name=TITLE,
                description="Manages your GitHub issues, PRs and repos through dialog (via MCP).",
                prompt=PROMPT,
                model="claude-haiku-4-5", price=1.0, category="Tech",
                visibility=Visibility.PUBLIC, html_template_id="classic",
                mcp_servers=[SERVER_ID], content_mode="slots",
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
