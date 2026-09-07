import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.core.config import get_settings
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.agent import AgentRun, AgentStep
from app.schemas.agent import AgentRunCreate, AgentRunOut, AgentStepOut
from app.services.agent_runtime import run_agent
from app.services.llm import AnthropicProvider

router = APIRouter(prefix="/agents", tags=["agents"])


async def _to_run_out(db: AsyncSession, run: AgentRun) -> AgentRunOut:
    result = await db.execute(
        select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.step_index)
    )
    steps = list(result.scalars().all())
    return AgentRunOut(
        id=run.id,
        question=run.question,
        status=run.status,
        final_answer=run.final_answer,
        created_at=run.created_at,
        steps=[AgentStepOut.model_validate(step) for step in steps],
    )


@router.post("/runs", response_model=AgentRunOut, status_code=201)
async def create_run(
    payload: AgentRunCreate,
    auth: AuthContext = Depends(require_permission(Permission.AGENT_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> AgentRunOut:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="agent runtime not configured: FORGE_ANTHROPIC_API_KEY is not set",
        )
    provider = AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

    run = await run_agent(
        db,
        organization_id=auth.organization_id,
        user_id=auth.user_id,
        role=auth.role,
        question=payload.question,
        provider=provider,
        max_steps=settings.agent_max_steps,
    )
    return await _to_run_out(db, run)


@router.get("/runs", response_model=list[AgentRunOut])
async def list_runs(
    auth: AuthContext = Depends(require_permission(Permission.AGENT_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> list[AgentRunOut]:
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.organization_id == auth.organization_id)
        .order_by(AgentRun.created_at.desc())
    )
    runs = list(result.scalars().all())
    return [await _to_run_out(db, run) for run in runs]


@router.get("/runs/{run_id}", response_model=AgentRunOut)
async def get_run(
    run_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.AGENT_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> AgentRunOut:
    result = await db.execute(
        select(AgentRun).where(
            AgentRun.id == run_id, AgentRun.organization_id == auth.organization_id
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    return await _to_run_out(db, run)
