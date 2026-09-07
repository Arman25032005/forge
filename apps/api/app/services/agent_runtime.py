import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import agent_runs_total, agent_tool_calls_total
from app.core.permissions import role_has_permission
from app.models.agent import AgentRun, AgentStep
from app.models.user import Role
from app.services.llm import AgentAction, LLMProvider, StepRecord
from app.services.tools import TOOLS, TOOLS_BY_NAME, ToolExecutionError

MAX_STEPS_DEFAULT = 8


async def run_agent(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    question: str,
    provider: LLMProvider,
    max_steps: int = MAX_STEPS_DEFAULT,
) -> AgentRun:
    run = AgentRun(
        organization_id=organization_id, user_id=user_id, question=question, status="running"
    )
    db.add(run)
    await db.flush()

    history: list[StepRecord] = []

    for step_index in range(max_steps):
        action: AgentAction = await provider.next_action(question, history, TOOLS)

        if action.kind == "final_answer":
            run.status = "completed"
            run.final_answer = action.final_answer
            await db.commit()
            await db.refresh(run)
            agent_runs_total.labels(status=run.status).inc()
            return run

        tool_input = action.tool_input or {}
        tool_output: object = None
        tool_error: str | None = None

        tool = TOOLS_BY_NAME.get(action.tool_name or "")
        if tool is None:
            tool_error = f"unknown tool: {action.tool_name}"
        elif not role_has_permission(role, tool.permission):
            tool_error = f"role '{role.value}' lacks permission '{tool.permission}' for this tool"
        else:
            try:
                tool_output = await tool.run(db, organization_id, tool_input)
            except ToolExecutionError as exc:
                tool_error = str(exc)

        agent_tool_calls_total.labels(
            tool_name=action.tool_name or "unknown", outcome="error" if tool_error else "ok"
        ).inc()

        db.add(
            AgentStep(
                organization_id=organization_id,
                run_id=run.id,
                step_index=step_index,
                thought=action.thought,
                tool_name=action.tool_name,
                tool_input=tool_input,
                tool_output={"error": tool_error} if tool_error is not None else tool_output,
            )
        )
        history.append(
            StepRecord(
                tool_name=action.tool_name or "",
                tool_input=tool_input,
                tool_output=tool_output,
                tool_error=tool_error,
            )
        )

    run.status = "max_steps_exceeded"
    await db.commit()
    await db.refresh(run)
    agent_runs_total.labels(status=run.status).inc()
    return run
