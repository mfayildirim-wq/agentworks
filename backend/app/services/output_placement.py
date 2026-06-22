"""Platziert die neue (HTML-)Ausgabe gemäß Modus über das Slots-Modell. Rein/testbar.
ueberschreiben → (new, None). Sonst → (gerendertes HTML, slots-data).

Modi: `hinzufuegen` (neuer Tab vorne; 1. Ergebnis bleibt Einzelseite),
`ueberarbeiten` (ersetzt den aktiven/linken Tab), `ueberschreiben` (ersetzt alles),
`liste`/`oben`/`unten` (verlinktes Verzeichnis: jeder Lauf = ein Eintrag mit Namen aus
der Überschrift; liste/oben fügen oben ein, unten unten; Klick scrollt zum Eintrag).
Der AGENT liefert sein Ergebnis als EINEN Block (siehe output_mode_prompt)."""
from __future__ import annotations

import copy
import re
import uuid

_HEADING_RE = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.IGNORECASE | re.DOTALL)


def _default_title() -> str:
    """Standard-Titel eines neuen Abschnitts/Tabs = aktuelles Datum/Uhrzeit (umbenennbar)."""
    from app.core import clock
    return clock.now_local().strftime("%d.%m.%Y %H:%M")


def _title_from(content: str) -> str:
    """Name eines Listen-/Abschnitts-Eintrags = erste Überschrift im Inhalt (z.B. Rezeptname);
    fällt auf Datum/Uhrzeit zurück, wenn keine Überschrift gefunden wird."""
    m = _HEADING_RE.search(content or "")
    if m:
        text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if text:
            return text[:80]
    return _default_title()


def output_mode_prompt(mode: str) -> str:
    if mode == "hinzufuegen":
        return ("\n\nAUSGABE-MODUS: Liefere dein **vollständiges neues Ergebnis** als EINEN "
                "```canvas```-Block. Das System legt es als NEUEN Tab an (ältere Ergebnisse "
                "bleiben in eigenen Tabs erhalten). Wiederhole alte Ergebnisse NICHT.\n\n")
    if mode == "ueberarbeiten":
        return ("\n\nAUSGABE-MODUS: Liefere dein **überarbeitetes, vollständiges Ergebnis** als "
                "EINEN ```canvas```-Block. Das System ersetzt damit den AKTUELLEN Tab "
                "(kein neuer Tab).\n\n")
    if mode in ("liste", "oben", "unten"):
        wo = {"liste": "oben in die Liste", "oben": "oben", "unten": "unten"}[mode]
        return ("\n\nAUSGABE-MODUS: Liefere NUR deinen neuen Eintrag als EINEN ```canvas```-Block, "
                "der mit einer kurzen Überschrift (z.B. `<h2>Name</h2>`) als Titel beginnt. "
                f"Das System hängt ihn {wo} an und erzeugt automatisch einen verlinkten "
                "Verzeichnis-Eintrag (Klick scrollt zum Eintrag). Wiederhole bestehende "
                "Einträge NICHT.\n\n")
    return ""


def _as_slots(current_data: dict | None, current_content: str) -> dict:
    if current_data and "slots" in current_data:
        return copy.deepcopy(current_data)   # behält slots; layout wird je Modus gesetzt
    base = []
    if (current_content or "").strip():
        base = [{"id": "prev", "title": "Start", "type": "richtext",
                 "order": 0, "body": current_content}]
    return {"layout": "sections", "slots": base}


def apply(mode: str, *, current_data: dict | None, current_content: str,
          new_output: str, design_id: str = "") -> tuple[str, dict | None]:
    from app.services.canvas_render import render_static

    if mode == "ueberschreiben" or not mode:
        return new_output, None

    data = _as_slots(current_data, current_content)
    slots = data["slots"]

    if mode == "ueberarbeiten":
        # Einzelseite (noch keine Tab-Struktur) → einfach ersetzen.
        if not (current_data and current_data.get("slots")):
            return new_output, None
        active = min(slots, key=lambda s: s.get("order", 0))
        active["body"] = new_output
        active["title"] = active.get("title") or _default_title()
        data["layout"] = data.get("layout") or "tabs"
        return render_static(data, design_id), data

    if mode in ("liste", "oben", "unten"):
        # Verlinkte Liste/Abschnitte: erstes Ergebnis bleibt Einzelseite; ab dem zweiten
        # entsteht das Verzeichnis (Namen aus den Überschriften, Klick scrollt zum Eintrag).
        if not slots:
            return new_output, None
        data["layout"] = "liste"
        # Bestehenden „Start"-Slot (vormals Einzelseite) sinnvoll benennen.
        for s in slots:
            if s.get("title") in (None, "", "Start"):
                s["title"] = _title_from(s.get("body", ""))
        new_slot = {"id": uuid.uuid4().hex[:8], "title": _title_from(new_output),
                    "type": "richtext", "body": new_output}
        if mode == "unten":
            new_slot["order"] = max([s.get("order", 0) for s in slots], default=-1) + 1
            slots.append(new_slot)
        else:  # liste, oben → neuer Eintrag oben
            for s in slots:
                s["order"] = s.get("order", 0) + 1
            new_slot["order"] = 0
            slots.insert(0, new_slot)
        return render_static(data, design_id), data

    # mode == "hinzufuegen": erstes Ergebnis bleibt eine Einzelseite (noch keine
    # Tab-Leiste); erst ab dem zweiten Ergebnis entstehen Tabs.
    if not slots:
        return new_output, None
    # neues Ergebnis als neuer Tab ganz vorne (neuester links)
    data["layout"] = "tabs"
    for s in slots:
        s["order"] = s.get("order", 0) + 1
        s.setdefault("title", _default_title())
    new_slot = {"id": uuid.uuid4().hex[:8], "title": _default_title(),
                "type": "richtext", "order": 0, "body": new_output}
    slots.insert(0, new_slot)
    return render_static(data, design_id), data
