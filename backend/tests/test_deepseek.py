from __future__ import annotations
from decimal import Decimal
import pytest
from app.schemas.agents import AgentCreate


def test_agent_create_defaults_to_deepseek():
    a = AgentCreate(name="X")
    assert a.provider == "deepseek" and a.model == "deepseek-chat"


def test_deepseek_provider_supports_tools():
    from agent_runtime.model_client import provider_supports_tools
    assert provider_supports_tools("deepseek") is True


@pytest.mark.asyncio
async def test_deepseek_in_pricing_seed():
    from app.db.session import SessionLocal
    from app.services import model_pricing
    async with SessionLocal() as db:
        await model_pricing.ensure_seed(db); await db.commit()
        pin, pout = await model_pricing.price_for(db, "deepseek-chat")
        assert pin == Decimal("0.27") and pout == Decimal("1.10")


@pytest.mark.asyncio
async def test_provider_for_overrides_stale_field():
    # Modell ist die Wahrheitsquelle: deepseek-chat -> deepseek, egal was im Agenten steht.
    from app.db.session import SessionLocal
    from app.services import model_pricing
    async with SessionLocal() as db:
        await model_pricing.ensure_seed(db); await db.commit()
        assert await model_pricing.provider_for(db, "deepseek-chat") == "deepseek"
        assert await model_pricing.provider_for(db, "claude-haiku-4-5") == "anthropic"
        assert await model_pricing.provider_for(db, "gibt-es-nicht") is None
