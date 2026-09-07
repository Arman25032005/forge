import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.action import Action
from app.schemas.action import ActionCreate, ActionOut
from app.services.action_types import ACTION_TYPES_BY_NAME
from app.services.actions import (
    ActionPermissionError,
    ActionStateError,
    approve_action,
    execute_action,
    get_action_or_none,
    propose_action,
    reject_action,
)

router = APIRouter(prefix="/actions", tags=["actions"])


async def _get_action_or_404(
    db: AsyncSession, organization_id: uuid.UUID, action_id: uuid.UUID
) -> Action:
    action = await get_action_or_none(db, organization_id, action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="action not found")
    return action


@router.post("", response_model=ActionOut, status_code=201)
async def create_action(
    payload: ActionCreate,
    auth: AuthContext = Depends(require_permission(Permission.ACTION_PROPOSE)),
    db: AsyncSession = Depends(get_db),
) -> ActionOut:
    if payload.action_type not in ACTION_TYPES_BY_NAME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown action type: {payload.action_type}",
        )
    action = await propose_action(
        db,
        organization_id=auth.organization_id,
        proposed_by=auth.user_id,
        decision_id=payload.decision_id,
        action_type=payload.action_type,
        description=payload.description,
        parameters=payload.parameters,
    )
    return ActionOut.model_validate(action)


@router.get("", response_model=list[ActionOut])
async def list_actions(
    auth: AuthContext = Depends(require_permission(Permission.ACTION_PROPOSE)),
    db: AsyncSession = Depends(get_db),
) -> list[ActionOut]:
    result = await db.execute(
        select(Action)
        .where(Action.organization_id == auth.organization_id)
        .order_by(Action.created_at.desc())
    )
    return [ActionOut.model_validate(a) for a in result.scalars().all()]


@router.get("/{action_id}", response_model=ActionOut)
async def get_action(
    action_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.ACTION_PROPOSE)),
    db: AsyncSession = Depends(get_db),
) -> ActionOut:
    action = await _get_action_or_404(db, auth.organization_id, action_id)
    return ActionOut.model_validate(action)


@router.post("/{action_id}/approve", response_model=ActionOut)
async def approve(
    action_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.ACTION_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> ActionOut:
    action = await _get_action_or_404(db, auth.organization_id, action_id)
    try:
        action = await approve_action(db, action, approved_by=auth.user_id)
    except ActionPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ActionStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ActionOut.model_validate(action)


@router.post("/{action_id}/reject", response_model=ActionOut)
async def reject(
    action_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.ACTION_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> ActionOut:
    action = await _get_action_or_404(db, auth.organization_id, action_id)
    try:
        action = await reject_action(db, action, rejected_by=auth.user_id)
    except ActionStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ActionOut.model_validate(action)


@router.post("/{action_id}/execute", response_model=ActionOut)
async def execute(
    action_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.ACTION_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> ActionOut:
    action = await _get_action_or_404(db, auth.organization_id, action_id)
    try:
        action = await execute_action(db, action)
    except ActionStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ActionOut.model_validate(action)
