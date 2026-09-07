import uuid

import pytest

from app.models.enterprise import Customer
from app.services.action_types import ACTION_TYPES_BY_NAME, ActionExecutionError


@pytest.mark.asyncio
async def test_flag_customer_at_risk_updates_status(db_session) -> None:
    org_id = uuid.uuid4()
    customer = Customer(organization_id=org_id, name="Acme", status="active")
    db_session.add(customer)
    await db_session.commit()

    spec = ACTION_TYPES_BY_NAME["flag_customer_at_risk"]
    result = await spec.execute(db_session, org_id, {"customer_id": str(customer.id)})

    assert result["previous_status"] == "active"
    assert result["new_status"] == "at_risk"
    await db_session.refresh(customer)
    assert customer.status == "at_risk"


@pytest.mark.asyncio
async def test_flag_customer_at_risk_is_tenant_scoped(db_session) -> None:
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    customer = Customer(organization_id=org_a, name="Acme", status="active")
    db_session.add(customer)
    await db_session.commit()

    spec = ACTION_TYPES_BY_NAME["flag_customer_at_risk"]
    with pytest.raises(ActionExecutionError):
        await spec.execute(db_session, org_b, {"customer_id": str(customer.id)})


@pytest.mark.asyncio
async def test_flag_customer_at_risk_requires_customer_id(db_session) -> None:
    spec = ACTION_TYPES_BY_NAME["flag_customer_at_risk"]
    with pytest.raises(ActionExecutionError):
        await spec.execute(db_session, uuid.uuid4(), {})


@pytest.mark.asyncio
async def test_create_support_ticket_creates_real_row(db_session) -> None:
    from sqlalchemy import select

    from app.models.enterprise import SupportTicket

    org_id = uuid.uuid4()
    customer = Customer(organization_id=org_id, name="Acme")
    db_session.add(customer)
    await db_session.commit()

    spec = ACTION_TYPES_BY_NAME["create_support_ticket"]
    result = await spec.execute(
        db_session,
        org_id,
        {"customer_id": str(customer.id), "subject": "Follow up on churn risk"},
    )

    ticket_id = uuid.UUID(result["support_ticket_id"])
    row = (
        await db_session.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))
    ).scalar_one()
    assert row.subject == "Follow up on churn risk"
    assert row.customer_id == customer.id


@pytest.mark.asyncio
async def test_manual_task_has_no_side_effect(db_session) -> None:
    spec = ACTION_TYPES_BY_NAME["manual_task"]
    result = await spec.execute(db_session, uuid.uuid4(), {"note": "call the customer"})
    assert "no automated side effect" in result["note"]
