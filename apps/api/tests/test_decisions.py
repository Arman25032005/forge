import uuid

import pytest

from app.models.agent import AgentRun, AgentStep
from app.services.decision_synthesis import DecisionDraft
from app.services.decisions import get_decision_for_run, synthesize_and_persist_decision


class ScriptedSynthesizer:
    def __init__(self, draft: DecisionDraft) -> None:
        self._draft = draft
        self.received_steps = None

    async def synthesize(self, question, steps) -> DecisionDraft:  # noqa: ANN001
        self.received_steps = steps
        return self._draft


@pytest.mark.asyncio
async def test_synthesize_and_persist_decision(db_session) -> None:
    org_id = uuid.uuid4()
    run = AgentRun(
        organization_id=org_id,
        user_id=uuid.uuid4(),
        question="why did revenue decline?",
        status="completed",
        final_answer="churn",
    )
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        AgentStep(
            organization_id=org_id,
            run_id=run.id,
            step_index=0,
            tool_name="sql_query",
            tool_input={"sql": "SELECT 1"},
            tool_output=[{"1": 1}],
        )
    )
    await db_session.commit()

    draft = DecisionDraft(
        conclusion="Revenue declined due to churn.",
        confidence=0.9,
        evidence=[{"step_index": 0, "summary": "declining transactions"}],
        recommended_actions=["Contact at-risk accounts"],
    )
    synthesizer = ScriptedSynthesizer(draft)

    decision = await synthesize_and_persist_decision(db_session, run, synthesizer)

    assert decision.organization_id == org_id
    assert decision.run_id == run.id
    assert decision.conclusion == "Revenue declined due to churn."
    assert decision.status == "draft"
    assert len(synthesizer.received_steps) == 1
    assert synthesizer.received_steps[0].tool_name == "sql_query"

    fetched = await get_decision_for_run(db_session, org_id, run.id)
    assert fetched is not None
    assert fetched.id == decision.id


@pytest.mark.asyncio
async def test_get_decision_for_run_returns_none_when_absent(db_session) -> None:
    assert await get_decision_for_run(db_session, uuid.uuid4(), uuid.uuid4()) is None
