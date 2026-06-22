"""Agenten-Tools (Phase 2a): Web-Suche + Seitenabruf für tool-fähige Online-Modelle.

Tools sind einfache async-Funktionen mit Typannotationen + Docstring — AutoGen leitet
daraus das Tool-Schema ab. I/O (httpx) lebt hier; reine Hilfsfunktionen sind direkt testbar.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx

from app.core.settings import get_settings

settings = get_settings()

_FETCH_TIMEOUT = 15
_MAX_BYTES = 2_000_000
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)


def is_safe_public_url(url: str) -> bool:
    """True nur für http(s)-URLs, deren aufgelöste IP(s) öffentlich sind (SSRF-Schutz)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def _html_to_text(html: str) -> str:
    """Reduziert HTML grob auf sichtbaren Text (Script/Style raus, Tags strippen)."""
    no_scripts = _SCRIPT_STYLE_RE.sub(" ", html or "")
    text = _TAG_RE.sub(" ", no_scripts)
    return re.sub(r"\s+", " ", text).strip()


async def web_fetch(url: str) -> str:
    """Holt eine öffentliche Webseite und gibt ihren sichtbaren Text gekürzt zurück.

    Nutze dies, um den Inhalt einer konkreten URL zu lesen (z.B. aus web_search).
    Args:
        url: Vollständige http(s)-URL einer öffentlichen Seite.
    """
    # SSRF-Guard zuerst (vor jedem Netzwerkzugriff). Hinweis: zwischen dieser Prüfung
    # und dem Abruf löst httpx den Hostnamen erneut auf — ein residuales DNS-Rebinding-
    # TOCTOU-Fenster bleibt (für 2a akzeptiert; echte Mitigation = validierte IP pinnen).
    if not is_safe_public_url(url):
        return "Fehler: URL nicht erlaubt (nur öffentliche http(s)-Adressen)."
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, follow_redirects=False) as client:
            async with client.stream(
                "GET", url, headers={"User-Agent": "AgentWorks/1.0"}
            ) as r:
                if 300 <= r.status_code < 400:
                    return "Fehler: Weiterleitung wird aus Sicherheitsgründen nicht gefolgt."
                if r.status_code >= 400:
                    return f"Fehler: HTTP {r.status_code}"
                ctype = r.headers.get("content-type", "")
                if not any(k in ctype for k in ("text", "html", "json")):
                    return f"Fehler: nicht-textueller Inhalt ({ctype or 'unbekannt'})."
                chunks: list[bytes] = []
                total = 0
                async for chunk in r.aiter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= _MAX_BYTES:
                        break
                body = b"".join(chunks)[:_MAX_BYTES]
    except Exception as e:  # noqa: BLE001 — Tool-Fehler werden als Text zurückgegeben
        return f"Fehler beim Abruf: {type(e).__name__}"
    text = body.decode("utf-8", errors="replace")
    return _html_to_text(text)[:8000]


def _format_search_results(data: dict) -> str:
    results = (data or {}).get("results", [])[:5]
    if not results:
        return "Keine Treffer."
    lines = [
        f"- {x.get('title', '')} — {x.get('url', '')} — {(x.get('content', '') or '')[:200]}"
        for x in results
    ]
    return "\n".join(lines)


async def web_search(query: str) -> str:
    """Sucht im Web (SearXNG) und gibt die Top-Treffer als Liste 'Titel — URL — Snippet'.

    Nutze dies, um aktuelle Informationen oder die passende Quelle zu einer Frage zu finden.
    Args:
        query: Suchanfrage in natürlicher Sprache.
    """
    url = f"{settings.searxng_url.rstrip('/')}/search"
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
            r = await client.get(url, params={"q": query, "format": "json"})
            r.raise_for_status()
            data = r.json()
    except Exception:  # noqa: BLE001 — Tool-Fehler als Text
        return "Suche derzeit nicht verfügbar."
    return _format_search_results(data)


def tool_capability_note(tool_capable: bool) -> str:
    """System-Prompt-Zusatz, wenn das Modell KEINE Tools hat: ehrlich bleiben."""
    if tool_capable:
        return ""
    return (
        "WICHTIG — Werkzeuge: Dieses Modell hat keine Werkzeuge (keine Web-Suche, kein "
        "Planen von Aufgaben). Wenn der Nutzer aktuelle Live-Daten oder geplante Aufgaben "
        "verlangt, sage ehrlich, dass dafür ein Online-Modell (z.B. Claude) nötig ist — "
        "erfinde keine aktuellen Daten.\n\n"
    )


def scheduling_etiquette() -> str:
    """System-Prompt-Zusatz für tool-fähige Chat-Agenten: erst fragen, dann planen."""
    return (
        "AUFGABEN PLANEN: Mit dem Werkzeug schedule_job kannst du zeitgesteuerte Aufgaben "
        "für diese Instanz anlegen. Wähle den passenden `mode`:\n"
        "- `reminder`: dem Nutzer regelmäßig eine NACHRICHT schicken (Erinnerung, "
        "Begrüßung, Briefing) — die Seite wird NICHT verändert.\n"
        "- `update`: die SEITE regelmäßig aktualisieren (Nutzer bekommt einen Hinweis mit Link).\n"
        "- `history`: wie update, zusätzlich als Verlauf markiert.\n"
        "Wenn unklar ist, welcher Modus gemeint ist, FRAGE zuerst nach — biete die Auswahl "
        "als Chips an, z. B.:\n"
        "```chips\nNur Nachricht\nSeite aktualisieren\nMit Verlauf\n```\n"
        "Lege eine Aufgabe ERST an, wenn der Nutzer zugestimmt hat — beschreibe vorher kurz "
        "(was, wann, welcher Modus, welche Benachrichtigung). Mit list_jobs/cancel_job kannst "
        "du bestehende Aufgaben zeigen bzw. abbrechen.\n\n"
    )


def _scheduling_tools(artifact_id: UUID, owner_id: UUID) -> list:
    """Baut die an die Instanz gebundenen Scheduling-Tools (eigene DB-Session je Aufruf)."""
    from app.db.session import SessionLocal
    from app.services import artifact_jobs as jobs_svc

    async def schedule_job(
        title: str,
        instruction: str,
        trigger_kind: str,
        cadence: str = "daily",
        hour: int = 8,
        minute: int = 0,
        run_at: str = "",
        notify_email: bool = False,
        notify_telegram: bool = False,
        mode: str = "update",
    ) -> str:
        """Plant eine Aufgabe für DIESE Instanz (erst NACH Zustimmung des Nutzers anlegen).

        Args:
            title: Kurzer Titel der Aufgabe.
            instruction: Was die Instanz bei jedem Lauf tun soll.
            trigger_kind: "recurring" (wiederkehrend) oder "once" (einmalig).
            cadence: bei recurring — "hourly" | "daily" | "weekly".
            hour: bei daily/weekly — Stunde 0-23 in lokaler Zeit.
            minute: Minute 0-59 in lokaler Zeit (bei hourly: die Minute jeder Stunde).
            run_at: bei once — lokale Startzeit als ISO 'YYYY-MM-DDTHH:MM'.
            notify_email: nach dem Lauf zusätzlich per E-Mail benachrichtigen.
            notify_telegram: nach dem Lauf zusätzlich per Telegram benachrichtigen.
            mode: "reminder" = nur eine Nachricht senden (kein Seiten-Update);
                  "update" = die Seite aktualisieren; "history" = Seite + Verlauf.
        """
        tz = settings.default_timezone
        cron_expr: str | None = None
        run_at_dt: datetime | None = None
        if trigger_kind == "once":
            if not run_at:
                return "Fehler: Für eine einmalige Aufgabe brauche ich run_at (ISO-Zeit)."
            try:
                run_at_dt = run_at_from_local(run_at, tz)
            except ValueError:
                return "Fehler: run_at ist keine gültige ISO-Zeit (z.B. 2026-06-11T08:00)."
        else:
            trigger_kind = "recurring"
            if cadence not in ("hourly", "daily", "weekly"):
                cadence = "daily"
            cron_expr = cron_from_local(cadence, hour, tz, minute=minute)
        async with SessionLocal() as db:
            job = await jobs_svc.create_job_from_tool(
                db,
                artifact_id=artifact_id,
                owner_id=owner_id,
                title=title,
                instruction=instruction,
                trigger_kind=trigger_kind,
                cadence=cadence if trigger_kind == "recurring" else None,
                cron_expr=cron_expr,
                run_at=run_at_dt,
                notify_email=notify_email,
                notify_telegram=notify_telegram,
                notify_chat=True,
                mode=mode,
            )
        if job is None:
            return "Fehler: Aufgabe konnte nicht angelegt werden."
        return f"Aufgabe „{title}“ angelegt ({trigger_kind})."

    async def list_jobs() -> str:
        """Listet die geplanten Aufgaben dieser Instanz (mit id für cancel_job)."""
        async with SessionLocal() as db:
            jobs = await jobs_svc.list_for_artifact(db, artifact_id, owner_id)
        if not jobs:
            return "Keine geplanten Aufgaben."
        return "\n".join(
            f"- {j.title} [{j.status}] id={j.id} nächster Lauf: {j.next_run_at}" for j in jobs
        )

    async def cancel_job(job_id: str) -> str:
        """Bricht eine geplante Aufgabe dieser Instanz ab (job_id aus list_jobs)."""
        try:
            jid = UUID(job_id)
        except ValueError:
            return "Fehler: ungültige job_id."
        async with SessionLocal() as db:
            ok = await jobs_svc.cancel_job(db, jid, owner_id)
        return "Aufgabe abgebrochen." if ok else "Fehler: Aufgabe nicht gefunden."

    return [schedule_job, list_jobs, cancel_job]


def publish_tools(*, artifact_id: UUID, owner_id: UUID) -> list:
    """Tool, mit dem der Agent die aktuelle Seite per SFTP veroeffentlicht (nach Bestaetigung)."""
    from app.db.session import SessionLocal
    from app.services import sftp_publish

    async def publish_site() -> str:
        """Veroeffentlicht die aktuelle Seite dieser Instanz auf dem hinterlegten SFTP-Server.
        Erst aufrufen, wenn der Nutzer ausdruecklich zugestimmt hat."""
        async with SessionLocal() as db:
            _ok, msg = await sftp_publish.publish_artifact(db, artifact_id, owner_id)
        return msg

    return [publish_site]


def wordpress_tools(*, artifact_id: UUID, owner_id: UUID) -> list:
    """Tool: aktuelle Seite als WordPress-Beitrag veröffentlichen (nach Bestätigung)."""
    from app.db.session import SessionLocal
    from app.services import wordpress_publish

    async def wordpress_publish_tool(title: str, status: str = "draft") -> str:
        """Veröffentlicht die aktuelle Seite als WordPress-Beitrag (Entwurf oder publish).
        Erst aufrufen, wenn der Nutzer ausdrücklich zugestimmt hat.

        Args:
            title: Titel des Beitrags.
            status: "draft" (Entwurf) oder "publish" (sofort sichtbar).
        """
        async with SessionLocal() as db:
            _ok, msg = await wordpress_publish.publish_post(
                db, artifact_id, owner_id, title=title, status=status
            )
        return msg

    wordpress_publish_tool.__name__ = "wordpress_publish"
    return [wordpress_publish_tool]


def google_calendar_tools(*, artifact_id, owner_id) -> list:
    """Tools für die Google-Kalender-Verbindung der Instanz (Token via OAuth-Service)."""
    from app.db.session import SessionLocal
    from app.services import google_oauth as go

    async def calendar_list_events(time_min: str = "", time_max: str = "") -> str:
        """Listet kommende Termine aus dem Google Kalender (ISO-Zeiten optional)."""
        async with SessionLocal() as db:
            token = await go.get_valid_access_token(db, artifact_id, owner_id)
        if not token:
            return "Keine Google-Kalender-Verbindung. Bitte im Verbindungen-Tab verbinden."
        from app.core import clock

        params = {"singleEvents": "true", "orderBy": "startTime", "maxResults": "10"}
        # Default „kommende Termine" = ab JETZT (Systemuhr) — sonst listet Google ab dem
        # ältesten Eintrag. Der Agent kann time_min/time_max für »diese Woche« überschreiben.
        params["timeMin"] = time_min or clock.now_utc().isoformat()
        if time_max:
            params["timeMax"] = time_max
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.get(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    headers={"Authorization": f"Bearer {token}"}, params=params,
                )
                r.raise_for_status()
                items = r.json().get("items", [])
        except Exception:
            return "Kalender konnte nicht geladen werden."
        if not items:
            return "Keine Termine gefunden."
        return "\n".join(
            f"- {e.get('summary', '(ohne Titel)')}: "
            f"{(e.get('start') or {}).get('dateTime') or (e.get('start') or {}).get('date', '')}"
            for e in items
        )

    async def calendar_create_event(title: str, start: str, end: str, description: str = "") -> str:
        """Legt einen Termin an. start/end als ISO-Zeit (z.B. 2026-06-17T10:00:00+02:00)."""
        async with SessionLocal() as db:
            token = await go.get_valid_access_token(db, artifact_id, owner_id)
        if not token:
            return "Keine Google-Kalender-Verbindung. Bitte im Verbindungen-Tab verbinden."
        body = {
            "summary": title, "description": description,
            "start": {"dateTime": start}, "end": {"dateTime": end},
        }
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    headers={"Authorization": f"Bearer {token}"}, json=body,
                )
                r.raise_for_status()
        except Exception:
            return "Termin konnte nicht angelegt werden."
        return f"Termin „{title}“ angelegt."

    calendar_list_events.__name__ = "calendar_list_events"
    calendar_create_event.__name__ = "calendar_create_event"
    return [calendar_list_events, calendar_create_event]


def gmail_tools(*, artifact_id, owner_id) -> list:
    import base64
    from app.db.session import SessionLocal
    from app.services import google_oauth as go

    _API = "https://gmail.googleapis.com/gmail/v1/users/me"

    async def gmail_search(query: str = "", max_results: int = 5) -> str:
        """Durchsucht/liest die letzten Gmail-Nachrichten (Gmail-Suchsyntax in query)."""
        async with SessionLocal() as db:
            token = await go.get_valid_access_token(db, artifact_id, owner_id, "gmail")
        if not token:
            return "Keine Gmail-Verbindung. Bitte im Verbindungen-Tab verbinden."
        h = {"Authorization": f"Bearer {token}"}
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.get(f"{_API}/messages", headers=h,
                                params={"q": query, "maxResults": str(max_results)})
                r.raise_for_status(); ids = [m["id"] for m in r.json().get("messages", [])]
                out = []
                for mid in ids[:max_results]:
                    rm = await c.get(f"{_API}/messages/{mid}", headers=h,
                                     params={"format": "metadata",
                                             "metadataHeaders": ["From", "Subject"]})
                    rm.raise_for_status(); m = rm.json()
                    hdr = {x["name"]: x["value"] for x in (m.get("payload", {}).get("headers", []))}
                    out.append(f"- Von {hdr.get('From','?')} | {hdr.get('Subject','(ohne Betreff)')} | {m.get('snippet','')[:120]}")
        except Exception:
            return "Gmail konnte nicht geladen werden."
        return "\n".join(out) if out else "Keine Nachrichten gefunden."

    async def gmail_send(to: str, subject: str, body: str) -> str:
        """Sendet eine E-Mail. NUR nach ausdrücklicher Bestätigung des Nutzers aufrufen."""
        async with SessionLocal() as db:
            token = await go.get_valid_access_token(db, artifact_id, owner_id, "gmail")
        if not token:
            return "Keine Gmail-Verbindung. Bitte im Verbindungen-Tab verbinden."
        # Header-Injektion verhindern: CR/LF aus To/Subject entfernen (sonst könnte ein
        # via gmail_search eingeschleuster Betreff/Empfänger zusätzliche Header wie Bcc
        # injizieren). EmailMessage kodiert Header/Body korrekt (UTF-8, RFC 2047).
        from email.message import EmailMessage

        def _hdr(v: str) -> str:
            return (v or "").replace("\r", " ").replace("\n", " ")

        em = EmailMessage()
        em["To"] = _hdr(to)
        em["Subject"] = _hdr(subject)
        em.set_content(body or "")
        raw = base64.urlsafe_b64encode(em.as_bytes()).decode()
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(f"{_API}/messages/send",
                                 headers={"Authorization": f"Bearer {token}"}, json={"raw": raw})
                r.raise_for_status()
        except Exception:
            return "E-Mail konnte nicht gesendet werden."
        return "E-Mail gesendet."

    gmail_search.__name__ = "gmail_search"
    gmail_send.__name__ = "gmail_send"
    return [gmail_search, gmail_send]


def slot_tools(*, artifact_id: UUID, owner_id: UUID) -> list:
    """Tools, mit denen der Agent die Seite slot-weise pflegt (eigene DB-Session je Aufruf)."""
    from app.db.session import SessionLocal
    from app.services import canvas_slots

    async def update_slot(slot_id: str, title: str, body: str) -> str:
        """Lege/aktualisiere einen Abschnitt (Slot) der Seite. body = HTML.
        Ein Slot pro Thema/Repo (slot_id z.B. 'repo:<name>') — nicht alles in einen Slot.
        Andere Slots bleiben unberuehrt — so waechst die Seite, statt ueberschrieben zu werden."""
        async with SessionLocal() as db:
            data = await canvas_slots.upsert_slot(
                db, artifact_id, owner_id, slot_id=slot_id, title=title, body=body
            )
        return "Abschnitt gespeichert." if data is not None else "Instanz nicht gefunden."

    async def remove_slot(slot_id: str) -> str:
        """Entferne einen Abschnitt (Slot) der Seite. Nur auf ausdruecklichen Wunsch."""
        async with SessionLocal() as db:
            data = await canvas_slots.remove_slot(db, artifact_id, owner_id, slot_id)
        return "Abschnitt entfernt." if data is not None else "Instanz nicht gefunden."

    update_slot.__name__ = "update_slot"
    remove_slot.__name__ = "remove_slot"
    return [update_slot, remove_slot]


def image_tools(*, artifact_id: UUID, owner_id: UUID) -> list:
    """Tool, mit dem der Agent ein Bild erzeugt (gpt-image-1) und in die Seite einbettet."""
    from app.db.session import SessionLocal

    async def generate_image(prompt: str) -> str:
        """Erzeugt ein Bild aus der Beschreibung (prompt) und gibt die Bild-URL zurueck.
        Bette das Bild danach mit <img src='<url>' alt='...'> in die Seite/einen Slot ein."""
        from decimal import Decimal
        from app.db.models import User
        from app.services import billing, image_gen
        async with SessionLocal() as db:
            user = await db.get(User, owner_id)
            if user is None or (user.balance_usd or Decimal("0")) <= 0:
                return "💳 Dein Guthaben ist aufgebraucht. Bitte lade es auf, um Bilder zu erzeugen."
        url = await image_gen.generate(prompt)
        if not url:
            return "Bild konnte nicht erzeugt werden (Bildgenerierung evtl. nicht eingerichtet)."
        async with SessionLocal() as db:
            await billing.charge_for_image(db, artifact_id=artifact_id, owner_id=owner_id)
            await db.commit()
        return (
            f"NEUES Bild erzeugt unter dieser EINZIGARTIGEN URL:\n{url}\n\n"
            f"Bette GENAU diese URL ein: <img src='{url}' alt='Bild' style='max-width:100%'>. "
            "WICHTIG: Verwende EXAKT diese URL — NIEMALS eine ältere/andere Bild-URL aus der "
            "bisherigen Seite kopieren. Jedes erzeugte Bild hat eine eigene, neue URL."
        )

    generate_image.__name__ = "generate_image"
    return [generate_image]


def slot_etiquette() -> str:
    """System-Prompt-Zusatz fuer Slots-Modus: Seite per Slot-Tools pflegen, kein Canvas-Block."""
    return (
        "SEITE PFLEGEN (SLOTS): Die rechte Seite besteht aus Abschnitten (Slots). Lege je "
        "Thema/Objekt einen EIGENEN Slot an — z.B. EIN Slot pro Repo mit slot_id "
        "'repo:<name>'. Packe NICHT alles in einen einzigen Slot (z.B. 'uebersicht'), "
        "sondern verteile die Infos auf je einen Slot pro Thema. Aktualisiere bestehende "
        "Slots per gleicher slot_id — so BAUST DU AUF, statt zu ueberschreiben. Loesche "
        "fremde Slots nur auf ausdruecklichen Wunsch. Gib KEINEN ```canvas```-Block aus.\n\n"
        "AKTIONS-BUTTONS: Du kannst in einen Slot einen Button legen: "
        "<button data-action=\"<klare Anweisung>\">Label</button>. Beim Klick wird die Anweisung als "
        "Chat-Nachricht an dich geschickt und du fuehrst sie mit deinen Werkzeugen aus. Lege Buttons "
        "nur fuer Aktionen an, die du auch ausfuehren kannst (z.B. 'Auf WordPress veroeffentlichen').\n\n"
    )


def publish_etiquette() -> str:
    """System-Prompt-Zusatz fuer Agenten mit Veroeffentlichungs-Werkzeug: erst fragen."""
    return (
        "VEROEFFENTLICHEN: Du hast ein Werkzeug, um die aktuelle Seite zu veroeffentlichen "
        "(z. B. auf den eigenen Server oder die WordPress-Seite des Nutzers). Rufe es ERST "
        "auf, wenn der Nutzer ausdruecklich zugestimmt hat. "
        "Veroeffentlichen geht AUSSCHLIESSLICH ueber dieses Werkzeug: Wenn der Nutzer "
        "veroeffentlichen will, RUFE DAS WERKZEUG AUF. Gib NIEMALS manuelle Anweisungen "
        "('in den Admin-Bereich kopieren' o.ae.) und behaupte NIEMALS, ein Beitrag sei "
        "veroeffentlicht oder kopiert, ohne dass das Werkzeug eine Erfolgsmeldung "
        "zurueckgegeben hat. Melde dem Nutzer exakt das Ergebnis des Werkzeugs: bei Erfolg "
        "den Link, bei Fehler die Fehlermeldung (rate nicht). Ist keine Verbindung "
        "hinterlegt, weise den Nutzer auf 'Verbindung' rechts hin.\n\n"
    )


def build_tools(*, artifact_id: UUID, owner_id: UUID, allow_scheduling: bool = False) -> list:
    """Baut die Tool-Liste für einen tool-fähigen Agenten.

    Immer: Web-Tools. Bei `allow_scheduling=True` zusätzlich die an die Instanz
    gebundenen Scheduling-Tools (nur im Chat-Pfad, nicht in automatischen Job-Läufen).
    """
    tools = [web_search, web_fetch]
    if allow_scheduling:
        tools += _scheduling_tools(artifact_id, owner_id)
    return tools


def cron_from_local(
    cadence: str, hour: int, tz: str, *, minute: int = 0, ref: datetime | None = None
) -> str:
    """Cron-Ausdruck (UTC) aus lokaler Kadenz/Uhrzeit. 'hourly' nutzt nur die Minute.

    Stunde+Minute werden mit dem Zeitzonen-Offset am Stichtag `ref` (Default: jetzt) nach
    UTC umgerechnet — über DST-Grenzen kann der lokale Lauf um eine Stunde driften (v1-Limitation).
    """
    m = max(0, min(59, minute))
    if cadence == "hourly":
        return f"{m} * * * *"
    h = max(0, min(23, hour))
    from app.core import clock

    z = ZoneInfo(tz)
    ref = ref or clock.now_local(tz)
    local = ref.astimezone(z).replace(hour=h, minute=m, second=0, microsecond=0)
    utc = local.astimezone(UTC)
    if cadence == "weekly":
        return f"{utc.minute} {utc.hour} * * 1"
    return f"{utc.minute} {utc.hour} * * *"  # daily (Default)


def run_at_from_local(local_iso: str, tz: str) -> datetime:
    """Lokale ISO-Zeit 'YYYY-MM-DDTHH:MM' → UTC-aware datetime (für einmalige Jobs)."""
    naive = datetime.fromisoformat(local_iso)
    return naive.replace(tzinfo=ZoneInfo(tz)).astimezone(UTC)
