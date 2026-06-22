from app.services.canvas_render import sanitize_html, render_static


def test_sanitize_removes_script_and_handlers():
    dirty = '<p onclick="x()">hi</p><script>alert(1)</script><a href="javascript:1">l</a>'
    out = sanitize_html(dirty)
    assert "<script" not in out.lower()
    assert "onclick" not in out.lower()
    assert "javascript:" not in out.lower()
    assert "hi" in out


def test_sanitize_keeps_action_button_drops_handlers():
    out = sanitize_html('<button data-action="Sag Hallo">Hi</button><button onclick="e()">B</button>')
    assert "data-action" in out
    assert "Sag Hallo" in out
    assert "onclick" not in out.lower()
    assert "<button" in out.lower()
    assert "<script" not in out.lower()


def test_render_static_sections_has_toc_no_script():
    data = {"layout": "sections", "slots": [
        {"id": "a", "title": "Alpha", "type": "richtext", "order": 0, "body": "<p>A</p>"},
        {"id": "b", "title": "Beta", "type": "richtext", "order": 1, "body": "<p>B</p>"},
    ]}
    html = render_static(data)
    assert "<script" not in html.lower()
    assert 'id="a"' in html and 'id="b"' in html
    assert 'href="#a"' in html


def test_render_static_tabs_css_only():
    data = {"layout": "tabs", "slots": [
        {"id": "a", "title": "Alpha", "type": "richtext", "order": 0, "body": "<p>A</p>"},
    ]}
    html = render_static(data)
    assert "<script" not in html.lower()
    assert "Alpha" in html


def test_render_static_empty():
    html = render_static({"layout": "sections", "slots": []})
    assert "<script" not in html.lower()
    assert "<!doctype" in html.lower()


def test_sanitize_strips_script_from_slot_body_in_render():
    data = {"layout": "sections", "slots": [
        {"id": "a", "title": "A", "type": "richtext", "order": 0, "body": "<p>ok</p><script>bad()</script>"},
    ]}
    html = render_static(data)
    assert "bad()" not in html
    assert "<script" not in html.lower()


def test_render_static_magazine_uses_design_css():
    data = {"layout": "sections", "slots": [
        {"id": "a", "title": "Alpha", "type": "richtext", "order": 0, "body": "<p>x</p>"}]}
    html = render_static(data, "magazine")
    assert "<script" not in html.lower()
    assert "linear-gradient" in html  # magazine hero gradient from its CSS
    assert 'class="card"' in html     # magazine card structure
    assert "Alpha" in html


def test_render_static_cards_structure():
    data = {"layout": "sections", "slots": [
        {"id": "a", "title": "Alpha", "type": "richtext", "order": 0, "body": "<p>x</p>"}]}
    html = render_static(data, "cards")
    assert 'class="grid"' in html and 'class="tile"' in html
    assert "<script" not in html.lower()


def test_render_static_unknown_design_fallback():
    data = {"layout": "sections", "slots": []}
    html = render_static(data, "nope")
    assert "<!doctype" in html.lower()  # kein Crash, Fallback
