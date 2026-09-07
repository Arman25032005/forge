"""Evaluate the investigation agent against a small golden question set.

Unlike `evaluate_retrieval.py`, this cannot run in this development
environment: it drives the real `AnthropicProvider` (Phase 5), which
requires `FORGE_ANTHROPIC_API_KEY`, unset here. It is implemented and
ready to run once a key is configured — see
docs/architecture/phase-8-observability-evaluation.md for exactly what
that gap is and why it exists.

Each case is a business question with keywords a competent, evidence-based
answer should mention, and a minimum number of tool calls a real
investigation should need (an agent that answers "why did revenue
decline" without ever querying the data is not investigating). This is a
smoke-level eval — a real evaluation suite would use an LLM-as-judge or
human grading against a larger, curated question set; this checks the
minimum bar (used tools, used the right ones, mentioned the right facts).

Usage (requires FORGE_ANTHROPIC_API_KEY):
    python scripts/evaluate_agent.py --org-slug acme
"""

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.agent import AgentStep
from app.models.organization import Organization
from app.models.user import Role
from app.services.agent_runtime import run_agent
from app.services.llm import AnthropicProvider


@dataclass(frozen=True)
class EvalCase:
    question: str
    expected_keywords: list[str]
    min_tool_calls: int


CASES: list[EvalCase] = [
    EvalCase(
        question="Why might revenue be declining among some customers this quarter?",
        expected_keywords=["churn", "declin", "ticket", "competitor", "risk"],
        min_tool_calls=1,
    ),
    EvalCase(
        question="Are there any customers showing signs of being at risk of churning?",
        expected_keywords=["at_risk", "at risk", "declin", "support"],
        min_tool_calls=1,
    ),
]


async def _get_org_id(db, org_slug: str):
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if org is None:
        raise SystemExit(f"no organization with slug '{org_slug}'")
    return org.id


async def evaluate(org_slug: str) -> None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise SystemExit(
            "FORGE_ANTHROPIC_API_KEY is not set — this evaluation drives a real "
            "model and cannot run without one."
        )
    provider = AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

    async with async_session_factory() as db:
        org_id = await _get_org_id(db, org_slug)

        passed = 0
        for case in CASES:
            run = await run_agent(
                db,
                organization_id=org_id,
                user_id=org_id,  # evaluation has no real user; org id is a stable placeholder
                role=Role.ADMIN,
                question=case.question,
                provider=provider,
            )
            answer = (run.final_answer or "").lower()
            keyword_hit = any(kw.lower() in answer for kw in case.expected_keywords)
            step_count_result = await db.execute(
                select(AgentStep).where(AgentStep.run_id == run.id)
            )
            tool_call_count = len(step_count_result.scalars().all())
            ok = (
                run.status == "completed" and keyword_hit and tool_call_count >= case.min_tool_calls
            )
            passed += int(ok)
            print(f"[{'PASS' if ok else 'FAIL'}] {case.question!r}")
            print(f"  status={run.status} answer={answer[:200]!r}")

        print(f"\n{passed}/{len(CASES)} cases passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org-slug", required=True)
    args = parser.parse_args()
    asyncio.run(evaluate(args.org_slug))


if __name__ == "__main__":
    main()
