from __future__ import annotations
from uuid import uuid4, UUID
import pytest
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import User
from app.services import roles


@pytest.mark.asyncio
async def test_put_topup_mode_goa_only(client, monkeypatch):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        target = User(email=f"t-{uuid4()}@x.de", google_sub=str(uuid4()), name="Target")
        db.add(target); await db.commit(); tid = str(target.id)
    # Non-GOA caller → 403 (admin_email is the real default, test user is test@local)
    r = await client.put(f"/admin/users/{tid}/topup-mode", json={"mode": "real"})
    assert r.status_code == 403
    # Make the auth test user GOA by pointing admin_email at its existing email
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")
    r = await client.put(f"/admin/users/{tid}/topup-mode", json={"mode": "real"})
    assert r.status_code == 200 and r.json()["ok"] is True
    async with SessionLocal() as db:
        assert (await db.get(User, UUID(tid))).topup_mode == "real"
    # invalid enum value → 422
    assert (await client.put(f"/admin/users/{tid}/topup-mode", json={"mode": "x"})).status_code == 422
