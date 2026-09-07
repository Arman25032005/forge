import uuid

import pytest

from app.models.enterprise import Customer
from app.services.actions import (
    ActionPermissionError,
    ActionStateError,
    approve_action,
    execute_action,
    propose_action,
    reject_action,
)


@pytest.mark.asyncio
async def test_full_propose_approve_execute_lifecycle(db_session) -> None:
    org_id = uuid.uuid4()
    proposer, approver = uuid.uuid4(), uuid.uuid4()
    customer = Customer(organization_id=org_id, name="Acme", status="active")
    db_session.add(customer)
    await db_session.commit()

    action = await propose_action(
        db_session,
        organization_id=org_id,
        proposed_by=proposer,
        decision_id=None,
        action_type="flag_customer_at_risk",
        description="Flag Acme as at-risk based on churn signals",
        parameters={"customer_id": str(customer.id)},
    )
    assert action.status == "proposed"

    action = await approve_action(db_session, action, approved_by=approver)
    assert action.status == "approved"
    assert action.approved_by == approver

    action = await execute_action(db_session, action)
    assert action.status == "executed"
    assert action.executed_at is not None
    assert action.result["new_status"] == "at_risk"


@pytest.mark.asyncio
async def test_cannot_approve_own_proposal(db_session) -> None:
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    action = await propose_action(
        db_session,
        organization_id=org_id,
        proposed_by=user_id,
        decision_id=None,
        action_type="manual_task",
        description="do a thing",
        parameters={},
    )
    with pytest.raises(ActionPermissionError):
        await approve_action(db_session, action, approved_by=user_id)


@pytest.mark.asyncio
async def test_cannot_execute_unapproved_action(db_session) -> None:
    action = await propose_action(
        db_session,
        organization_id=uuid.uuid4(),
        proposed_by=uuid.uuid4(),
        decision_id=None,
        action_type="manual_task",
        description="do a thing",
        parameters={},
    )
    with pytest.raises(ActionStateError):
        await execute_action(db_session, action)


@pytest.mark.asyncio
async def test_cannot_approve_already_rejected_action(db_session) -> None:
    org_id = uuid.uuid4()
    proposer, approver = uuid.uuid4(), uuid.uuid4()
    action = await propose_action(
        db_session,
        organization_id=org_id,
        proposed_by=proposer,
        decision_id=None,
        action_type="manual_task",
        description="do a thing",
        parameters={},
    )
    action = await reject_action(db_session, action, rejected_by=approver)
    assert action.status == "rejected"

    with pytest.raises(ActionStateError):
        await approve_action(db_session, action, approved_by=approver)


@pytest.mark.asyncio
async def test_failed_execution_records_error_without_crashing(db_session) -> None:
    org_id = uuid.uuid4()
    proposer, approver = uuid.uuid4(), uuid.uuid4()
    action = await propose_action(
        db_session,
        organization_id=org_id,
        proposed_by=proposer,
        decision_id=None,
        action_type="flag_customer_at_risk",
        description="flag a customer that doesn't exist",
        parameters={"customer_id": str(uuid.uuid4())},
    )
    action = await approve_action(db_session, action, approved_by=approver)
    action = await execute_action(db_session, action)

    assert action.status == "failed"
    assert "error" in action.result
