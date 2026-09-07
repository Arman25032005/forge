import uuid

import pytest
from sqlalchemy import select

from app.models.enterprise import Customer
from app.models.user import Role
from app.services.agent_runtime import run_agent
from app.services.llm import AgentAction, StepRecord


class ScriptedProvider:
    """A deterministic reasoning provider for testing the orchestration
    loop's control flow (iteration, persistence, permission gating,
    step-limit handling) independent of any real model."""

    def __init__(self, actions: list[AgentAction]) -> None:
        self._actions = actions
        self.calls: list[tuple[str, list[StepRecord]]] = []

    async def next_action(self, question, history, tools) -> AgentAction:  # noqa: ANN001
        self.calls.append((question, list(history)))
        return self._actions[len(self.calls) - 1]


class LoopingProvider:
    """Always requests the same tool call — used to test max-step truncation."""

    async def next_action(self, question, history, tools) -> AgentAction:  # noqa: ANN001
        return AgentAction(kind="tool_call", tool_name="sql_query", tool_input={"sql": "SELECT 1"})


@pytest.mark.asyncio
async def test_run_agent_executes_tool_then_returns_final_answer(db_session) -> None:
    org_id = uuid.uuid4()
    customer = Customer(organization_id=org_id, name="Acme")
    db_session.add(customer)
    await db_session.commit()

    provider = ScriptedProvider(
        [
            AgentAction(
                kind="tool_call",
                thought="checking customers",
                tool_name="sql_query",
                tool_input={"sql": "SELECT name FROM customers"},
            ),
            AgentAction(kind="final_answer", final_answer="There is one customer: Acme."),
        ]
    )

    run = await run_agent(
        db_session,
        organization_id=org_id,
        user_id=uuid.uuid4(),
        role=Role.ANALYST,
        question="How many customers do we have?",
        provider=provider,
    )

    assert run.status == "completed"
    assert run.final_answer == "There is one customer: Acme."
    assert len(provider.calls) == 2
    # second call's history reflects the first step's real tool output
    _, second_call_history = provider.calls[1]
    assert second_call_history[0].tool_output == [{"name": "Acme"}]


@pytest.mark.asyncio
async def test_run_agent_records_permission_denied_tool_error(db_session) -> None:
    org_id = uuid.uuid4()
    provider = ScriptedProvider(
        [
            AgentAction(kind="tool_call", tool_name="sql_query", tool_input={"sql": "SELECT 1"}),
            AgentAction(kind="final_answer", final_answer="done"),
        ]
    )

    run = await run_agent(
        db_session,
        organization_id=org_id,
        user_id=uuid.uuid4(),
        role=Role.VIEWER,  # VIEWER lacks data.query
        question="q",
        provider=provider,
    )

    assert run.status == "completed"
    _, second_call_history = provider.calls[1]
    assert second_call_history[0].tool_error is not None
    assert "lacks permission" in second_call_history[0].tool_error


@pytest.mark.asyncio
async def test_run_agent_stops_at_max_steps(db_session) -> None:
    org_id = uuid.uuid4()
    run = await run_agent(
        db_session,
        organization_id=org_id,
        user_id=uuid.uuid4(),
        role=Role.ANALYST,
        question="q",
        provider=LoopingProvider(),
        max_steps=3,
    )
    assert run.status == "max_steps_exceeded"
    assert run.final_answer is None


@pytest.mark.asyncio
async def test_run_agent_persists_steps(db_session) -> None:
    from app.models.agent import AgentStep

    org_id = uuid.uuid4()
    provider = ScriptedProvider(
        [
            AgentAction(kind="tool_call", tool_name="sql_query", tool_input={"sql": "SELECT 1"}),
            AgentAction(kind="final_answer", final_answer="ok"),
        ]
    )
    run = await run_agent(
        db_session,
        organization_id=org_id,
        user_id=uuid.uuid4(),
        role=Role.ANALYST,
        question="q",
        provider=provider,
    )

    result = await db_session.execute(select(AgentStep).where(AgentStep.run_id == run.id))
    steps = list(result.scalars().all())
    assert len(steps) == 1
    assert steps[0].tool_name == "sql_query"
    assert steps[0].organization_id == org_id
