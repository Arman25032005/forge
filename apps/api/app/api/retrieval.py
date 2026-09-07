from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.schemas.retrieval import RetrievalQuery, RetrievalResponse
from app.services.retrieval import search_chunks

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalResponse)
async def search(
    payload: RetrievalQuery,
    auth: AuthContext = Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> RetrievalResponse:
    results = await search_chunks(
        db,
        organization_id=auth.organization_id,
        query=payload.query,
        top_k=payload.top_k,
        customer_id=payload.customer_id,
    )
    return RetrievalResponse(results=results)
