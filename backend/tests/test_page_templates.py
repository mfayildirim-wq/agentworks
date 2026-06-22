from app.services import page_templates


def test_list_all_has_placeholders():
    items = page_templates.list_all()
    names = {t["name"] for t in items}
    assert "journal" in names and "studio" in names
    j = next(t for t in items if t["name"] == "journal")
    assert {p["key"] for p in j["placeholders"]} >= {"title", "intro"}


def test_render_fills_inlines_sanitizes():
    html = page_templates.render("journal", {"title": "Hallo", "intro": "<b>ok</b><script>x()</script>"})
    assert "Hallo" in html
    assert "<script>x()" not in html        # body value sanitized
    assert "<link" not in html.lower()        # css inlined, no <link>
    assert "journal_js.js" not in html        # js inlined, no external src
    assert "{{title}}" not in html and "{{" not in html
    assert "<!doctype" in html.lower()


def test_render_missing_placeholder_empty():
    html = page_templates.render("journal", {})
    assert "{{" not in html


def test_get_unknown_none():
    assert page_templates.get("nope") is None
