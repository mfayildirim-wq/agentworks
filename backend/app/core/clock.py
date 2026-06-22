"""Zentrale System-Zeit — die EINZIGE Wahrheitsquelle für „jetzt".

Jeder zeitbezogene Prompt und jede Zeit-Logik MUSS „jetzt" von hier beziehen
(aus der Systemuhr, zeitzonenbewusst) — niemals aus einer Modell-Annahme. So kann
das LLM das aktuelle Datum nicht „raten"; es bekommt es verbindlich aus der App."""
from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.core.settings import get_settings

settings = get_settings()

_WEEKDAYS_DE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag",
]


def now_utc() -> datetime:
    """Aktueller Zeitpunkt, zeitzonenbewusst in UTC (aus der Systemuhr)."""
    return datetime.now(UTC)


def now_local(tz: str | None = None) -> datetime:
    """Aktueller Zeitpunkt in der App-Zeitzone (`settings.default_timezone`) oder `tz`."""
    return now_utc().astimezone(ZoneInfo(tz or settings.default_timezone))


def time_context(name: str | None = None, tz: str | None = None) -> str:
    """Verbindlicher Zeit-Baustein für Prompts: das aktuelle Datum aus der Systemuhr.
    Wird zeitrelevanten Prompts vorangestellt, damit das Modell sich AUSSCHLIESSLICH
    hierauf verlässt statt zu raten."""
    zone = tz or settings.default_timezone
    n = now_local(zone)
    wd = _WEEKDAYS_DE[n.weekday()]
    stamp = n.strftime("%d.%m.%Y, %H:%M")
    name_line = f" Der Nutzer heißt {name.strip()}." if (name or "").strip() else ""
    return (
        f"AKTUELLE ZEIT (verbindlich, aus der Systemuhr — verlass dich NUR hierauf, "
        f"rate NIE ein Datum): {wd}, {stamp} Uhr ({zone}). "
        f"Nutze dieses Datum für »heute/jetzt/diese Woche/morgen« und alle "
        f"Zeitangaben.{name_line}\n\n"
    )
