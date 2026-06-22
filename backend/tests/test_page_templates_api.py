from __future__ import annotations


async def test_endpoint_lists_prepared_templates(client):
    r = await client.get("/page-templates")
    assert r.status_code == 200, r.text
    items = r.json()
    names = {t["name"] for t in items}
    assert "journal" in names and "studio" in names
    for t in items:
        assert t["label"] and "description" in t
        assert isinstance(t["placeholders"], list)
    journal = next(t for t in items if t["name"] == "journal")
    assert {p["key"] for p in journal["placeholders"]} >= {"title", "intro"}
