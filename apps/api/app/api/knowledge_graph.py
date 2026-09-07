import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.schemas.knowledge_graph import GraphEdge, GraphNode, GraphResponse
from app.services.knowledge_graph import ENTITY_TYPES, get_neighborhood

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])


@router.get("/{entity_type}/{entity_id}", response_model=GraphResponse)
async def get_entity_neighborhood(
    entity_type: str,
    entity_id: uuid.UUID,
    depth: int = Query(default=1, ge=1, le=3),
    auth: AuthContext = Depends(require_permission(Permission.DATA_QUERY)),
    db: AsyncSession = Depends(get_db),
) -> GraphResponse:
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown entity type: {entity_type}"
        )

    graph = await get_neighborhood(db, auth.organization_id, entity_type, entity_id, depth=depth)
    if graph is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="entity not found")

    return GraphResponse(
        nodes=[GraphNode(type=n.type, id=n.id, label=n.label) for n in graph.nodes.values()],
        edges=[
            GraphEdge(source=e.source, target=e.target, relation=e.relation) for e in graph.edges
        ],
    )
