import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.decision import Decision
from app.schemas.decision import DecisionOut
from app.services.decisions import list_decisions

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("", response_model=list[DecisionOut])
async def get_decisions(
    auth: AuthContext = Depends(require_permission(Permission.AGENT_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> list[DecisionOut]:
    decisions = await list_decisions(db, auth.organization_id)
    return [DecisionOut.model_validate(d) for d in decisions]


@router.get("/{decision_id}", response_model=DecisionOut)
async def get_decision_by_id(
    decision_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.AGENT_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> DecisionOut:
    result = await db.execute(
        select(Decision).where(
            Decision.id == decision_id, Decision.organization_id == auth.organization_id
        )
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="decision not found")
    return DecisionOut.model_validate(decision)
