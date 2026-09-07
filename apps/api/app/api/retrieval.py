from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.enterprise import Document, DocumentChunk
from app.schemas.retrieval import RetrievalQuery, RetrievalResponse, RetrievalResult
from app.services.embeddings import cosine_similarity, embed

# Chunks are scored with a full in-memory scan (no ANN index), so this caps
# how many candidate chunks a single query will pull from the database.
# Fine at the current synthetic-data scale; a real vector index is required
# before this is safe at large document-corpus scale.
MAX_CANDIDATE_CHUNKS = 5_000

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalResponse)
async def search(
    payload: RetrievalQuery,
    auth: AuthContext = Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> RetrievalResponse:
    stmt = (
        select(DocumentChunk, Document.title)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.organization_id == auth.organization_id)
    )
    if payload.customer_id is not None:
        stmt = stmt.where(Document.customer_id == payload.customer_id)
    stmt = stmt.limit(MAX_CANDIDATE_CHUNKS)

    result = await db.execute(stmt)
    rows = result.all()

    query_vector = embed(payload.query)
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
    return RetrievalResponse(results=scored[: payload.top_k])
