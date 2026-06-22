"""Veröffentlicht die aktuelle HTML einer Instanz als WordPress-Beitrag (nativ, REST).

Application Password (Basic-Auth) wird server-seitig aus der verschlüsselten Instanz-
Verbindung gelesen und nur in den Auth-Header gegeben — nie ins LLM/Log/Response.
Die erzeugte post_id wird in der Verbindungs-config gemerkt → Folge-Veröffentlichungen
aktualisieren denselben Beitrag. Fehler → kurze, sichere Meldung."""

from __future__ import annotations

import logging
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.db.models import Artifact, ArtifactVersion
from app.services.artifact_connections import get_connection

logger = logging.getLogger(__name__)


async def _wp_post(url: str, *, auth: tuple[str, str], json: dict, timeout: float) -> dict:
    """POST an die WP-REST-API; gibt die JSON-Antwort zurück. (In Tests gemockt.)"""
    # User-Agent: viele Hoster-WAFs (ModSecurity) blocken den Default `python-httpx`
    # mit 403, bevor die Anfrage WordPress erreicht. Ein normaler UA kommt durch.
    # follow_redirects: WP-Hoster leiten oft http<->https oder mit/ohne Slash um.
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AgentWorks/1.0)"}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        r = await client.post(url, auth=auth, json=json)
        r.raise_for_status()
        return r.json()


async def publish_post(
    db: AsyncSession, artifact_id: UUID, owner_id: UUID, *, title: str, status: str = "draft"
) -> tuple[bool, str]:
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != owner_id:
        return False, "Instanz nicht gefunden."
    if art.current_version_id is None:
        return False, "Es gibt noch keine Seite zum Veröffentlichen."
    version = await db.get(ArtifactVersion, art.current_version_id)
    html = version.content if version else ""
    if not html.strip():
        return False, "Es gibt noch keine Seite zum Veröffentlichen."

    conn = await get_connection(db, artifact_id, owner_id, "wordpress")
    if conn is None:
        return False, 'Bitte zuerst die WordPress-Verbindung einrichten (rechts unter "Verbindung").'

    cfg = conn.config or {}
    site = str(cfg.get("site_url", "")).rstrip("/")
    if not site:
        return False, "WordPress-Verbindung unvollständig: Seiten-URL fehlt."
    username = cfg.get("username", "")
    post_id = cfg.get("post_id")
    url = f"{site}/wp-json/wp/v2/posts/{post_id}" if post_id else f"{site}/wp-json/wp/v2/posts"
    if status not in ("draft", "publish"):
        status = "draft"

    try:
        resp = await _wp_post(
            url, auth=(username, crypto.decrypt(conn.secret_encrypted)),
            json={"title": title, "content": html, "status": status}, timeout=30.0,
        )
    except httpx.HTTPStatusError as exc:
        # WP-Fehlerkörper (z.B. {"code":"incorrect_password"...}) ist sicher zu loggen —
        # er enthält kein Secret. Hilft, 401 (Auth) von 403 (Plugin) / 404 (URL) zu trennen.
        code = exc.response.status_code
        logger.warning(
            "wp-publish-failed site=%s status=%s body=%s", site, code, exc.response.text[:200]
        )
        return False, f"Veröffentlichen fehlgeschlagen (HTTP {code}). Bitte Zugang/URL prüfen."
    except Exception as exc:  # noqa: BLE001 — keine Details/Secret nach außen
        logger.warning("wp-publish-failed site=%s err=%s", site, type(exc).__name__)
        return False, f"Veröffentlichen fehlgeschlagen ({type(exc).__name__}). Bitte Zugang/URL prüfen."

    new_id = resp.get("id")
    if new_id and new_id != post_id:
        conn.config = {**cfg, "post_id": new_id}
        await db.commit()
    link = resp.get("link") or site
    return True, f"Veröffentlicht: {link}"
