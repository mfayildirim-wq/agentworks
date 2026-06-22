# backend/tests/test_canvas_render_tabs.py
from app.services.canvas_render import render_static

DATA = {"layout": "tabs", "slots": [
    {"id": "n", "title": "Neu",  "order": 0, "body": "<p>NEU</p>"},
    {"id": "a", "title": "Alt",  "order": 1, "body": "<p>ALT</p>"}]}


def test_tabs_include_design_structure_cards():
    html = render_static(DATA, "cards")
    assert ".tabbar" in html                     # neue Button-Bar vorhanden
    assert ".tile" in html or ".grid" in html    # cards-Design-CSS vorhanden
    assert "class=\"tile\"" in html              # Panel nutzt Design-Struktur


def test_tabs_first_panel_is_newest():
    html = render_static(DATA, "")
    assert html.index("NEU") < html.index("ALT")  # neuester Tab zuerst (links/aktiv)


def test_tabbar_structure_and_scrollbar_free():
    html = render_static(DATA, "")
    # scrollbare Button-Leiste statt klassischer Tabs
    assert '<nav class="tabbar">' in html
    assert "overflow-x:auto" in html
    assert "scrollbar-width:none" in html
    assert "::-webkit-scrollbar" in html


def test_tabs_one_radio_per_slot():
    html = render_static(DATA, "")
    # genau ein echtes radio-Input pro Slot
    assert html.count('<input type="radio"') == 2
    # alle radios teilen sich den name
    assert html.count('name="canvas-tabs"') == 2


def test_tabs_panels_have_panel_ids():
    html = render_static(DATA, "")
    assert 'id="panel-n"' in html
    assert 'id="panel-a"' in html


def test_tabs_per_tab_checked_rules_present():
    html = render_static(DATA, "")
    # je Slot eine Regel, die den passenden Panel bei :checked sichtbar macht
    for sid in ("n", "a"):
        assert f':checked ~ ' in html
        # Panel-Sichtbarkeit per :checked ~ Geschwister-Selektor
        assert 'display: block' in html or 'display:block' in html
    # konkret pro Slot: checked-Regel referenziert das jeweilige Panel
    assert 'tab-n' in html and 'panel-n' in html
    assert 'tab-a' in html and 'panel-a' in html


def test_tabs_active_label_inset_style():
    html = render_static(DATA, "")
    # aktiver Button "reingedrückt": Inset-Schatten
    assert "inset" in html
    assert "box-shadow" in html


def test_tabs_radio_mechanism_intact_first_checked():
    html = render_static(DATA, "")
    # erstes Tab vorausgewählt
    first_input = html.split('<input type="radio"', 1)[1].split(">", 1)[0]
    assert "checked" in first_input
    assert 'id="tab-n"' in first_input
