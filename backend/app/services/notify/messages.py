"""Reine Bau-Funktionen für Benachrichtigungstexte (kein I/O, direkt testbar)."""

from __future__ import annotations


def update_subject(title: str, version_no: int) -> str:
    return f"🔄 {title} aktualisiert (v{version_no})"


def update_body(title: str, version_no: int, url: str) -> str:
    return (
        f"Deine Seite „{title}“ wurde gerade aktualisiert (Version {version_no}).\n\n"
        f"Ansehen: {url}"
    )


def update_chat_text(title: str, version_no: int, url: str) -> str:
    return (
        f"🔄 Automatische Aktualisierung: „{title}“ ist jetzt auf Version {version_no}. "
        f"Ansehen: {url}"
    )


def reminder_subject(title: str) -> str:
    return f"🔔 {title}"


def reminder_chat_text(text: str) -> str:
    """Bereinigt den Agenten-Text für die Zustellung als Nachricht (kein I/O)."""
    t = (text or "").strip()
    if t.startswith("```"):
        # Codeblock-Zaun entfernen, falls der Agent doch einen geliefert hat.
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()
