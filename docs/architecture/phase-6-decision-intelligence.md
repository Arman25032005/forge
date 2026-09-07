# Phase 6 — Decision Intelligence

## Scope delivered
- **`Decision` model** (`app/models/decision.py`): tenant-scoped, tied to
  the `AgentRun` it was synthesized from — `conclusion` (text),
  `confidence` (float), `evidence` (JSON list of `{step_index, summary}`
  citations into that run's actual steps), `recommended_actions` (JSON
  list of strings), and `status` (`draft` — nothing beyond drafting
  exists yet; approval/execution is Phase 7's job, not this one's).
- **Decision synthesis** (`app/services/decision_synthesis.py`): turns a
  completed agent run's step trace into a `DecisionDraft` via a single
  structured-output call (`output_config: {format: {type: "json_schema",
  schema: DECISION_JSON_SCHEMA}}`), which guarantees the model's response
  is valid JSON matching the schema rather than free text to parse
  hopefully. As with Phase 5's `llm.py`, the prompt-building and response
  parsing are pure functions (`_build_synthesis_messages`,
  `_parse_decision_json`) so they're unit-tested without a network call.
- **Evidence grounding is enforced in code, not trusted from the model**:
  `_parse_decision_json` rejects any decision whose evidence cites a
  `step_index` that doesn't actually exist in the run it was synthesized
  from. A model asserting "step 7 shows X" when the run only ran 3 steps
  is a fabricated citation — this is caught and raises
  `DecisionSynthesisError` rather than being persisted as if it were a
  real citation. Confidence is also range-checked (`0 <= confidence <=
  1`) for the same reason: schema-valid JSON is not the same as
  semantically valid content.
- **API** (`POST /agents/runs/{run_id}/decision`, `GET
  /agents/runs/{run_id}/decision`, both under the existing `agents.py`
  router since a decision only exists in relation to a run): gated by
  `agent.execute` (the same permission that gates the run itself).
  Synthesizing a decision requires the run to be in `completed` status
  (400 otherwise — there's no evidence to synthesize from a run that's
  still going or that hit the step limit) and requires
  `FORGE_ANTHROPIC_API_KEY` to be configured (503 otherwise, same honest
  failure mode as Phase 5's `/agents/runs`).

## What was actually tested, and how
84 tests in `apps/api/tests/` (up from 73 after Phase 5), all passing
against real SQLite through the actual FastAPI app / synthesis pipeline —
not mocks of our own code.

| Check | Test(s) | Result |
|---|---|---|
| Prompt construction includes the question and every step's tool/input/output | `test_build_synthesis_messages_includes_question_and_steps` | pass |
| Valid structured-output JSON parses into a `DecisionDraft` correctly | `test_parse_decision_json_valid` | pass |
| A citation to a step index that doesn't exist in the run is rejected, not silently accepted | `test_parse_decision_json_rejects_fabricated_evidence` | pass |
| Out-of-range confidence is rejected | `test_parse_decision_json_rejects_out_of_range_confidence` | pass |
| Malformed JSON from the model is rejected with a clear error | `test_parse_decision_json_rejects_invalid_json` | pass |
| A decision is actually persisted, tenant-tagged, and readable back | `test_synthesize_and_persist_decision` | pass |
| Synthesizing from a non-`completed` run is rejected (400) | `test_decision_requires_completed_run` | pass |
| Synthesizing without a configured provider is rejected (503, not a fabricated decision) | `test_decision_requires_configured_provider` | pass |
| Decisions are tenant-isolated; unknown run/decision 404s | `test_decision_endpoint_404_for_unknown_run`, `test_decision_is_tenant_isolated` | pass |

`ruff check`, `ruff format --check`, and `mypy app` are all clean. The
`decisions` migration was applied and rolled back against a real SQLite
file, chained on top of the Phase 5 migration.

## What was NOT tested (honest limitation — same root cause as Phase 5)
**No live call to the Claude API was made**, for the same reason as
Phase 5: `FORGE_ANTHROPIC_API_KEY` is unset in this environment. Every
test exercising `AnthropicDecisionSynthesizer` uses `ScriptedSynthesizer`,
a deterministic test double, rather than the real class. What's verified
is the harness around the model call — prompt construction, structured-
output request shape, grounding/range validation of whatever comes back,
persistence, and the API's failure modes. What's *not* verified is
whether a real model, given a real investigation trace, produces useful
conclusions and sensible recommended actions — that requires a
configured key and is the next verification step before this phase's
output should be trusted for an actual business decision.

Other limitations:
- **A decision is a manual follow-up call, not automatic.** `run_agent`
  (Phase 5) does not synthesize a decision when it completes; a caller
  must separately call `POST /agents/runs/{id}/decision`. This keeps
  investigation and synthesis as separately-retriable steps (a bad
  synthesis doesn't require re-running the whole investigation) at the
  cost of an extra call.
- **One decision synthesis attempt, no retry on a validation failure.**
  If the model's structured output cites a fabricated step or an
  out-of-range confidence, the endpoint returns 502 and nothing is
  persisted — there's no automatic "ask the model to try again" loop.
- **`recommended_actions` are plain strings**, not structured, executable
  action proposals — turning a recommendation into something that can
  actually be proposed and approved is Phase 7's job.

## Gate status
Structured, evidence-backed decision synthesis is implemented, with
evidence grounding and confidence validated in code rather than trusted
from model output, and is tested end-to-end with a substitute synthesizer
covering the full happy path and every named failure mode. The real
Anthropic-backed synthesizer's request/response handling is unit-tested
but — like Phase 5's `AnthropicProvider` — has not been exercised against
a live model, because no API key is available here. That gap is inherited
from, not new to, this phase.
