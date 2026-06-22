async def test_agent_crud_flow(client):
    payload = {
        "name": "Research Bot",
        "description": "Sucht Quellen",
        "domain": "research",
        "system_prompt": "Du bist ein Recherche-Assistent.",
        "model": "claude-sonnet-4-6",
        "skills": ["research", "summarization"],
        "visibility": "public",
    }
    r = await client.post("/agents", json=payload)
    assert r.status_code == 201, r.text
    agent = r.json()
    assert agent["name"] == "Research Bot"
    assert agent["skills"] == ["research", "summarization"]
    assert agent["rating_count"] == 0

    r = await client.get("/agents")
    assert r.status_code == 200
    assert any(a["id"] == agent["id"] for a in r.json())

    r = await client.patch(f"/agents/{agent['id']}", json={"description": "neu"})
    assert r.status_code == 200
    assert r.json()["description"] == "neu"

    r = await client.delete(f"/agents/{agent['id']}")
    assert r.status_code == 204


async def test_agent_filter_by_skill(client):
    a = await client.post(
        "/agents",
        json={
            "name": "SEO Pro",
            "system_prompt": "x",
            "skills": ["seo"],
            "visibility": "public",
        },
    )
    assert a.status_code == 201
    r = await client.get("/agents", params={"skill": "seo"})
    assert r.status_code == 200
    assert any(a.json()["id"] == x["id"] for x in r.json())


async def test_create_agent_stores_provider_and_encrypts_key(client):
    payload = {
        "name": "Reiseführer",
        "role": "Reiseführer",
        "description": "Plant Reisen und gibt Empfehlungen",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "api_key": "sk-ant-test-XYZ",
        "visibility": "public",
    }
    res = await client.post("/agents", json=payload)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["provider"] == "anthropic"
    assert body["has_api_key"] is True
    assert "api_key" not in body  # Klartext-Key nie ausgeben


async def test_search_matches_expertise_and_description(client):
    await client.post(
        "/agents",
        json={
            "name": "Koch-Bot",
            "role": "Sternekoch",
            "description": "Erstellt Menüs",
            "visibility": "public",
        },
    )
    res = await client.get("/agents", params={"q": "sternekoch"})
    assert res.status_code == 200
    names = [a["name"] for a in res.json()]
    assert "Koch-Bot" in names
