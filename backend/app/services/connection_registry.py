"""Kuratierte Registry der Verbindungs-Typen (kind → Felder + Geheimnis-Label).

Single Source of Truth für die nicht-geheimen Felder je Verbindung; treibt sowohl
die Backend-Validierung als auch (gespiegelt) die generischen Formulare im Frontend.
Das Geheimnis selbst wird getrennt + verschlüsselt gespeichert (nicht hier)."""

from __future__ import annotations

CONNECTIONS: list[dict] = [
    {
        "kind": "sftp",
        "name": "SFTP-Server",
        "fields": [
            {"key": "host", "label": "Host", "type": "text"},
            {"key": "port", "label": "Port", "type": "number", "default": 22},
            {"key": "username", "label": "Benutzer", "type": "text"},
            {"key": "remote_path", "label": "Zielpfad", "type": "text"},
        ],
        "secret_label": "Passwort",
    },
    {
        "kind": "wordpress",
        "name": "WordPress",
        "fields": [
            {"key": "site_url", "label": "Seiten-URL (https://…)", "type": "text"},
            {"key": "username", "label": "Benutzer", "type": "text"},
        ],
        "secret_label": "Application Password",
    },
    {
        "kind": "google_calendar",
        "name": "Google Kalender",
        "auth": "oauth",
        "provider": "google",
        "scopes": ["https://www.googleapis.com/auth/calendar.events"],
    },
    {
        "kind": "gmail", "name": "Gmail", "auth": "oauth", "provider": "google",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly",
                   "https://www.googleapis.com/auth/gmail.send"],
    },
]


def _normalize(entry: dict) -> dict:
    """Liefert den Eintrag mit explizitem `auth` (Default "fields").

    Feld-basierte Verbindungen (sftp, wordpress) haben kein `auth`-Feld und gelten
    implizit als "fields"; OAuth-Arten (google_calendar) tragen `auth:"oauth"`."""
    out = dict(entry)
    out.setdefault("auth", "fields")
    return out


_BY_KIND: dict[str, dict] = {c["kind"]: _normalize(c) for c in CONNECTIONS}


def list_connections() -> list[dict]:
    return [_normalize(c) for c in CONNECTIONS]


def get(kind: str) -> dict | None:
    return _BY_KIND.get(kind)


def is_valid(kind: str) -> bool:
    return kind in _BY_KIND


def kinds() -> list[str]:
    return [c["kind"] for c in CONNECTIONS]
