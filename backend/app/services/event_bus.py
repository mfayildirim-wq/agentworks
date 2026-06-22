"""Persistiert Run-Events in DB + published auf Redis-Channel für SSE."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as redis_async
from sqlalchemy.ext.asyncio import AsyncSession

from agent_runtime.events import RunEvent, RunEventType

from app.core.settings import get_settings
from app.db.models import LogEntry, Message, WorkRun

settings = get_settings()


def channel(run_id: UUID) -> str:
    return f"runs:{run_id}"


async def publish(run_id: UUID, event: RunEvent) -> None:
    r = redis_async.from_url(settings.redis_url)
    try:
        await r.publish(channel(run_id), event.model_dump_json())
    finally:
        await r.aclose()


async def persist(db: AsyncSession, event: RunEvent) -> None:
    if event.type == RunEventType.AGENT_MESSAGE:
        db.add(
            Message(
                run_id=event.run_id,
                agent_id=event.agent_id,
                agent_name=event.agent_name or "",
                role="assistant",
                content=event.content or "",
                tokens_in=event.tokens_in,
                tokens_out=event.tokens_out,
                cost_usd=event.cost_usd,
            )
        )
    db.add(
        LogEntry(
            run_id=event.run_id,
            level="error" if event.type == RunEventType.ERROR else "info",
            type=event.type.value,
            payload={
                "agent_name": event.agent_name,
                "content": event.content,
                "tokens_in": event.tokens_in,
                "tokens_out": event.tokens_out,
                "cost_usd": event.cost_usd,
                **event.payload,
            },
        )
    )
    if event.type == RunEventType.RUN_COMPLETED:
        run = await db.get(WorkRun, event.run_id)
        if run:
            run.finished_at = datetime.now(timezone.utc)
    if event.type == RunEventType.ERROR:
        run = await db.get(WorkRun, event.run_id)
        if run:
            run.error = (run.error or "") + (event.content or "")
    await db.flush()


async def subscribe_stream(run_id: UUID):
    """Async-Generator: yieldet SSE-formatierte Strings für FastAPI StreamingResponse."""
    r = redis_async.from_url(settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(channel(run_id))
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            yield f"data: {data}\n\n"
            # Sentinel: bei RUN_COMPLETED Stream beenden
            try:
                parsed = json.loads(data)
                if parsed.get("type") in (
                    RunEventType.RUN_COMPLETED.value,
                    RunEventType.ERROR.value,
                ):
                    break
            except Exception:
                continue
    finally:
        await pubsub.unsubscribe(channel(run_id))
        await pubsub.aclose()
        await r.aclose()
