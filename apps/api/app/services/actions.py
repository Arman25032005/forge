import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import actions_total
from app.models.action import Action
from app.models.decision import Decision
from app.services.action_types import ACTION_TYPES_BY_NAME, ActionExecutionError


class ActionStateError(Exception):
    """Raised when the requested transition doesn't make sense for an
    action's current status (e.g. approving an already-executed action)."""


class ActionPermissionError(Exception):
    """Raised for authorization rules the caller's role alone can't
    express, e.g. maker-checker (can't approve your own proposal)."""


class ActionReferenceError(Exception):
    """Raised when a proposed action references another tenant's data —
    e.g. a decision_id that exists, just not in the caller's organization."""


async def propose_action(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    proposed_by: uuid.UUID,
    decision_id: uuid.UUID | None,
    action_type: str,
    description: str,
    parameters: dict,
) -> Action:
    if action_type not in ACTION_TYPES_BY_NAME:
        raise ActionExecutionError(f"unknown action type: {action_type}")

    if decision_id is not None:
        result = await db.execute(
            select(Decision).where(
                Decision.id == decision_id, Decision.organization_id == organization_id
            )
        )
        if result.scalar_one_or_none() is None:
            raise ActionReferenceError(f"no decision found with id {decision_id}")

    action = Action(
        organization_id=organization_id,
        decision_id=decision_id,
        action_type=action_type,
        description=description,
        parameters=parameters,
        status="proposed",
        proposed_by=proposed_by,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    actions_total.labels(action_type=action.action_type, status=action.status).inc()
    return action


async def get_action_or_none(
    db: AsyncSession, organization_id: uuid.UUID, action_id: uuid.UUID
) -> Action | None:
    result = await db.execute(
        select(Action).where(Action.id == action_id, Action.organization_id == organization_id)
    )
    return result.scalar_one_or_none()


async def approve_action(db: AsyncSession, action: Action, approved_by: uuid.UUID) -> Action:
    if action.status != "proposed":
        raise ActionStateError(f"cannot approve an action with status '{action.status}'")
    if action.proposed_by == approved_by:
        raise ActionPermissionError("a user cannot approve their own proposed action")

    action.status = "approved"
    action.approved_by = approved_by
    await db.commit()
    await db.refresh(action)
    actions_total.labels(action_type=action.action_type, status=action.status).inc()
    return action


async def reject_action(db: AsyncSession, action: Action, rejected_by: uuid.UUID) -> Action:
    if action.status != "proposed":
        raise ActionStateError(f"cannot reject an action with status '{action.status}'")

    action.status = "rejected"
    action.approved_by = rejected_by
    await db.commit()
    await db.refresh(action)
    actions_total.labels(action_type=action.action_type, status=action.status).inc()
    return action


async def execute_action(db: AsyncSession, action: Action) -> Action:
    if action.status != "approved":
        raise ActionStateError(f"cannot execute an action with status '{action.status}'")

    spec = ACTION_TYPES_BY_NAME[action.action_type]
    try:
        result = await spec.execute(db, action.organization_id, action.parameters)
        action.status = "executed"
        action.result = result
    except ActionExecutionError as exc:
        action.status = "failed"
        action.result = {"error": str(exc)}

    action.executed_at = datetime.datetime.now(datetime.UTC)
    await db.commit()
    await db.refresh(action)
    actions_total.labels(action_type=action.action_type, status=action.status).inc()
    return action
