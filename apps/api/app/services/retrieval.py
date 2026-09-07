import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Document, DocumentChunk
from app.schemas.retrieval import RetrievalResult
from app.services.embeddings import cosine_similarity, embed

# Chunks are scored with a full in-memory scan (no ANN index), so this caps
# how many candidate chunks a single query will pull from the database.
# Fine at the current synthetic-data scale; a real vector index is required
# before this is safe at large document-corpus scale.
MAX_CANDIDATE_CHUNKS = 5_000


async def search_chunks(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    query: str,
    top_k: int = 5,
    customer_id: uuid.UUID | None = None,
) -> list[RetrievalResult]:
    stmt = (
        select(DocumentChunk, Document.title)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.organization_id == organization_id)
    )
    if customer_id is not None:
        stmt = stmt.where(Document.customer_id == customer_id)
    stmt = stmt.limit(MAX_CANDIDATE_CHUNKS)

    result = await db.execute(stmt)
    rows = result.all()

    query_vector = embed(query)
    scored = [
        RetrievalResult(
            document_id=chunk.document_id,
            document_title=title,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=cosine_similarity(query_vector, chunk.embedding),
        )
        for chunk, title in rows
    ]
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]
