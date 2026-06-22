"""Slot-DB pro Instanz: liest/merged Slots in artifact_version.data, rendert HTML
(Fallback) und schreibt eine neue Version. Owner-only. body wird sanitisiert."""

from __future__ import annotations

import copy
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, ArtifactVersion
from app.services.artifacts import record_version
from app.services.canvas_render import render_static, sanitize_html

_EMPTY = {"layout": "sections", "slots": []}


async def _owned(db, artifact_id, owner_id):
    art = await db.get(Artifact, artifact_id)
    return art if art is not None and art.owner_id == owner_id else None


async def _current_data(db, art) -> dict:
    if art.current_version_id is not None:
        v = await db.get(ArtifactVersion, art.current_version_id)
        if v is not None and v.data:
            # deepcopy: jede Version braucht ihren eigenen data-Schnappschuss; die
            # ORM-geladene JSON-Liste darf nicht in-place mutiert werden.
            return copy.deepcopy(v.data)
    return {"layout": "sections", "slots": []}


async def _save(db, art, data: dict) -> dict:
    design_id = ""
    if art.template_id is not None:
        from app.db.models import Template

        tpl = await db.get(Template, art.template_id)
        design_id = (tpl.config or {}).get("html_template_id", "") if tpl else ""

    # Render-Dispatch nach gewähltem output_template der Instanz:
    #   prepared:<name> → fertige Datei-Vorlage (Slots füllen Platzhalter, CSS inline)
    #   slots:<design>  → Slot-Renderer mit einem bestimmten Design (render_static)
    #   "" (Legacy)     → Slot-Renderer mit dem Template-Design (unverändert)
    ot = (art.output_template or "")
    if ot.startswith("prepared:"):
        from app.services import page_templates

        name = ot.split(":", 1)[1]
        if page_templates.get(name) is not None:
            values = {s.get("id"): s.get("body", "") for s in (data.get("slots") or [])}
            html = page_templates.render(name, values)
        else:
            # Unbekannte Vorlage → sicherer Legacy-Fallback (kein Render-Crash).
            html = render_static(data, design_id)
    elif ot.startswith("slots:"):
        html = render_static(data, ot.split(":", 1)[1])
    else:
        html = render_static(data, design_id)
    await record_version(
        db, artifact_id=art.id, content=html, prompt="(slots)", run_id=None, data=data
    )
    return data


async def get_slots(db: AsyncSession, artifact_id: UUID, owner_id: UUID) -> dict | None:
    art = await _owned(db, artifact_id, owner_id)
    if art is None:
        return None
    return await _current_data(db, art)


async def upsert_slot(
    db, artifact_id, owner_id, *, slot_id, title=None, body=None, type="richtext", order=None
) -> dict | None:
    art = await _owned(db, artifact_id, owner_id)
    if art is None:
        return None
    data = await _current_data(db, art)
    slots = data.setdefault("slots", [])
    slot = next((s for s in slots if s.get("id") == slot_id), None)
    if slot is None:
        slot = {"id": slot_id, "title": "", "type": type, "order": len(slots), "body": ""}
        slots.append(slot)
    if title is not None:
        slot["title"] = title
    if body is not None:
        slot["body"] = sanitize_html(body)
    if order is not None:
        slot["order"] = order
    slot["type"] = type
    return await _save(db, art, data)


async def remove_slot(db, artifact_id, owner_id, slot_id) -> dict | None:
    art = await _owned(db, artifact_id, owner_id)
    if art is None:
        return None
    data = await _current_data(db, art)
    data["slots"] = [s for s in data.get("slots", []) if s.get("id") != slot_id]
    return await _save(db, art, data)


async def set_layout(db, artifact_id, owner_id, layout) -> dict | None:
    if layout not in ("sections", "tabs"):
        raise ValueError("layout muss 'sections' oder 'tabs' sein")
    art = await _owned(db, artifact_id, owner_id)
    if art is None:
        return None
    data = await _current_data(db, art)
    data["layout"] = layout
    return await _save(db, art, data)
