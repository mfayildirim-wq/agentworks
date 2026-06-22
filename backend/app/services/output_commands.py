"""Befehls-Registry fürs '/'-Menü: was es je Ausgabe-Typ gibt (Modi + Aktionen)."""
from __future__ import annotations

_COMMON = [
    {"key": "hinzufuegen", "label": "Neuer Tab (Standard)", "kind": "mode"},
    {"key": "liste", "label": "Liste (verlinkt, neue oben)", "kind": "mode"},
    {"key": "oben", "label": "Oben anfügen", "kind": "mode"},
    {"key": "unten", "label": "Unten anfügen", "kind": "mode"},
    {"key": "ueberarbeiten", "label": "Aktuellen Tab überarbeiten", "kind": "mode"},
    {"key": "ueberschreiben", "label": "Alles überschreiben", "kind": "mode"},
    {"key": "abschnitte", "label": "Einträge verwalten", "kind": "action"},
    {"key": "refresh", "label": "Seite aktualisieren", "kind": "action"},
]
_BY_TYPE = {"page": [], "image": [], "data": []}
_MODES = {c["key"] for c in _COMMON if c["kind"] == "mode"}
# Reservierte System-Keys: Template-eigene „/"-Funktionen dürfen keinen davon belegen.
SYSTEM_KEYS = {c["key"] for c in _COMMON}


def kinds(output_type: str = "page") -> list[dict]:
    return _COMMON + _BY_TYPE.get(output_type, [])


def is_mode(key: str) -> bool:
    return key in _MODES


def is_system_key(key: str) -> bool:
    return key in SYSTEM_KEYS
