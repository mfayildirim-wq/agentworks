"""Tests für die gemeinsame Datei-Text-Extraktion."""

from __future__ import annotations

from app.services import file_text


def test_txt_is_decoded():
    assert file_text.extract_text("notizen.txt", "Hallo Welt".encode()) == "Hallo Welt"


def test_md_is_decoded():
    assert "Überschrift" in file_text.extract_text("readme.md", "# Überschrift".encode())


def test_csv_is_decoded():
    out = file_text.extract_text("daten.csv", b"a,b\n1,2")
    assert "a,b" in out and "1,2" in out


def test_unknown_type_returns_empty_string():
    assert file_text.extract_text("foto.png", b"\x89PNG\r\n") == ""


def test_invalid_utf8_does_not_raise():
    assert file_text.extract_text("x.txt", b"\xff\xfeok") == "ok"
