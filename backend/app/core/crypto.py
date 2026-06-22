"""Symmetrische Verschlüsselung für pro-Agent API-Keys (Fernet)."""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet

from app.core.settings import get_settings


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().agent_secret_key
    if not key:
        raise RuntimeError("AGENT_SECRET_KEY ist nicht gesetzt (Fernet-Key erforderlich)")
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
