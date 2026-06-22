"""JS-freier statischer Renderer + HTML-Sanitizer fuer Canvas-Slots.

Dieser Renderer erzeugt bewusst KEIN ``<script>`` und ist der No-JS-Fallback
fuer die oeffentliche ``/p/``-Seite sowie der in ``artifact_version.content``
gespeicherte statische Snapshot. Die interaktive JS-Variante lebt im Frontend.

``layout == "tabs"``: umgesetzt als reine CSS-Tabs ueber den
Radio-Input-+-``:checked``-Trick (keine JS-Abhaengigkeit). Das erste Tab ist
per ``checked`` vorausgewaehlt.
"""

from __future__ import annotations

import html as _html

import nh3

from app.services import html_templates

# Allowlist fuer den Rich-Text-Body eines Slots.
_ALLOWED_TAGS = {
    "p", "br", "h1", "h2", "h3", "h4", "ul", "ol", "li", "a", "strong",
    "em", "b", "i", "code", "pre", "blockquote", "table", "thead", "tbody",
    "tr", "th", "td", "img", "span", "div", "hr", "button",
}
_ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "button": {"data-action", "class"},
}

_STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
       line-height: 1.6; margin: 0; padding: 1.5rem; max-width: 50rem;
       margin-inline: auto; }
nav.toc { margin-bottom: 2rem; padding: 1rem; border: 1px solid #ddd;
          border-radius: .5rem; }
nav.toc ul { list-style: none; margin: 0; padding: 0; }
nav.toc li { margin: .25rem 0; }
section { margin-bottom: 2.5rem; }
section h2 { border-bottom: 1px solid #eee; padding-bottom: .25rem; }
img { max-width: 100%; height: auto; }
pre { overflow-x: auto; padding: .75rem; background: #f5f5f5; border-radius: .375rem; }
""".strip()

_EMPTY_PLACEHOLDER = "<p>Noch keine Inhalte.</p>"


def sanitize_html(body: str | None) -> str:
    """HTML-Fragment gegen die Allowlist saeubern.

    nh3 entfernt mit dieser Allowlist ``<script>``, ``on*``-Handler und
    ``javascript:``-URLs. ``None`` wird zu ``""``.
    """
    return nh3.clean(body or "", tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS)


def _sorted_slots(data: dict) -> list[dict]:
    slots = data.get("slots") or []
    return sorted(slots, key=lambda s: s.get("order", 0))


def _doc(title: str, body_html: str, css: str = _STYLE) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="de">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_html.escape(title)}</title>\n"
        f"<style>\n{css}\n</style>\n"
        "</head>\n<body>\n"
        f"{body_html}\n"
        "</body>\n</html>\n"
    )


def _render_sections(slots: list[dict]) -> str:
    if not slots:
        return _EMPTY_PLACEHOLDER

    toc_items = []
    sections = []
    for slot in slots:
        sid = _html.escape(str(slot.get("id", "")))
        stitle = _html.escape(str(slot.get("title", "")))
        body = sanitize_html(slot.get("body"))
        toc_items.append(f'<li><a href="#{sid}">{stitle}</a></li>')
        sections.append(
            f'<section id="{sid}"><h2>{stitle}</h2>{body}</section>'
        )

    toc = '<nav class="toc"><ul>' + "".join(toc_items) + "</ul></nav>"
    return toc + "\n" + "\n".join(sections)


def _design_panel(slot: dict, design_id: str) -> str:
    """Rendert EINEN Slot als design-konformen Panel-Inhalt (ohne <h2>-Doppelung)."""
    one = [slot]
    title = str(slot.get("title", ""))
    if design_id == "magazine":
        return _render_magazine(title, one)
    if design_id == "cards":
        return _render_cards(title, one)
    # classic/leer: schlichte Sektion ohne TOC
    body = sanitize_html(slot.get("body"))
    return f'<section><h2>{_html.escape(title)}</h2>{body}</section>'


# Basis-CSS fuer die scroll-bare Button-Leiste (ohne Scrollbalken, JS-frei).
# Die Tab-Mechanik laeuft ueber den Radio-+-``:checked``-Trick; die per-Tab-
# Regeln (welcher Button aktiv aussieht + welcher Panel sichtbar ist) werden in
# ``_render_tabs`` dynamisch erzeugt.
_TABS_BASE_CSS = """
.tabs > input[type=radio]{display:none}
.tabbar{display:flex;gap:.4rem;overflow-x:auto;padding-bottom:.25rem;scrollbar-width:none;-ms-overflow-style:none}
.tabbar::-webkit-scrollbar{display:none}
.tabbar > label{flex:0 0 auto;white-space:nowrap;cursor:pointer;padding:.35rem .9rem;border:1px solid #ddd;border-radius:999px;background:#fff;font-size:.9rem}
.tabs > .tab-panel{display:none;margin-top:.75rem}
""".strip()


def _render_tabs(slots: list[dict], design_id: str = "") -> str:
    if not slots:
        return _EMPTY_PLACEHOLDER

    # ``sid`` stammt aus ``slot["id"]`` (uuid-hex / "prev" o.ae.) und ist damit
    # auf sichere Zeichen beschraenkt. Fuer die CSS-Selektoren nutzen wir
    # dennoch [id="..."]-Attribut-Selektoren statt #id, damit etwaige
    # Sonderzeichen die Regel nicht zerbrechen. Fuer HTML-Attribute escapen wir
    # zusaetzlich via _html.escape.
    rules: list[str] = [_TABS_BASE_CSS]
    inputs: list[str] = []
    labels: list[str] = ['<nav class="tabbar">']
    panels: list[str] = []

    for idx, slot in enumerate(slots):
        sid = _html.escape(str(slot.get("id", "")))
        stitle = _html.escape(str(slot.get("title", "")))
        checked = " checked" if idx == 0 else ""
        tab_id = f"tab-{sid}"
        panel_id = f"panel-{sid}"

        inputs.append(
            f'<input type="radio" name="canvas-tabs" id="{tab_id}"{checked}>'
        )
        labels.append(f'<label for="{tab_id}">{stitle}</label>')
        panels.append(
            f'<div class="tab-panel" id="{panel_id}">'
            f"{_design_panel(slot, design_id)}</div>"
        )

        # Aktiver Button: "reingedrueckt" via Inset-Schatten + dunklerer BG.
        rules.append(
            f'.tabs > input[type=radio][id="{tab_id}"]:checked ~ '
            f'.tabbar label[for="{tab_id}"]{{'
            "background:#e5e7eb;box-shadow:inset 0 2px 5px rgba(0,0,0,.18);"
            "font-weight:600}"
        )
        # Passenden Panel sichtbar schalten.
        rules.append(
            f'.tabs > input[type=radio][id="{tab_id}"]:checked ~ '
            f'.tab-panel[id="{panel_id}"]{{display:block}}'
        )

    labels.append("</nav>")

    style = "<style>\n" + "\n".join(rules) + "\n</style>"
    return (
        style
        + '<div class="tabs">'
        + "".join(inputs)
        + "".join(labels)
        + "".join(panels)
        + "</div>"
    )


def _render_magazine(title: str, slots: list[dict]) -> str:
    # Struktur passt zum Magazin-CSS: header.hero / main / section.card / h2 / .tag.
    head = f'<header class="hero"><h1>{_html.escape(title or "—")}</h1></header>'
    if not slots:
        return head + "<main>" + _EMPTY_PLACEHOLDER + "</main>"
    cards = []
    for slot in slots:
        sid = _html.escape(str(slot.get("id", "")))
        stitle = _html.escape(str(slot.get("title", "")))
        body = sanitize_html(slot.get("body"))
        cards.append(
            f'<section class="card" id="{sid}"><h2>{stitle}</h2>{body}</section>'
        )
    return head + "<main>" + "".join(cards) + "</main>"


def _render_cards(title: str, slots: list[dict]) -> str:
    # Struktur passt zum Karten-CSS: header / .grid / .tile / .tile .num / .tile h3.
    head = f"<header><h1>{_html.escape(title or '—')}</h1></header>"
    if not slots:
        return head + '<div class="grid">' + _EMPTY_PLACEHOLDER + "</div>"
    tiles = []
    for idx, slot in enumerate(slots):
        sid = _html.escape(str(slot.get("id", "")))
        stitle = _html.escape(str(slot.get("title", "")))
        body = sanitize_html(slot.get("body"))
        num = f"{idx + 1:02d}"
        tiles.append(
            f'<article class="tile" id="{sid}">'
            f'<div class="num">{num}</div><h3>{stitle}</h3>{body}</article>'
        )
    return head + '<div class="grid">' + "".join(tiles) + "</div>"


def render_static(data: dict, design_id: str = "") -> str:
    """Vollstaendiges ``<!doctype html>``-Dokument ohne ``<script>`` erzeugen.

    ``design_id`` waehlt das CSS (und bei den Sektionen die passende Struktur) aus
    den ``html_templates``. Ohne ``design_id`` bleibt das Verhalten unveraendert
    (TOC-Sektionen / CSS-Tabs mit dem eingebauten ``_STYLE``).
    """
    data = data or {}
    layout = data.get("layout") or "sections"
    slots = _sorted_slots(data)
    title = str(data.get("title") or "Canvas")

    tpl = html_templates.get(design_id) if design_id else None
    css = tpl["css"] if tpl else _STYLE

    # Tabs bleiben CSS-only (Radio-+-:checked-Trick). Die Tab-spezifischen CSS-
    # Regeln (Basis + per-Tab) gibt _render_tabs als eigenen <style>-Block im
    # Body aus, daher reicht hier das (Design- oder Default-)CSS im <head>.
    if layout == "tabs":
        return _doc(title, _render_tabs(slots, design_id), css)

    # Liste: verlinktes Verzeichnis (TOC) oben + Einträge als Abschnitte. Klick auf einen
    # Namen scrollt zum Eintrag (Anker-Links). Design-CSS für Typografie, _STYLE für die
    # .toc-Optik. Design-unabhängig, damit die verlinkte Liste immer erscheint.
    if layout == "liste":
        liste_css = css if css is _STYLE else css + "\n" + _STYLE
        return _doc(title, _render_sections(slots), liste_css)

    # Sektionen: design-spezifische Struktur, damit das jeweilige CSS greift.
    if tpl and design_id == "magazine":
        body_html = _render_magazine(title, slots)
    elif tpl and design_id == "cards":
        body_html = _render_cards(title, slots)
    else:
        # classic oder unbekannt/leer: bisherige TOC-/<main>-Struktur.
        body_html = _render_sections(slots)

    return _doc(title, body_html, css)
