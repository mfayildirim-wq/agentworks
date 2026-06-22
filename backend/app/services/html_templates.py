"""Registry der eingebauten HTML-Vorlagen (Schritt ①.1).

Drei fertige, eigenständige `<!doctype html>`-Seiten mit eingebettetem `<style>`
und **ohne JavaScript** (passt zur Serving-CSP `script-src 'none'`; Inline-CSS ist
über `style-src 'unsafe-inline'` erlaubt). Beim Anlegen/Bearbeiten einer Agent-Vorlage
muss genau eine davon gewählt werden; die Auswahl wird an der Vorlage gespeichert.

Die Seiten enthalten bewusst noch **Beispiel-/Blindtext**, damit die Vorschau den Stil
zeigt — echte Platzhalter/Slots und das Befüllen durch den Agenten kommen in ①.2.
"""

from __future__ import annotations

import re

_CLASSIC_HTML = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Klassisch / Dokument</title>
<style>
  :root { color-scheme: light; }
  body {
    margin: 0; background: #faf9f6; color: #1f1d1a;
    font-family: Georgia, "Times New Roman", serif; line-height: 1.65;
  }
  main { max-width: 720px; margin: 0 auto; padding: 64px 24px; }
  h1 { font-size: 2.6rem; line-height: 1.15; margin: 0 0 .2em; font-weight: 600; }
  .lead { font-size: 1.15rem; color: #55504a; margin: 0 0 2.5rem; }
  h2 { font-size: 1.5rem; margin: 2.5rem 0 .6rem; border-bottom: 1px solid #e3ded5; padding-bottom: .3rem; }
  p { margin: 0 0 1.1rem; }
  blockquote { margin: 1.6rem 0; padding-left: 1.2rem; border-left: 3px solid #c9a96a; color: #5c564e; font-style: italic; }
  footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e3ded5; color: #8a847b; font-size: .9rem; }
</style>
</head>
<body>
<main>
  <h1>Ein klares Dokument</h1>
  <p class="lead">Eine ruhige, einspaltige Vorlage mit viel Weißraum — für Reisepläne, Guides und Berichte.</p>
  <h2>Überschrift der Sektion</h2>
  <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Hier steht später der vom Agenten erzeugte Inhalt, sauber in dieses Layout eingebettet.</p>
  <blockquote>Ein hervorgehobener Gedanke oder ein wichtiger Hinweis.</blockquote>
  <h2>Weitere Sektion</h2>
  <p>Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation.</p>
  <footer>Erstellt mit AgentWorks · Vorlage „Klassisch"</footer>
</main>
</body>
</html>
"""

_MAGAZINE_HTML = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Magazin / Editorial</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: #ffffff; color: #16181d;
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6;
  }
  header.hero {
    background: linear-gradient(135deg, #4f46e5, #db2777); color: #fff;
    padding: 72px 24px; text-align: center;
  }
  header.hero h1 { font-size: 3rem; margin: 0 0 .3em; font-weight: 800; letter-spacing: -.02em; }
  header.hero p { font-size: 1.2rem; margin: 0; opacity: .92; }
  main { max-width: 900px; margin: -40px auto 0; padding: 0 24px 64px; }
  section.card {
    background: #fff; border-radius: 16px; padding: 28px 32px; margin-bottom: 20px;
    box-shadow: 0 10px 30px rgba(20, 20, 40, .08); border: 1px solid #eef0f4;
  }
  section.card h2 { margin: 0 0 .4em; font-size: 1.5rem; color: #4f46e5; }
  section.card p { margin: 0 0 .8rem; color: #3a3f4b; }
  .tag { display: inline-block; background: #eef2ff; color: #4f46e5; font-size: .8rem;
         font-weight: 600; padding: 4px 10px; border-radius: 999px; margin-bottom: .8rem; }
</style>
</head>
<body>
<header class="hero">
  <h1>Editorial-Magazin</h1>
  <p>Großer Header, klare Sektionen, moderner Look.</p>
</header>
<main>
  <section class="card">
    <span class="tag">Highlight</span>
    <h2>Die erste Sektion</h2>
    <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Der Agent füllt hier später den Inhalt ein — das Design bleibt fest.</p>
  </section>
  <section class="card">
    <h2>Zweite Sektion</h2>
    <p>Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam.</p>
  </section>
  <section class="card">
    <h2>Dritte Sektion</h2>
    <p>Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore.</p>
  </section>
</main>
</body>
</html>
"""

_CARDS_HTML = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Karten-Raster</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: #0f172a; color: #e2e8f0;
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.55;
  }
  header { padding: 56px 24px 24px; text-align: center; }
  header h1 { font-size: 2.4rem; margin: 0 0 .2em; font-weight: 700; }
  header p { margin: 0; color: #94a3b8; }
  .grid {
    max-width: 1000px; margin: 0 auto; padding: 24px; display: grid; gap: 18px;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  }
  .tile {
    background: #1e293b; border: 1px solid #334155; border-radius: 14px; padding: 22px;
  }
  .tile .num { font-size: .8rem; color: #38bdf8; font-weight: 700; letter-spacing: .08em; }
  .tile h3 { margin: .3em 0 .4em; font-size: 1.15rem; color: #f1f5f9; }
  .tile p { margin: 0; color: #94a3b8; font-size: .95rem; }
</style>
</head>
<body>
<header>
  <h1>Karten-Raster</h1>
  <p>Responsives Grid — für Listen, Empfehlungen und Galerien.</p>
</header>
<div class="grid">
  <article class="tile"><div class="num">01</div><h3>Erste Karte</h3><p>Kurzer Beschreibungstext, den der Agent später befüllt.</p></article>
  <article class="tile"><div class="num">02</div><h3>Zweite Karte</h3><p>Lorem ipsum dolor sit amet, consectetur adipiscing.</p></article>
  <article class="tile"><div class="num">03</div><h3>Dritte Karte</h3><p>Sed do eiusmod tempor incididunt ut labore.</p></article>
  <article class="tile"><div class="num">04</div><h3>Vierte Karte</h3><p>Ut enim ad minim veniam, quis nostrud.</p></article>
  <article class="tile"><div class="num">05</div><h3>Fünfte Karte</h3><p>Duis aute irure dolor in reprehenderit.</p></article>
  <article class="tile"><div class="num">06</div><h3>Sechste Karte</h3><p>Excepteur sint occaecat cupidatat non proident.</p></article>
</div>
</body>
</html>
"""

_STYLE_RE = re.compile(r"<style>(.*?)</style>", re.DOTALL)


def _css(html: str) -> str:
    """Reiner CSS-Inhalt zwischen <style> und </style> (ohne Tags)."""
    m = _STYLE_RE.search(html)
    return m.group(1).strip() if m else ""


HTML_TEMPLATES: list[dict] = [
    {
        "id": "classic",
        "name": "Klassisch / Dokument",
        "description": "Eine Spalte, ruhige Serif-Überschriften, viel Weißraum. Für Reisepläne, Guides, Berichte.",
        "html": _CLASSIC_HTML,
        "css": _css(_CLASSIC_HTML),
    },
    {
        "id": "magazine",
        "name": "Magazin / Editorial",
        "description": "Großer Titel-Header mit Akzentfarbe, in Sektionen/Karten gegliedert, moderner Sans-Serif.",
        "html": _MAGAZINE_HTML,
        "css": _css(_MAGAZINE_HTML),
    },
    {
        "id": "cards",
        "name": "Karten-Raster",
        "description": "Responsives Grid aus Karten. Für Listen, Empfehlungen, Galerien.",
        "html": _CARDS_HTML,
        "css": _css(_CARDS_HTML),
    },
]

_BY_ID: dict[str, dict] = {t["id"]: t for t in HTML_TEMPLATES}


def list_templates() -> list[dict]:
    """Alle 3 Vorlagen (id, name, description, html)."""
    return list(HTML_TEMPLATES)


def get(template_id: str) -> dict | None:
    """Eine Vorlage oder None, wenn die id unbekannt ist."""
    return _BY_ID.get(template_id)


def is_valid(template_id: str) -> bool:
    """True, wenn `template_id` eine bekannte Vorlage ist (leerer String → False)."""
    return template_id in _BY_ID
