from __future__ import annotations


def test_registry_has_three_known_templates():
    from app.services import html_templates as ht

    items = ht.list_templates()
    ids = [t["id"] for t in items]
    assert ids == ["classic", "magazine", "cards"]
    for t in items:
        assert t["name"] and t["description"]
        assert t["html"].lstrip().lower().startswith("<!doctype html>")
        # Eingebettetes CSS, kein JavaScript (passt zur Serving-CSP script-src 'none').
        assert "<script" not in t["html"].lower()


def test_each_template_has_clean_css():
    from app.services import html_templates as svc

    for t in svc.list_templates():
        assert t["css"], f"{t['id']} hat kein css"
        assert "<style" not in t["css"].lower()
        assert "</style>" not in t["css"].lower()
        # CSS-Inhalt plausibel (enthält eine Regel)
        assert "{" in t["css"]


def test_is_valid_and_get():
    from app.services import html_templates as ht

    assert ht.is_valid("classic")
    assert ht.is_valid("cards")
    assert not ht.is_valid("")
    assert not ht.is_valid("nope")
    assert ht.get("magazine")["name"]
    assert ht.get("nope") is None


async def test_endpoint_lists_templates_with_html(client):
    r = await client.get("/html-templates")
    assert r.status_code == 200, r.text
    items = r.json()
    assert [t["id"] for t in items] == ["classic", "magazine", "cards"]
    assert all(t["html"].lower().lstrip().startswith("<!doctype html>") for t in items)


async def test_html_templates_api_includes_css(client):
    r = await client.get("/html-templates")
    assert r.status_code == 200, r.text
    items = r.json()
    for t in items:
        assert t["css"], f"{t['id']} hat kein css"


async def test_agent_template_stores_html_template_id(client):
    r = await client.post(
        "/templates/agent-template",
        json={
            "name": "Reiseplaner",
            "prompt": "Plane Reisen.",
            "category": "Everyday",
            "visibility": "public",
            "html_template_id": "magazine",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["config"]["html_template_id"] == "magazine"


async def test_agent_template_rejects_empty_html_template_id(client):
    r = await client.post(
        "/templates/agent-template",
        json={"name": "X", "prompt": "Y", "visibility": "public", "html_template_id": ""},
    )
    assert r.status_code == 422, r.text


async def test_agent_template_rejects_unknown_html_template_id(client):
    r = await client.post(
        "/templates/agent-template",
        json={"name": "X", "prompt": "Y", "visibility": "public", "html_template_id": "bogus"},
    )
    assert r.status_code == 422, r.text


async def test_update_agent_template_changes_html_template_id(client):
    created = await client.post(
        "/templates/agent-template",
        json={
            "name": "Reiseplaner",
            "prompt": "Plane Reisen.",
            "category": "Everyday",
            "visibility": "public",
            "html_template_id": "classic",
        },
    )
    tid = created.json()["id"]
    upd = await client.put(
        f"/templates/agent-template/{tid}",
        json={"html_template_id": "cards"},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["config"]["html_template_id"] == "cards"


async def test_update_agent_template_rejects_unknown_html_template_id(client):
    created = await client.post(
        "/templates/agent-template",
        json={
            "name": "Reiseplaner",
            "prompt": "Plane Reisen.",
            "category": "Everyday",
            "visibility": "public",
            "html_template_id": "classic",
        },
    )
    tid = created.json()["id"]
    upd = await client.put(
        f"/templates/agent-template/{tid}",
        json={"html_template_id": "bogus"},
    )
    assert upd.status_code == 422, upd.text
