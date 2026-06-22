"""Integrationstests: Google-Token gegen langlebiges Backend-Session-Token tauschen."""

from __future__ import annotations

import pytest

from app.auth import dependencies as deps


@pytest.fixture
def real_auth(monkeypatch):
    """Aktiviert die echte Auth (statt Test-Bypass) und ersetzt die Google-Prüfung."""
    monkeypatch.setattr(deps.settings, "auth_disabled_for_tests", False)

    async def fake_verify(token: str) -> dict:
        if token == "expired":
            raise ValueError("Token expired, 1 < 2")
        return {"sub": "g-sub-1", "email": "u@ex.de", "name": "U", "picture": None}

    monkeypatch.setattr(deps, "_verify_google_token", fake_verify)


@pytest.mark.asyncio
async def test_exchange_returns_backend_token_and_is_accepted(client, real_auth):
    r = await client.post("/auth/session", json={"id_token": "google-xyz"})
    assert r.status_code == 200
    token = r.json()["token"]
    assert token

    # Das Backend-Token wird als Bearer akzeptiert (kein Google-Call mehr nötig).
    r2 = await client.get("/artifacts", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_expired_google_token_is_rejected(client, real_auth):
    r = await client.get("/artifacts", headers={"Authorization": "Bearer expired"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_missing_bearer_is_rejected(client, real_auth):
    r = await client.get("/artifacts")
    assert r.status_code == 401
