from app.services.agents import compose_system_prompt


def test_compose_system_prompt_from_skills():
    p = compose_system_prompt(
        role="Softwareentwickler",
        domain="software",
        skills=["java", "spring"],
        description="10 Jahre Erfahrung.",
    )
    assert "Softwareentwickler" in p
    assert "software" in p
    assert "java" in p and "spring" in p
    assert "10 Jahre Erfahrung." in p


async def test_create_agent_without_system_prompt(client):
    r = await client.post(
        "/agents",
        json={
            "name": "Java-Dev",
            "role": "Softwareentwickler",
            "domain": "software",
            "description": "Backend-Spezialist.",
            "skills": ["java", "spring"],
            "visibility": "public",
        },
    )
    assert r.status_code == 201, r.text
    agent = r.json()
    assert "java" in agent["system_prompt"].lower()
    assert agent["skills"] == ["java", "spring"]


async def test_agent_works_empty(client):
    r = await client.post(
        "/agents",
        json={"name": "Solo", "role": "x", "skills": ["a"], "visibility": "public"},
    )
    aid = r.json()["id"]
    w = await client.get(f"/agents/{aid}/works")
    assert w.status_code == 200
    assert w.json() == []
