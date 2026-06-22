async def _make_agent(client):
    r = await client.post(
        "/agents",
        json={
            "name": "Echo Agent",
            "system_prompt": "Reply",
            "model": "claude-haiku-4-5",
            "visibility": "public",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_work_create_and_get(client):
    agent = await _make_agent(client)
    payload = {
        "title": "Test Work",
        "goal": "Echo test",
        "initial_message": "Hi",
        "mode": "single",
        "agents": [{"agent_id": agent["id"]}],
    }
    r = await client.post("/works", json=payload)
    assert r.status_code == 201, r.text
    work = r.json()
    assert work["title"] == "Test Work"
    assert work["estimated_cost_usd"] >= 0

    r = await client.get(f"/works/{work['id']}")
    assert r.status_code == 200
    assert r.json()["agents"][0]["agent_id"] == agent["id"]


async def test_work_copy(client):
    agent = await _make_agent(client)
    r = await client.post(
        "/works",
        json={
            "title": "Src",
            "goal": "g",
            "initial_message": "m",
            "mode": "single",
            "agents": [{"agent_id": agent["id"]}],
            "visibility": "public",
        },
    )
    work = r.json()
    r = await client.post(f"/works/{work['id']}/copy")
    assert r.status_code == 201
    assert r.json()["title"].startswith("Copy: ")
