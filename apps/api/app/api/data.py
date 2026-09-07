from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.schemas.data import SQLQueryRequest, SQLQueryResponse
from app.services.audit import record_event
from app.services.sql_tool import ALLOWED_TABLES, SQLValidationError, execute_sql_tool

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/catalog")
async def data_catalog(
    auth: AuthContext = Depends(require_permission(Permission.DATA_QUERY)),
) -> dict:
    return {"tables": sorted(ALLOWED_TABLES)}


@router.post("/query", response_model=SQLQueryResponse)
async def run_query(
    payload: SQLQueryRequest,
    auth: AuthContext = Depends(require_permission(Permission.DATA_QUERY)),
    db: AsyncSession = Depends(get_db),
) -> SQLQueryResponse:
    try:
        rows = await execute_sql_tool(db, raw_sql=payload.sql, organization_id=auth.organization_id)
    except SQLValidationError as exc:
        await record_event(
            db,
            organization_id=auth.organization_id,
            user_id=auth.user_id,
            action="data.query",
            resource="sql_tool",
            outcome="rejected",
            context={"reason": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await record_event(
        db,
        organization_id=auth.organization_id,
        user_id=auth.user_id,
        action="data.query",
        resource="sql_tool",
        context={"row_count": len(rows)},
    )
    return SQLQueryResponse(rows=rows, row_count=len(rows))
