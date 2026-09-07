"""The kinds of actions an approved Action can actually execute.

Two of these have a real, verifiable side effect against this
organization's own data (`flag_customer_at_risk`, `create_support_ticket`)
— there is no external CRM/email/Slack integration in this codebase, so
those are the only side effects that can be executed and tested honestly.
`manual_task` deliberately does nothing: it exists because a recommended
action from Phase 6 ("reach out to the customer") is often something only
a human can actually do — executing it just records that a human marked
it done, rather than pretending the system performed an external action
it has no way to perform.
"""

import datetime
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Customer, SupportTicket


class ActionExecutionError(Exception):
    pass


class ActionExecutor(Protocol):
    async def __call__(
        self, db: AsyncSession, organization_id: uuid.UUID, parameters: dict[str, Any]
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ActionTypeSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    execute: ActionExecutor


async def _get_customer(
    db: AsyncSession, organization_id: uuid.UUID, customer_id: uuid.UUID
) -> Customer:
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id, Customer.organization_id == organization_id
        )
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise ActionExecutionError(f"no customer found with id {customer_id}")
    return customer


async def _flag_customer_at_risk(
    db: AsyncSession, organization_id: uuid.UUID, parameters: dict[str, Any]
) -> dict[str, Any]:
    customer_id_raw = parameters.get("customer_id")
    if not customer_id_raw:
        raise ActionExecutionError("'customer_id' is required")
    try:
        customer_id = uuid.UUID(str(customer_id_raw))
    except ValueError as exc:
        raise ActionExecutionError(f"invalid customer_id: {customer_id_raw}") from exc

    customer = await _get_customer(db, organization_id, customer_id)
    previous_status = customer.status
    customer.status = "at_risk"
    await db.flush()
    return {
        "customer_id": str(customer.id),
        "previous_status": previous_status,
        "new_status": "at_risk",
    }


async def _create_support_ticket(
    db: AsyncSession, organization_id: uuid.UUID, parameters: dict[str, Any]
) -> dict[str, Any]:
    customer_id_raw = parameters.get("customer_id")
    subject = parameters.get("subject")
    if not customer_id_raw or not subject:
        raise ActionExecutionError("'customer_id' and 'subject' are required")
    try:
        customer_id = uuid.UUID(str(customer_id_raw))
    except ValueError as exc:
        raise ActionExecutionError(f"invalid customer_id: {customer_id_raw}") from exc

    await _get_customer(db, organization_id, customer_id)

    ticket = SupportTicket(
        organization_id=organization_id,
        customer_id=customer_id,
        subject=str(subject),
        severity=str(parameters.get("severity", "normal")),
        opened_on=datetime.date.today(),
    )
    db.add(ticket)
    await db.flush()
    return {"support_ticket_id": str(ticket.id)}


async def _manual_task(
    db: AsyncSession, organization_id: uuid.UUID, parameters: dict[str, Any]
) -> dict[str, Any]:
    return {"note": "no automated side effect — this action records that a human completed it"}


ACTION_TYPES: list[ActionTypeSpec] = [
    ActionTypeSpec(
        name="flag_customer_at_risk",
        description="Set a customer's status to 'at_risk'.",
        input_schema={
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
        execute=_flag_customer_at_risk,
    ),
    ActionTypeSpec(
        name="create_support_ticket",
        description="Open a support ticket for a customer.",
        input_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "subject": {"type": "string"},
                "severity": {"type": "string", "default": "normal"},
            },
            "required": ["customer_id", "subject"],
        },
        execute=_create_support_ticket,
    ),
    ActionTypeSpec(
        name="manual_task",
        description=(
            "A recommendation for a human to act on outside this system "
            "(e.g. a phone call). Executing it has no automated side effect."
        ),
        input_schema={"type": "object", "properties": {"note": {"type": "string"}}},
        execute=_manual_task,
    ),
]

ACTION_TYPES_BY_NAME: dict[str, ActionTypeSpec] = {spec.name: spec for spec in ACTION_TYPES}
