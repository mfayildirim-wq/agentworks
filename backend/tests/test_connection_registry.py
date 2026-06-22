"""Tests für die Verbindungs-Registry (Felder je kind)."""

from __future__ import annotations

from app.services import connection_registry as reg


def test_sftp_and_wordpress_valid():
    assert reg.is_valid("sftp") is True
    assert reg.is_valid("wordpress") is True
    assert reg.is_valid("nope") is False


def test_get_wordpress_fields():
    entry = reg.get("wordpress")
    assert entry is not None
    field_keys = [f["key"] for f in entry["fields"]]
    assert "site_url" in field_keys and "username" in field_keys
    assert entry["secret_label"]


def test_kinds_lists_both():
    assert set(reg.kinds()) >= {"sftp", "wordpress"}
