"""Ausgabe-Vertrag des Dialog-Agenten.

Der Agent antwortet als Prosa (= Chat) und gibt die Seite — falls er sie bauen
oder ändern will — in genau einem eingezäunten Block aus:

    ```canvas
    <!doctype html> … komplette Seite …
    ```

`split_agent_output` trennt beides: Prosa → Chat-Nachricht, Canvas-Block →
neuer Seiteninhalt. Modell-agnostisch (auch kleine lokale Modelle), daher mit
Robustheits-Fallbacks (``` ```html ``` als Alias, reines HTML ohne Zaun).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, ArtifactMessage, ArtifactVersion, User
from app.services import chat_summary

# Erster eingezäunter Block mit Sprache `canvas` oder `html` (alias für kleine Modelle).
_FENCE = re.compile(r"```(?:canvas|html)[^\n]*\n(.*?)```", re.DOTALL | re.IGNORECASE)
# Geöffneter, aber NICHT geschlossener Zaun (abgeschnittene Ausgabe) → Rest = Canvas.
_OPEN_FENCE = re.compile(r"```(?:canvas|html)[^\n]*\n(.*)\Z", re.DOTALL | re.IGNORECASE)

# Was der Agent pro Turn liefern soll: Dialog im Chat, Ergebnis als ```canvas```-Block.
CANVAS_CONTRACT = (
    "## Dialog & Ergebnis (WICHTIG)\n"
    "Du führst einen Dialog und pflegst eine HTML-Seite (das Ergebnis).\n"
    "- Fehlt dir Kontext für die erste Seite, FRAGE zuerst im Chat (normaler Text). "
    "Gib in diesem Fall KEINE Seite aus.\n"
    "- Sobald du genug weißt ODER der Nutzer eine Änderung wünscht, gib die KOMPLETTE "
    "Seite in genau EINEM Block aus:\n"
    "```canvas\n<!doctype html> … komplette Seite …\n```\n"
    "- Reine Infos/Rückfragen bleiben normaler Chat-Text (ohne canvas-Block).\n"
    "- Bei Änderungen immer die GANZE aktualisierte Seite erneut als ```canvas```-Block.\n"
    "- Halte die Seite KOMPAKT und in sich GESCHLOSSEN (vollständiges <html>…</html>): "
    "klare Struktur, keine unnötig langen Fließtexte — die Seite muss komplett ausgegeben "
    "werden, ohne abzubrechen.\n"
    "- Beende JEDE Antwort mit 1–3 konkreten, passenden Folgefragen oder Vorschlägen, was "
    "du als Nächstes tun könntest (z.B. „Soll ich Tag 2 mit Museen ergänzen?“ oder "
    "„Möchtest du Hotel-Empfehlungen?“). Halte den Nutzer aktiv im Dialog.\n\n"
)

# Hinweis (alle Modi): Auswahlmoeglichkeiten als ```chips-Block — bleibt im Chat-Text,
# das Frontend macht daraus klickbare Buttons (split_agent_output entfernt ihn NICHT).
CHIPS_NOTE = (
    "AUSWAHL-VORSCHLAEGE: Wenn du dem Nutzer Auswahlmoeglichkeiten gibst, biete sie als "
    "```chips-Block an (eine Option pro Zeile) — sie erscheinen als klickbare Buttons. Beispiel:\n"
    "```chips\nJa, veroeffentliche\nNein, noch aendern\n```\n\n"
)

# Wird als Assistant-Nachricht genutzt, wenn der Agent nur die Seite (ohne Prosa) liefert.
_CANVAS_DONE_TEXT = "Ich habe die Seite aktualisiert."

# Anstoß für den Init-Turn (leerer Verlauf): Agent begrüßt + stellt die ersten Fragen.
_KICKOFF = (
    "(Neue Sitzung — der Nutzer hat gerade geöffnet. Begrüße ihn kurz und stelle die "
    "Fragen, die du brauchst, um die erste Seite zu erstellen.)"
)


# Altlast aus dem Loop-Protokoll (goal_loop): „STATUS: …"-Zeilen gehören nicht in den Chat.
_STATUS_LINE = re.compile(r"^\s*STATUS:.*$", re.MULTILINE | re.IGNORECASE)


def _strip_status_lines(s: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", _STATUS_LINE.sub("", s)).strip()


def _looks_like_html(s: str) -> bool:
    low = s.lstrip().lower()
    if low.startswith("<!doctype") or low.startswith("<html"):
        return True
    # Beginnt mit einem HTML-Tag und enthält irgendwo ein schließendes Tag.
    return bool(re.match(r"^<[a-z][a-z0-9]*[\s>]", low)) and "</" in low


def split_agent_output(text: str) -> tuple[str, str | None]:
    """Zerlegt die Agent-Ausgabe in (Chat-Prosa, Canvas-HTML|None).

    - Ist ein ```canvas```/```html```-Block vorhanden, wird sein Inhalt als Canvas
      genommen (nur der erste) und alle solchen Blöcke aus der Prosa entfernt.
    - Ohne Block, aber roher HTML-Text → ganzer Text als Canvas, Chat leer.
    - Sonst → reiner Chat-Turn (Canvas None).
    """
    text = text or ""
    matches = list(_FENCE.finditer(text))
    if matches:
        canvas = matches[0].group(1).strip()
        chat = _strip_status_lines(_FENCE.sub("", text))
        return chat, canvas

    # Abgeschnittene Ausgabe: Zaun geöffnet, aber nie geschlossen → Rest als Canvas.
    open_m = _OPEN_FENCE.search(text)
    if open_m:
        canvas = open_m.group(1).strip()
        chat = _strip_status_lines(text[: open_m.start()])
        return chat, canvas

    stripped = text.strip()
    if _looks_like_html(stripped):
        return "", stripped
    return _strip_status_lines(stripped), None


def prepared_slot_note(placeholders: list[dict]) -> str:
    """Zusatz für den prepared-Modus: nennt die FESTEN Platzhalter-Slots der Vorlage.

    Der Agent soll GENAU diese Keys per update_slot(slot_id=<key>, …) füllen — keine
    eigenen Slots anlegen, kein eigenes HTML/Canvas erzeugen."""
    if not placeholders:
        return ""
    keys = ", ".join(f"{p['key']} ({p.get('label', p['key'])})" for p in placeholders)
    return (
        "Die Seite hat feste Abschnitte: "
        + keys
        + ". Fülle GENAU diese per update_slot(slot_id=<key>, …); lege keine anderen "
        "Slots an und erzeuge kein eigenes HTML.\n\n"
    )


def build_turn_system_prompt(
    purpose: str, current_canvas: str | None, content_mode: str = "html"
) -> str:
    """System-Prompt eines Dialog-Turns: Scope-Guard + Canvas-Vertrag + aktuelle Seite.

    Im Slots-Modus (`content_mode="slots"`) entfällt der CANVAS_CONTRACT: die Seite wird
    nicht als ganzer ```canvas```-Block ausgegeben, sondern per Slot-Tools gepflegt (deren
    Anweisung kommt aus `slot_etiquette()` im make_completer). Der `html`-Pfad bleibt unverändert.
    """
    from app.services.artifacts import build_scope_guard

    canvas_note = (
        "Aktuelle Seite (nur zur Orientierung, nicht erneut ausgeben, außer du änderst sie):\n"
        f"{current_canvas}\n\n"
        if current_canvas
        else "Es gibt noch KEINE Seite — erzeuge sie, sobald du genug Kontext hast.\n\n"
    )
    if content_mode == "slots":
        return build_scope_guard(purpose) + canvas_note + CHIPS_NOTE
    return build_scope_guard(purpose) + CANVAS_CONTRACT + canvas_note + CHIPS_NOTE


async def _legacy_content_mode(db: AsyncSession, art: Artifact) -> str:
    """content_mode ('html' | 'slots') aus dem Template-Config der Instanz (Altlast-Pfad)."""
    from app.db.models import Template

    if art.template_id is None:
        return "html"
    tpl = await db.get(Template, art.template_id)
    if tpl is None:
        return "html"
    return (tpl.config or {}).get("content_mode", "html")


async def _output_mode_for(db: AsyncSession, art: Artifact) -> tuple[str, list[dict]]:
    """Löst den Ausgabe-Modus der Instanz aus `output_template` auf.

    Liefert (mode, placeholders): mode ist der bestehende String ('html' | 'slots'),
    der bestimmt, ob CANVAS_CONTRACT oder Slot-Tools greifen. placeholders ist nur im
    prepared-Fall gefüllt (die FESTEN Platzhalter-Keys der Vorlage), sonst leer.

    - `prepared:<name>` → ('slots', [placeholders der Vorlage])
    - `slots:<design>`  → ('slots', []) — freie Slots wie bisher
    - `agent`           → ('html', []) — CANVAS_CONTRACT wie bisher
    - leer (Altlast)    → Template-config content_mode, []
    """
    ot = art.output_template or ""
    if ot.startswith("prepared:"):
        from app.services import page_templates

        tpl = page_templates.get(ot.split(":", 1)[1])
        return "slots", (tpl or {}).get("placeholders", [])
    if ot.startswith("slots:"):
        return "slots", []
    if ot == "agent":
        return "html", []
    return await _legacy_content_mode(db, art), []


async def _content_mode_for(db: AsyncSession, art: Artifact) -> str:
    """content_mode ('html' | 'slots') der Instanz — nach `output_template` aufgelöst."""
    mode, _ = await _output_mode_for(db, art)
    return mode


def compose_history(messages: list[ArtifactMessage]) -> str:
    """Rendert den bisherigen Chatverlauf als Text (modell-agnostisch, ein Turn-Input)."""
    lines: list[str] = []
    for m in messages:
        who = "Nutzer" if m.role == "user" else "Agent"
        lines.append(f"{who}: {m.content}")
    return "\n".join(lines)


async def run_turn(
    db: AsyncSession,
    *,
    artifact_id: UUID,
    complete: Callable[[str, str], Awaitable[str]],
    summarize: Callable[[str, list], Awaitable[str]] | None = None,
) -> ArtifactMessage | None:
    """Führt einen Dialog-Turn aus: baut den Prompt, ruft `complete(system, message)`,
    splittet die Ausgabe und schreibt die Assistant-Nachricht (+ optional neue Version).

    `complete` ist injiziert (in Tests gefälscht, in Produktion der echte LLM-Aufruf).
    """
    from app.services.artifacts import _load_agent_purpose, record_version_placed

    art = await db.get(Artifact, artifact_id)
    if art is None:
        return None

    rows = await db.execute(
        select(ArtifactMessage)
        .where(ArtifactMessage.artifact_id == artifact_id)
        .order_by(ArtifactMessage.created_at)
    )
    history = list(rows.scalars().all())
    last_user = next((m.content for m in reversed(history) if m.role == "user"), "")

    current_canvas = None
    if art.current_version_id is not None:
        v = await db.get(ArtifactVersion, art.current_version_id)
        current_canvas = v.content if v else None

    content_mode, placeholders = await _output_mode_for(db, art)
    purpose = await _load_agent_purpose(db, art.agent_id)
    system = build_turn_system_prompt(purpose, current_canvas, content_mode=content_mode)
    if placeholders:
        system = system + prepared_slot_note(placeholders)
    # Ausgabe-Modus (oben/unten/neuer_tab): der Agent soll NUR den neuen Block liefern,
    # das System platziert ihn (nur html-Modus; Slots-Agenten pflegen Abschnitte selbst).
    if content_mode != "slots":
        from app.services.output_placement import output_mode_prompt

        system = system + output_mode_prompt(getattr(art, "output_mode", "ueberschreiben"))
    # Verbindliche Systemzeit voranstellen — der Agent kennt „heute" so aus der App,
    # nicht aus eigener Annahme. Name aus dem Instanz-Eigentümer (für die Begrüßung).
    from app.core import clock

    owner = await db.get(User, art.owner_id)
    system = clock.time_context(name=owner.name if owner else None) + system
    to_fold, recent, new_count = chat_summary.select_window(history, art.summarized_count)
    if to_fold:
        _sum = summarize or chat_summary.summarize
        art.chat_summary = await _sum(art.chat_summary or "", to_fold)
        art.summarized_count = new_count
    message = chat_summary.build_turn_input(art.chat_summary or "", recent) or _KICKOFF

    text = await complete(system, message)

    version: ArtifactVersion | None = None
    if content_mode == "slots":
        # Slots-Modus: das Tool update_slot hat bereits Versionen aufgezeichnet.
        # Hier KEINE ```canvas```-Extraktion — der Text ist reine Chat-Prosa.
        content = _strip_status_lines(text or "")
    else:
        chat, canvas = split_agent_output(text)
        if canvas:
            version = await record_version_placed(
                db, artifact_id=artifact_id, content=canvas, prompt=last_user, run_id=None
            )
        content = chat or (_CANVAS_DONE_TEXT if canvas else "")
    assistant = ArtifactMessage(
        artifact_id=artifact_id,
        role="assistant",
        content=content,
        version_id=version.id if version else None,
    )
    db.add(assistant)
    await db.commit()
    await db.refresh(assistant)
    return assistant


async def post_chat_message(
    db: AsyncSession,
    artifact_id: UUID,
    owner_id: UUID,
    message: str,
    file_ids: list[UUID] | None = None,
) -> bool:
    """Speichert die Nutzer-Nachricht (inkl. Datei-Kontext) und reiht den Dialog-Turn ein.
    False, wenn die Instanz fremd ist. Bei angehängten Dateien hängt `attachments_context`
    den extrahierten Dokumenttext bzw. Bild-URLs direkt an den Nachrichtentext; die
    Datei-IDs werden zusätzlich an der Nachricht persistiert (für den Vision-Pfad)."""
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != owner_id:
        return False
    from app.services.artifact_files import attachments_context

    ids = file_ids or []
    content = message + await attachments_context(db, artifact_id, ids)
    db.add(
        ArtifactMessage(
            artifact_id=artifact_id,
            role="user",
            content=content,
            file_ids=[str(x) for x in ids] or None,
        )
    )
    await db.commit()

    from app.workers import execute_chat_turn

    execute_chat_turn.send(str(artifact_id))
    return True


async def start_turn(db: AsyncSession, artifact_id: UUID, owner_id: UUID) -> bool:
    """Init-Turn beim ersten Öffnen: stößt die Begrüßung an, falls noch kein Verlauf
    existiert. Idempotent (mehrfaches Öffnen erzeugt keine Mehrfach-Greetings)."""
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != owner_id:
        return False
    existing = await db.execute(
        select(ArtifactMessage.id).where(ArtifactMessage.artifact_id == artifact_id).limit(1)
    )
    if existing.first() is not None:
        return True  # schon ein Verlauf vorhanden → nichts tun

    from app.workers import execute_chat_turn

    execute_chat_turn.send(str(artifact_id))
    return True


async def list_chat_messages(
    db: AsyncSession, artifact_id: UUID, owner_id: UUID
) -> list[dict] | None:
    """Chatverlauf inkl. `version_no` der erzeugten Seiten. None, wenn fremd/fehlt."""
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != owner_id:
        return None

    rows = await db.execute(
        select(ArtifactMessage)
        .where(ArtifactMessage.artifact_id == artifact_id)
        .order_by(ArtifactMessage.created_at)
    )
    messages = list(rows.scalars().all())

    version_nos: dict[UUID, int] = {}
    vids = [m.version_id for m in messages if m.version_id is not None]
    if vids:
        vrows = await db.execute(
            select(ArtifactVersion.id, ArtifactVersion.version_no).where(
                ArtifactVersion.id.in_(vids)
            )
        )
        version_nos = {vid: no for vid, no in vrows.all()}

    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "version_id": m.version_id,
            "version_no": version_nos.get(m.version_id) if m.version_id else None,
            "created_at": m.created_at,
        }
        for m in messages
    ]
