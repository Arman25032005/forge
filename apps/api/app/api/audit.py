from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.audit import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
async def list_audit_logs(
    auth: AuthContext = Depends(require_permission(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    # Every audit query is scoped to the caller's organization_id from the
    # verified token — never from a client-supplied tenant parameter — so a
    # user can never read another tenant's audit trail.
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.organization_id == auth.organization_id)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "action": log.action,
            "resource": log.resource,
            "outcome": log.outcome,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
