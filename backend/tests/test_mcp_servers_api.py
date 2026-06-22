"""Tests für die Admin-MCP-Katalog-Endpoints."""

from __future__ import annotations


async def test_list_servers_authed(client):
    r = await client.get("/mcp-servers")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_crud_requires_admin(client):
    # Test-User test@local ist kein Admin => 403
    r = await client.post("/mcp-servers", json={
        "server_id": "x", "name": "X", "description": "", "transport": "sse",
        "url": "http://x", "requires_credential": False,
    })
    assert r.status_code == 403, r.text


async def test_admin_crud_happy_path(client, monkeypatch):
    import app.auth.dependencies as deps
    monkeypatch.setattr(deps.settings, "admin_email", "test@local")

    create = await client.post("/mcp-servers", json={
        "server_id": "wetter", "name": "Wetter", "description": "d",
        "transport": "sse", "url": "http://wetter/sse", "requires_credential": False,
    })
    assert create.status_code == 201, create.text
    assert create.json()["server_id"] == "wetter"

    lst = await client.get("/mcp-servers")
    assert any(s["server_id"] == "wetter" for s in lst.json())

    upd = await client.put("/mcp-servers/wetter", json={"enabled": False})
    assert upd.status_code == 200 and upd.json()["enabled"] is False

    dup = await client.post("/mcp-servers", json={
        "server_id": "wetter", "name": "X", "description": "", "transport": "sse",
        "url": "http://x", "requires_credential": False,
    })
    assert dup.status_code == 409

    dele = await client.delete("/mcp-servers/wetter")
    assert dele.status_code == 204
