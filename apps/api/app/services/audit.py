import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def record_event(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    resource: str,
    outcome: str = "success",
    context: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        resource=resource,
        outcome=outcome,
        context=context or {},
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry
