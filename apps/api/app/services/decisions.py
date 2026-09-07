import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun, AgentStep
from app.models.decision import Decision
from app.services.decision_synthesis import DecisionSynthesizer, StepSummary


async def synthesize_and_persist_decision(
    db: AsyncSession, run: AgentRun, synthesizer: DecisionSynthesizer
) -> Decision:
    result = await db.execute(
        select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.step_index)
    )
    steps = list(result.scalars().all())
    summaries = [
        StepSummary(
            step_index=step.step_index,
            tool_name=step.tool_name,
            tool_input=step.tool_input,
            tool_output=step.tool_output,
        )
        for step in steps
    ]

    draft = await synthesizer.synthesize(run.question, summaries)

    decision = Decision(
        organization_id=run.organization_id,
        run_id=run.id,
        conclusion=draft.conclusion,
        confidence=draft.confidence,
        evidence=draft.evidence,
        recommended_actions=draft.recommended_actions,
        status="draft",
    )
    db.add(decision)
    await db.commit()
    await db.refresh(decision)
    return decision


async def get_decision_for_run(
    db: AsyncSession, organization_id: uuid.UUID, run_id: uuid.UUID
) -> Decision | None:
    result = await db.execute(
        select(Decision)
        .where(Decision.run_id == run_id, Decision.organization_id == organization_id)
        .order_by(Decision.created_at.desc())
    )
    return result.scalars().first()
