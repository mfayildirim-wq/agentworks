from __future__ import annotations

import os

os.environ.setdefault("AUTH_DISABLED_FOR_TESTS", "1")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://agentworks:agentworks_dev@localhost:5432/agentworks_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from cryptography.fernet import Fernet

os.environ.setdefault("AGENT_SECRET_KEY", Fernet.generate_key().decode())

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.settings import get_settings
from app.db.base import Base
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _prepare_schema():
    settings = get_settings()
    # SICHERHEITSGURT: drop_all/create_all NUR gegen eine erkennbare Test-DB zulassen.
    # Verhindert, dass ein Testlauf (z.B. im Prod-Container mit gesetzter DATABASE_URL)
    # versehentlich die Produktions-DB leert. Der DB-Name MUSS "test" enthalten.
    db_name = settings.database_url.rsplit("/", 1)[-1].split("?", 1)[0].lower()
    if "test" not in db_name:
        raise RuntimeError(
            f"Abbruch: Test-Setup würde DB '{db_name}' droppen — das ist KEINE Test-DB. "
            "DATABASE_URL muss auf eine DB mit 'test' im Namen zeigen."
        )
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_between_tests():
    """Schließt gepoolte asyncpg-Verbindungen nach jedem Test innerhalb der noch
    offenen Event-Loop. Sonst werden sie erst beim GC nach Loop-Schluss geschlossen
    → 'RuntimeError: Event loop is closed'."""
    yield
    from app.db.session import engine

    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
