from __future__ import annotations

import json
import urllib.request

from fastapi import HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.core.settings import get_settings
from app.schemas.agents import ProfileExtract

settings = get_settings()

_PROMPT = (
    "Du bist ein Parser für Lebensläufe und Beraterprofile. Extrahiere aus dem "
    "folgenden Text ein JSON-Objekt mit den Feldern: name (string), role (string, "
    "z.B. 'Softwareentwickler'), domain (string, z.B. 'software'), seniority "
    "(string, z.B. 'Senior'), skills (Array kurzer Tags wie 'java','react',"
    "'buchhaltung'), summary (2-3 Sätze deutsch). Antworte AUSSCHLIESSLICH mit JSON.\n\nTEXT:\n"
)


def _extract_text(filename: str, data: bytes) -> str:
    from app.services.file_text import extract_text

    text = extract_text(filename, data)
    if not text:
        raise HTTPException(400, "Nur PDF, DOCX, TXT/MD/CSV werden unterstützt.")
    return text


def _call_ollama(text: str) -> dict:
    body = json.dumps(
        {
            "model": settings.ollama_model,
            "prompt": _PROMPT + text[:12000],
            "format": "json",
            "stream": False,
        }
    ).encode()
    req = urllib.request.Request(
        settings.ollama_url.rstrip("/") + "/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Skill-Erkennung fehlgeschlagen: {exc}") from exc
    try:
        return json.loads(resp.get("response", "{}"))
    except json.JSONDecodeError:
        return {}


async def extract_profile(file: UploadFile) -> ProfileExtract:
    data = await file.read()
    text = _extract_text(file.filename or "", data)
    if not text.strip():
        raise HTTPException(400, "Konnte keinen Text aus der Datei lesen.")
    parsed = await run_in_threadpool(_call_ollama, text)
    skills = parsed.get("skills") or []
    if not isinstance(skills, list):
        skills = []
    return ProfileExtract(
        name=str(parsed.get("name") or ""),
        role=str(parsed.get("role") or ""),
        domain=str(parsed.get("domain") or ""),
        seniority=str(parsed.get("seniority") or ""),
        skills=[str(s) for s in skills][:20],
        summary=str(parsed.get("summary") or ""),
    )
