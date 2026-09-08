# Phase 10 — Groq Integration (and Live Verification of Phases 5–9)

## Scope
Phases 5, 6, 8, and 9 all shipped real code (`AnthropicProvider`,
`AnthropicDecisionSynthesizer`, the retrieval/agent evaluation harness,
prompt-injection framing) that had never been exercised against a live
model — every one of those phase docs says so explicitly, because no API
key was available in this environment. This phase adds a second
reasoning-provider implementation on top of the existing `LLMProvider` /
`DecisionSynthesizer` protocols — Groq's OpenAI-compatible chat
completions API — and, with a real Groq key now configured, actually runs
the agent and decision-synthesis pipelines against a live model for the
first time in this project. That live run surfaced three real bugs that
no amount of unit testing against synthetic tool-call sequences had
caught, because they only manifest against a real model's actual output
shape. All three are fixed and covered by regression tests below.

## Scope delivered
- **`GroqProvider`** (`app/services/llm.py`) and **`GroqDecisionSynthesizer`**
  (`app/services/decision_synthesis.py`): implement the same
  `LLMProvider`/`DecisionSynthesizer` protocols Anthropic's
  implementations use, so the orchestration loop and decision-synthesis
  pipeline are unchanged — only the reasoning backend differs. Uses
  OpenAI-style tool-calling (`tools`/`tool_choice`, `role: "tool"` results)
  and OpenAI-style structured output (`response_format:
  {type: "json_schema", ...}`) instead of Anthropic's shapes; the
  request/response translation is pure functions
  (`_tool_to_openai_schema`, `_build_openai_messages`,
  `_openai_message_to_action`) tested the same way the Anthropic
  translation functions are.
- **`get_llm_provider()` / `get_decision_synthesizer()` factories**:
  pick Groq first if `FORGE_GROQ_API_KEY` is set, else Anthropic, else
  raise a clear "not configured" error. `app/api/agents.py` now calls
  these instead of hardcoding `AnthropicProvider`.
- **A live agent investigation actually ran and completed**: asked
  "Which customers have overdue invoices?", the agent made 3 real tool
  calls (`sql_query` ×3) against real generated data and returned a
  correct, evidence-backed final answer listing 15 real customer names.
  `POST /agents/runs/{id}/decision` then synthesized a structured
  decision from that same run — `confidence: 0.98`, evidence correctly
  citing the exact step that produced the customer list, and three
  concrete recommended actions. This is the first time in this project
  that "the AI agent gives a real, evidence-backed answer" has been
  observed rather than assumed.
- **A second, harder live investigation** ("Why might some customers be
  at risk of churning?") made 6 tool calls — 5 `sql_query` (including a
  join with table aliases) and 1 `knowledge_graph_lookup` drilling into a
  specific flagged customer — with zero occurrences of any of the three
  bugs below, before failing on the 7th call with a transient Groq
  connection error, caught cleanly by the new error handling rather than
  crashing.

## Three real bugs found live, fixed, and now regression-tested

1. **SQL tool dropped table aliases** (`app/services/sql_tool.py`). The
   tenant-scoping rewrite always re-aliased a rewritten subquery to the
   bare table name, discarding any alias the query itself used. A model
   naturally writes `FROM support_tickets st JOIN customers c ON
   st.customer_id = c.id`; the rewrite turned `st`/`c` references into
   "no such column" errors on every single query using an alias — which
   is most real, non-trivial SQL. Fixed by preserving `table.alias_or_name`
   when rewriting. `test_aliased_join_preserves_alias_references`.

2. **The SQL tool gave the model table names but no column names**
   (`app/services/tools.py`, `app/services/sql_tool.py`). With nothing
   but `customers, products, ... invoices` to go on, the model
   confidently guessed plausible-but-wrong columns (`invoices.paid`,
   `invoices.invoice_id` instead of the real `status`, `id`). Fixed by
   introspecting the actual SQLAlchemy models
   (`sql_tool.SCHEMA_DESCRIPTION`) and including real column names in the
   tool's description; `/data/catalog` now also returns per-table columns
   for the same reason. `test_data_catalog_includes_real_column_names`.

3. **A syntactically valid, schema-invalid query crashed the whole
   request with a 500** (`app/services/sql_tool.py`,
   `app/services/llm.py`, `app/services/agent_runtime.py`). Two related
   issues, both found from the same live failure: (a) a query that parses
   fine but references a column that doesn't exist (even a real, if
   imperfect, model will sometimes still get this wrong) raised an
   uncaught `sqlalchemy.exc.OperationalError` instead of the tool's own
   `SQLValidationError` — fixed by catching `DBAPIError` in
   `execute_sql_tool` and re-raising as `SQLValidationError` (with a
   `db.rollback()` first, since the session is reused for later steps in
   the same run and SQLAlchemy refuses further use after a failed
   flush/execute without one) — `test_nonexistent_column_raises_
   validation_error_not_crash`, `test_session_is_usable_after_a_failed_
   query`; (b) separately, a real SDK-level failure (Groq's free-tier
   429/413 token-rate-limit, or a transient connection error) also
   propagated uncaught all the way to a 500 — fixed by having both
   providers catch their SDK's base API error and re-raise as a shared
   `ProviderError`, which `run_agent` now catches and turns into a clean
   `status: "failed"` run with the error message recorded (new `AgentRun.error`
   column, migration `2b557369a291`) instead of crashing the request —
   `test_run_agent_fails_cleanly_on_provider_error`. A related, smaller
   fix: resending the full tool-call history every step (an accepted
   simplification since Phase 5) compounds token usage across steps and
   pushed a 4-step conversation over Groq's free-tier 8,000 TPM budget —
   large tool results are now truncated specifically in what's sent to
   the model (`MAX_TOOL_RESULT_CHARS_IN_PROMPT`, `_truncate_for_prompt`),
   while the full untruncated result is still what's persisted to
   `AgentStep` and what decision synthesis reads —
   `test_truncate_for_prompt_caps_long_content`.

## What was actually tested, and how
The full test suite (up from 118 after Phase 9) passes against real
SQLite through the actual FastAPI app, with the pure-function Groq
translation logic tested the same way Anthropic's has been since Phase 5
— and, uniquely for this phase, real live verification against Groq
happened too (documented above), not just unit tests against synthetic
provider doubles. `ruff check`, `ruff format --check`, and `mypy app` are
all clean. The `agent_runs.error` migration was applied and rolled back
against a real SQLite file, chained on top of Phase 9's migration.

**Test-suite hygiene note, itself found live**: the first live run
accidentally happened *during* `pytest`, not manually — because a local
`.env` file (created for interactive dev use, gitignored, containing the
real Groq key) was being picked up by `get_settings()` inside the test
process, and one of the "returns 503 when unconfigured" tests silently
became "makes a real, billed API call" instead. Fixed with an autouse
`monkeypatch` fixture in `conftest.py` that forces both provider keys
empty for every test regardless of local `.env` contents — the test
suite must never depend on a developer's local secrets or hit a real
network.

## What was NOT tested (honest limitations)
- **`AnthropicProvider`/`AnthropicDecisionSynthesizer` are still
  unverified against a live model** — this phase only obtained a Groq
  key, not an Anthropic one. Everything said about them in Phases 5/6
  still stands.
- **Groq's free tier is rate-limited enough to matter.** The `on_demand`
  service tier hit both RPM and TPM limits during ordinary multi-step
  investigations; the SDK's own retry/backoff got most requests through
  eventually, but a run can now take over a minute in wall-clock time
  purely from waiting out those retries, and one run failed outright on a
  transient connection error. Nothing here is a code bug — it's the
  actual, current constraint of running production traffic against a
  free-tier key, and it will not go away without a paid tier.
- **Prompt-injection resistance is still unverified** — this phase
  proved the harness works end-to-end with a live model, not that Groq's
  `openai/gpt-oss-120b` specifically resists a poisoned document. That
  would need a deliberate adversarial test case, which wasn't run here.
- **Only two live questions were asked.** This is evidence the pipeline
  *can* work, not a systematic evaluation of answer quality — that's what
  `scripts/evaluate_agent.py` (Phase 8) is for, and it has still not been
  run as a full suite against Groq.
- **No frontend was built in this phase** — despite the phase name,
  scope ran long on backend fixes surfaced by the first live test. A
  frontend remains apps/web's untouched Next.js scaffold.

## Gate status
For the first time in this project, "the AI agent produces a real,
evidence-backed answer" is an observed fact, not an assumption carried
forward from unit tests against a scripted double. Three bugs that only
a live model could have surfaced are fixed and regression-tested. The
frontend work implied by this phase's original scope has not started.
