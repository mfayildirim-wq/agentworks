"""RAG: Dokumente chunken, embedden (Voyage), in pgvector ablegen, abrufen."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.models import RagDocument

settings = get_settings()

_EMBEDDING_DIM = 1024


def chunk_text(text: str, *, size: int = 800, overlap: int = 100) -> list[str]:
    text = text.strip()
    if not text:
        return []
    out: list[str] = []
    i = 0
    while i < len(text):
        end = min(len(text), i + size)
        out.append(text[i:end])
        if end == len(text):
            break
        i = max(0, end - overlap)
    return out


async def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if not settings.voyage_api_key:
        # Fallback: dummy-Embedding (alle Nullen + position-based hash) ermöglicht
        # End-to-End ohne Voyage-Key; Retrieval ist dann nicht semantisch korrekt.
        return [_pseudo_embedding(t) for t in texts]

    import voyageai

    client = voyageai.Client(api_key=settings.voyage_api_key)
    res = client.embed(texts, model="voyage-3", input_type="document")
    return [list(v) for v in res.embeddings]


def _pseudo_embedding(text: str) -> list[float]:
    import hashlib

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    out = [0.0] * _EMBEDDING_DIM
    for i, b in enumerate(digest):
        out[i % _EMBEDDING_DIM] += (b / 255.0) - 0.5
    return out


async def ingest(db: AsyncSession, agent_id: UUID, title: str, text: str) -> int:
    chunks = chunk_text(text)
    embeddings = await embed(chunks)
    for chunk, emb in zip(chunks, embeddings, strict=True):
        db.add(RagDocument(agent_id=agent_id, title=title, chunk=chunk, embedding=emb))
    await db.commit()
    return len(chunks)


async def retrieve(db: AsyncSession, agent_id: UUID, query: str, k: int = 4) -> list[str]:
    query_emb = (await embed([query]))[0] if query else None
    stmt = select(RagDocument).where(RagDocument.agent_id == agent_id)
    if query_emb is not None:
        # pgvector L2 distance
        try:
            stmt = stmt.order_by(RagDocument.embedding.l2_distance(query_emb)).limit(k)
        except Exception:
            stmt = stmt.limit(k)
    else:
        stmt = stmt.limit(k)
    rows = (await db.execute(stmt)).scalars().all()
    return [row.chunk for row in rows]
