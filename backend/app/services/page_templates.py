"""Datei-basierte 'fertige' Seiten-Templates (prepared). Jede Vorlage besteht aus
<name>.html (mit {{key}} + <link>/<script>-Includes), <name>_css.css, <name>_js.js,
<name>.json (Manifest). Gerendert wird ein eigenstaendiges HTML (CSS/JS inline)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.services.canvas_render import sanitize_html

_DIR = Path(__file__).resolve().parents[2] / "page_templates"  # backend/page_templates
_LINK_RE = re.compile(r'<link[^>]*href="[^"]*_css\.css"[^>]*>', re.I)
_SCRIPT_RE = re.compile(r'<script[^>]*src="[^"]*_js\.js"[^>]*>\s*</script>', re.I)
_PH_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def _names() -> list[str]:
    if not _DIR.exists():
        return []
    return sorted(p.name for p in _DIR.iterdir() if p.is_dir())


def get(name: str) -> dict | None:
    d = _DIR / name
    if not d.is_dir() or not (d / f"{name}.html").exists():
        return None
    mf = d / f"{name}.json"
    manifest = json.loads(mf.read_text()) if mf.exists() else {}
    return {
        "name": name,
        "label": manifest.get("label", name),
        "description": manifest.get("description", ""),
        "placeholders": manifest.get("placeholders", []),
    }


def list_all() -> list[dict]:
    out = []
    for n in _names():
        g = get(n)
        if g:
            out.append(g)
    return out


def render(name: str, values: dict) -> str:
    d = _DIR / name
    html = (d / f"{name}.html").read_text()
    css = (d / f"{name}_css.css").read_text() if (d / f"{name}_css.css").exists() else ""
    js = (d / f"{name}_js.js").read_text() if (d / f"{name}_js.js").exists() else ""
    html = _LINK_RE.sub(f"<style>{css}</style>", html)
    html = _SCRIPT_RE.sub(f"<script>{js}</script>", html)
    html = _PH_RE.sub(lambda m: sanitize_html(str(values.get(m.group(1), "") or "")), html)
    return html
