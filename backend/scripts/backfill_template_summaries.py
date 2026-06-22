"""Einmal-Backfill: Template.description aus dem Prompt (config.prompt_template) erzeugen.
Lauf: docker exec agentworks-backend python -m scripts.backfill_template_summaries"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.models import Template
from app.db.session import SessionLocal
from app.services import template_summary


async def main() -> None:
    done = skipped = 0
    async with SessionLocal() as db:
        tpls = (await db.execute(select(Template))).scalars().all()
        for t in tpls:
            prompt = (t.config or {}).get("prompt_template") or ""
            if not prompt.strip():
                skipped += 1
                continue
            desc = await template_summary.summarize_prompt(prompt)
            if desc:
                t.description = desc
                done += 1
            else:
                skipped += 1
        await db.commit()
    print(f"backfill fertig: {done} aktualisiert, {skipped} übersprungen")


if __name__ == "__main__":
    asyncio.run(main())
