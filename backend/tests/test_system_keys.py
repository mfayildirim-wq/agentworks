from __future__ import annotations

from uuid import uuid4

import pytest

from app.core import crypto
from app.db.models import User
from app.db.session import SessionLocal
from app.services import roles, system_keys


# --- Task 1: deepseek-Spalte -------------------------------------------------


@pytest.mark.asyncio
async def test_user_has_deepseek_key_attribute():
    u = User(email=f"u-{uuid4()}@x.de", google_sub=str(uuid4()), name="X")
    assert u.deepseek_key_encrypted is None


# --- Task 2: system_keys-Service --------------------------------------------


@pytest.mark.asyncio
async def test_set_keys_encrypts_onto_goa(client, monkeypatch):
    await client.get("/artifacts")  # legt den Auth-Test-User an (test@local)
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")
    monkeypatch.setattr(system_keys.settings, "admin_email", "test@local")
    async with SessionLocal() as db:
        await system_keys.set_keys(db, anthropic="sk-ant-XYZ")
    async with SessionLocal() as db:
        goa = await system_keys._goa(db)
        assert goa is not None
        assert goa.anthropic_key_encrypted
        assert goa.anthropic_key_encrypted != "sk-ant-XYZ"
        assert crypto.decrypt(goa.anthropic_key_encrypted) == "sk-ant-XYZ"


@pytest.mark.asyncio
async def test_set_keys_none_keeps_existing(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")
    monkeypatch.setattr(system_keys.settings, "admin_email", "test@local")
    async with SessionLocal() as db:
        await system_keys.set_keys(db, openai="sk-open-1")
        await system_keys.set_keys(db, anthropic="sk-ant-1")  # openai unverändert
    async with SessionLocal() as db:
        goa = await system_keys._goa(db)
        assert crypto.decrypt(goa.openai_key_encrypted) == "sk-open-1"
        assert crypto.decrypt(goa.anthropic_key_encrypted) == "sk-ant-1"


@pytest.mark.asyncio
async def test_system_key_for_prefers_db_then_env(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")
    monkeypatch.setattr(system_keys.settings, "admin_email", "test@local")
    monkeypatch.setattr(system_keys.settings, "deepseek_api_key", "env-deepseek")
    async with SessionLocal() as db:
        # noch kein DB-Key → Env-Fallback
        assert await system_keys.system_key_for(db, "deepseek") == "env-deepseek"
        await system_keys.set_keys(db, deepseek="db-deepseek")
    async with SessionLocal() as db:
        assert await system_keys.system_key_for(db, "deepseek") == "db-deepseek"


@pytest.mark.asyncio
async def test_status_reflects_db_and_env(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")
    monkeypatch.setattr(system_keys.settings, "admin_email", "test@local")
    monkeypatch.setattr(system_keys.settings, "anthropic_api_key", "")
    monkeypatch.setattr(system_keys.settings, "openai_api_key", "")
    monkeypatch.setattr(system_keys.settings, "deepseek_api_key", "env-deepseek")
    async with SessionLocal() as db:
        # GOA-Felder zurücksetzen (DB wird über die Session geteilt → kein impliziter Reset).
        goa = await system_keys._goa(db)
        goa.anthropic_key_encrypted = None
        goa.openai_key_encrypted = None
        goa.deepseek_key_encrypted = None
        await db.commit()
        await system_keys.set_keys(db, anthropic="sk-ant-1")
        st = await system_keys.status(db)
    assert st["anthropic"] is True  # aus DB
    assert st["deepseek"] is True  # aus Env
    assert st["openai"] is False


# --- Task 3: Endpoints (GOA-only) -------------------------------------------


@pytest.mark.asyncio
async def test_get_keys_forbidden_for_non_goa(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(roles.settings, "admin_email", "someone-else@x.de")
    r = await client.get("/system/keys")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_put_keys_forbidden_for_non_goa(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(roles.settings, "admin_email", "someone-else@x.de")
    r = await client.put("/system/keys", json={"deepseek": "x"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_goa_sets_deepseek_and_status_true_no_plaintext(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")
    monkeypatch.setattr(system_keys.settings, "admin_email", "test@local")
    r = await client.put("/system/keys", json={"deepseek": "sk-deep-secret"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["deepseek"] is True
    # NIE Klartext in der Response
    assert "sk-deep-secret" not in r.text
    r2 = await client.get("/system/keys")
    assert r2.status_code == 200
    assert r2.json()["deepseek"] is True
    assert "sk-deep-secret" not in r2.text


# --- Task 4: persönliche Keys aus dem Profil entfernt ------------------------


@pytest.mark.asyncio
async def test_profile_has_no_personal_key_fields(client):
    await client.get("/artifacts")
    r = await client.get("/profile")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "has_openai_key" not in body
    assert "has_anthropic_key" not in body


@pytest.mark.asyncio
async def test_profile_update_without_keys(client):
    await client.get("/artifacts")
    r = await client.put("/profile", json={"name": "Neuer Name"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Neuer Name"
    # persönliche Key-Felder werden nicht mehr akzeptiert/zurückgegeben
    assert "openai_key" not in r.json()
