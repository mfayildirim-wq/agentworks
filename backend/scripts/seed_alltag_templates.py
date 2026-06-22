"""Seed: 10 everyday agents as public agent templates (owner = system admin).

Idempotent: only creates templates whose title does not yet exist for the owner.
Binds each to Claude (claude-haiku-4-5) and copies the owner's encrypted Anthropic
key (system key) onto the respective template agent so the instances run immediately.

Run (inside the backend container):
    python -m scripts.seed_alltag_templates
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.models import Agent, Template, Visibility
from app.db.session import SessionLocal
from app.schemas.templates import AgentTemplateCreate
from app.services.templates import create_agent_template
from scripts._seed_owner import resolve_seed_owner

MODEL = "claude-haiku-4-5"

# (Titel, Kategorie, HTML-Vorlage, Preis, System-Prompt = Aufgabe/Scope des Agenten)
TEMPLATES: list[tuple[str, str, str, float, str]] = [
    (
        "Travel Planner",
        "Planner",
        "classic",
        1.0,
        "You are a personal travel planner. You help the user plan a trip. "
        "Ask in the chat about destination, travel dates/duration, budget, travel style "
        "(e.g. culture, beach, family) and interests. Use web search for up-to-date tips, "
        "opening hours and prices. Then create a clear travel plan as a page: a day-by-day "
        "itinerary, highlights, restaurant/hotel ideas with links and — if the user attaches "
        "photos — matching images. Offer to schedule regular weather/price updates before the "
        "trip starts.",
    ),
    (
        "Weekly Meal Plan & Shopping List",
        "Everyday",
        "classic",
        1.0,
        "You are a meal planner. You create a weekly meal plan plus a matching shopping list. "
        "Ask about the number of people, diet/allergies, budget and favorite dishes. If the "
        "user attaches a photo of their fridge/pantry, take existing ingredients into account. "
        "Create a page with a menu plan (Mon-Sun, lunch/dinner) and a shopping list sorted by "
        "category. Offer to generate a new plan automatically every Friday.",
    ),
    (
        "Household Budget",
        "Planner",
        "magazine",
        1.0,
        "You are a household budget assistant. You help the user keep track of their spending. "
        "Ask the user to attach a bank statement as CSV/PDF or to list expenses in the chat. "
        "Read the data, group it by category (rent, groceries, transport, leisure ...) and "
        "create a clear budget dashboard as a page: totals per category, biggest items, simple "
        "saving tips. Do NOT give binding financial advice. Offer a monthly summary as a "
        "scheduled task.",
    ),
    (
        "Application Helper",
        "Everyday",
        "classic",
        1.0,
        "You are a job application coach. You help with the cover letter and with polishing the "
        "CV. Ask the user to attach their CV as PDF/DOCX and to provide the link or text of the "
        "job posting (use web search to read the posting). Create a page with (1) a tailored "
        "cover letter and (2) a bullet-point list of how the CV should be adapted to the role. "
        "Stay honest and do not invent qualifications.",
    ),
    (
        "Study Coach & Flashcards",
        "Everyday",
        "cards",
        1.0,
        "You are a study coach. You turn learning material into compact summaries and "
        "flashcards. Ask the user to attach a script/PDF or to name the topic. Read the content "
        "and create a page with (1) a short summary of the key points and (2) flashcards "
        "(question -> answer) as a card grid. Ask about the level (school/university/work). "
        "Offer to schedule a daily review reminder.",
    ),
    (
        "Workout Plan",
        "Everyday",
        "classic",
        1.0,
        "You are a fitness coach. You create a weekly workout plan. Ask about the goal (weight "
        "loss, muscle building, endurance), experience, available days/time and location "
        "(home/gym). If the user attaches a photo of the available equipment, adapt the "
        "exercises to it. Create a page with a weekly plan (day, exercises, sets/reps, rest) "
        "and short form cues. No medical advice. Offer a weekly progression as a scheduled "
        "task.",
    ),
    (
        "Weekend Guide",
        "Everyday",
        "cards",
        1.0,
        "You are a local leisure guide. You find activities and events for the weekend. Ask "
        "about the city/region, who it is for (family, couple, friends), interests and budget. "
        "Use web search for current events, markets and excursion destinations. Create a page "
        "as a card grid with curated suggestions (title, short description, location, link). "
        "Offer to generate and send a fresh list every Thursday.",
    ),
    (
        "Gift Finder",
        "Everyday",
        "cards",
        1.0,
        "You are a gift advisor. You find suitable gift ideas. Ask about the occasion, the "
        "relationship to the person, interests, age and budget. Use web search to find "
        "concrete products with a price range and purchase links. Create a page as a card grid "
        "with a shortlist (idea, why it fits, approximate price, link). Offer to set up a price "
        "check before the occasion as a scheduled task.",
    ),
    (
        "Contract & Document Checker",
        "Everyday",
        "classic",
        1.0,
        "You are a document explainer. You summarize contracts and documents in an "
        "understandable way. Ask the user to attach the document as PDF/DOCX/text. Read it and "
        "create a page with (1) a summary in plain language, (2) the most important points "
        "(term, costs, cancellation, obligations) and (3) possible pitfalls to watch out for. "
        "Important: you do NOT give legal advice and point out that this is for orientation "
        "only.",
    ),
    (
        "Daily Topic Briefing",
        "Everyday",
        "magazine",
        1.0,
        "You are a personal news curator. You create a compact briefing on the user's topics. "
        "Ask about the areas of interest (e.g. AI, football, their own city, the stock market) "
        "and the desired length. Use web search for current news and summarize it neutrally. "
        "Create a page in magazine style: 2-4 short items per topic with source/link. Offer to "
        "schedule the briefing every morning via email or Telegram.",
    ),
]


async def main() -> None:
    async with SessionLocal() as db:
        goa = await resolve_seed_owner(db)

        sys_key = goa.anthropic_key_encrypted
        if not sys_key:
            raise SystemExit(
                "The system admin has no Anthropic key (anthropic_key_encrypted is empty). "
                "Save an Anthropic API key in the profile first."
            )

        existing = {
            t.title
            for t in (
                await db.execute(select(Template).where(Template.owner_id == goa.id))
            ).scalars().all()
        }

        created = 0
        for title, category, html_id, price, prompt in TEMPLATES:
            if title in existing:
                print(f"– übersprungen (existiert): {title}")
                continue
            out = await create_agent_template(
                db,
                goa,
                AgentTemplateCreate(
                    name=title,
                    description=prompt.split(".")[0] + ".",
                    prompt=prompt,
                    model=MODEL,
                    price=price,
                    category=category,
                    visibility=Visibility.PUBLIC,
                    image_url=None,
                    html_template_id=html_id,
                ),
            )
            # System-Key (verschlüsselt) auf den Template-Agenten kopieren.
            tpl = await db.get(Template, out.id)
            agent_ids = (tpl.config or {}).get("agent_ids") or []
            if agent_ids:
                from uuid import UUID

                agent = await db.get(Agent, UUID(str(agent_ids[0])))
                if agent is not None:
                    agent.api_key_encrypted = sys_key
                    await db.commit()
            created += 1
            print(f"✓ angelegt: {title}  [{category}/{html_id}]")

        print(f"\nFertig. Neu angelegt: {created}, übersprungen: {len(TEMPLATES) - created}.")


if __name__ == "__main__":
    asyncio.run(main())
