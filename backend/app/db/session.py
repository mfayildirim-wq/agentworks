from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import get_settings

settings = get_settings()
# idle_in_transaction_session_timeout: verwaiste „idle in transaction"-Verbindungen (z.B.
# nach einem per Time-Limit gekillten Turn) rollen nach 60s automatisch zurück und geben
# ihre Sperren frei — sonst kann EINE Leiche alle Artefakt-Writes blockieren (Telegram-Hang).
engine = create_async_engine(
    settings.database_url, pool_pre_ping=True, future=True,
    connect_args={"server_settings": {"idle_in_transaction_session_timeout": "60000"}},
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
