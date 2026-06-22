from __future__ import annotations


async def test_pricing_public_list(client):
    items = (await client.get("/pricing")).json()
    models = [p["model"] for p in items]
    assert "claude-haiku-4-5" in models
    hp = next(p for p in items if p["model"] == "claude-haiku-4-5")
    # Portalpreis = Provider x 1.30 (25% Portal + 5% Creator)
    assert float(hp["portal_input_per_million_usd"]) == 1.30


async def test_pricing_update_requires_admin(client):
    # Test-User ist test@local (kein Admin) => 403
    r = await client.put(
        "/pricing/claude-haiku-4-5",
        json={"input_per_million_usd": 2, "output_per_million_usd": 8},
    )
    assert r.status_code == 403, r.text
