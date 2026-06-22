"""Veröffentlicht die aktuelle HTML einer Instanz per SFTP auf den Server des Nutzers.

Nativer Connector (kein MCP): es ist eine Aktion auf unseren eigenen Daten. Der
blockierende paramiko-Teil (`_sftp_upload`) läuft im Threadpool und ist in Tests
gemockt. Fehler werden zu einer kurzen, sicheren Meldung — nie Stacktrace/Passwort."""

from __future__ import annotations

import io
import logging
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.db.models import Artifact, ArtifactVersion
from app.services.artifact_connections import get_connection

logger = logging.getLogger(__name__)


def _sftp_upload(
    *, host: str, port: int, username: str, password: str,
    remote_path: str, data: bytes, timeout: float = 15.0,
) -> None:
    """Verbindet per SFTP und schreibt `data` nach `remote_path`. Synchron (Threadpool)."""
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host, port=port, username=username, password=password,
            timeout=timeout, allow_agent=False, look_for_keys=False,
        )
        sftp = client.open_sftp()
        try:
            sftp.putfo(io.BytesIO(data), remote_path)
        finally:
            sftp.close()
    finally:
        client.close()


def _ftps_upload(
    *, host: str, port: int, username: str, password: str,
    remote_path: str, data: bytes, timeout: float = 15.0,
) -> None:
    """Lädt `data` per explizitem FTPS (FTP über TLS, AUTH TLS) hoch. Synchron (Threadpool).

    Viele Shared-Hoster (ProFTPD) bieten FTPS statt SFTP — FileZilla nutzt das als
    'FTP über TLS'. Zertifikate passen dort oft nicht zum vhost; wie bei SFTP
    (AutoAddPolicy) vertrauen wir dem nutzereigenen Ziel ohne strikte Prüfung."""
    import ftplib
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    class _FTPS(ftplib.FTP_TLS):
        # ProFTPD u.a. verlangen, dass der Datenkanal die TLS-Session des
        # Steuerkanals wiederverwendet — sonst schlägt STOR mit TLS-Fehler fehl.
        def ntransfercmd(self, cmd, rest=None):  # type: ignore[override]
            conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
            if self._prot_p:  # type: ignore[attr-defined]
                conn = self.context.wrap_socket(
                    conn, server_hostname=self.host,
                    session=self.sock.session,  # type: ignore[attr-defined]
                )
            return conn, size

    ftp = _FTPS(context=ctx)
    try:
        ftp.connect(host, port, timeout=timeout)
        ftp.auth()  # Steuerkanal auf TLS heben
        ftp.login(username, password)
        ftp.prot_p()  # Datenkanal verschlüsseln
        ftp.storbinary(f"STOR {remote_path}", io.BytesIO(data))
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001 — Aufräumen, Fehler egal
            ftp.close()


async def publish_artifact(
    db: AsyncSession, artifact_id: UUID, owner_id: UUID
) -> tuple[bool, str]:
    """Lädt die aktuelle HTML der Instanz per SFTP hoch. (ok, Meldung)."""
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != owner_id:
        return False, "Instanz nicht gefunden."
    if art.current_version_id is None:
        return False, "Es gibt noch keine Seite zum Veröffentlichen."
    version = await db.get(ArtifactVersion, art.current_version_id)
    html = version.content if version else ""
    if not html.strip():
        return False, "Es gibt noch keine Seite zum Veröffentlichen."

    conn = await get_connection(db, artifact_id, owner_id, "sftp")
    if conn is None:
        return False, 'Bitte zuerst die SFTP-Verbindung einrichten (rechts unter "Verbindung").'

    cfg = conn.config or {}
    host = cfg.get("host", "")
    port = int(cfg.get("port", 22) or 22)
    # Leerer Pfad → Standard-Datei. Port 22 = SFTP (SSH), sonst FTP über TLS (Port 21).
    remote = cfg.get("remote_path", "") or "index.html"
    upload = _sftp_upload if port == 22 else _ftps_upload
    proto = "SFTP" if port == 22 else "FTPS"
    try:
        await run_in_threadpool(
            upload,
            host=host, port=port, username=cfg.get("username", ""),
            password=crypto.decrypt(conn.secret_encrypted),
            remote_path=remote, data=html.encode("utf-8"),
        )
    except Exception as exc:  # noqa: BLE001 — keine Details/Secret nach außen
        logger.warning(
            "publish-failed proto=%s host=%s port=%s err=%s: %s",
            proto, host, port, type(exc).__name__, str(exc)[:160],
        )
        return False, f"Veröffentlichen fehlgeschlagen ({type(exc).__name__}). Bitte Zugangsdaten/Pfad prüfen."

    return True, f"Veröffentlicht ({proto}): {host}/{remote}"
