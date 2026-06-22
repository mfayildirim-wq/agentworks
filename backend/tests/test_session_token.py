"""Tests für das langlebige Backend-Session-Token (Fernet, ersetzt den 1h-Google-Token)."""

from __future__ import annotations

from app.auth.session_token import issue_session_token, read_session_token


def test_round_trip_returns_claims():
    tok = issue_session_token({"sub": "123", "email": "a@b.de", "name": "A", "picture": None})
    claims = read_session_token(tok)
    assert claims is not None
    assert claims["sub"] == "123"
    assert claims["email"] == "a@b.de"


def test_fresh_within_ttl_ok():
    tok = issue_session_token({"sub": "123", "email": "a@b.de"}, now=1000)
    claims = read_session_token(tok, max_age_seconds=60, now=1030)
    assert claims is not None
    assert claims["sub"] == "123"


def test_expired_token_returns_none():
    tok = issue_session_token({"sub": "123", "email": "a@b.de"}, now=1000)
    assert read_session_token(tok, max_age_seconds=60, now=1061) is None


def test_garbage_token_returns_none():
    assert read_session_token("not-a-real-token") is None


def test_google_like_jwt_returns_none():
    # Ein Google id_token (JWT) ist kein Fernet-Token -> None (HTTP-Fallback greift dann).
    assert read_session_token("eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxIn0.sig") is None
