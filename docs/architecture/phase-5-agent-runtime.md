# Phase 5 — Agent Runtime

## Scope delivered
- **Tool registry** (`app/services/tools.py`): three tools an agent can
  call — `sql_query`, `retrieval_search`, `knowledge_graph_lookup` — each
  a thin wrapper around the already-implemented, already-tested Phase 3/4
  capability (the SQL tool, retrieval search, the knowledge graph). The
  runtime does not reimplement any data-access logic; it only adds
  argument validation, a JSON schema for the model, and a required
  permission per tool (`data.query` for SQL and graph lookups,
  `document.read` for retrieval).
- **Pluggable reasoning provider** (`app/services/llm.py`): an
  `LLMProvider` protocol with one method, `next_action(question, history,
  tools) -> AgentAction` (either a tool call or a final answer).
  `AnthropicProvider` is the real implementation — a manual, one-decision-
  per-call loop against the Claude API (not the beta tool runner, to keep
  the orchestration loop, permission checks, and persistence entirely
  under this codebase's control). The request/response translation
  (`_build_messages`, `_tool_to_anthropic_schema`, `_response_to_action`)
  is factored into pure functions so it can be tested without a network
  call.
- **Orchestration loop** (`app/services/agent_runtime.py`): `run_agent`
  persists an `AgentRun`, then repeatedly asks the provider for the next
  action, checks the calling user's role against the tool's required
  permission before running it (reusing the same `role_has_permission`
  used everywhere else in the app), executes the tool, records an
  `AgentStep` with the thought/tool/input/output, and feeds the real
  result back into the next reasoning call. Stops on a final answer or
  after `FORGE_AGENT_MAX_STEPS` (default 8) steps.
- **API** (`app/api/agents.py`): `POST /agents/runs` (gated by
  `agent.execute`) starts a run and returns it with its full step trace;
  `GET /agents/runs` and `GET /agents/runs/{id}` list/read a tenant's own
  runs. `AgentRun`/`AgentStep` are tenant-scoped exactly like every other
  enterprise table (`d00a00191413`-style migration, `73c37e6f9104`).

## What was actually tested, and how
73 tests in `apps/api/tests/` (up from 53 after Phase 4), all passing
against real SQLite through the actual FastAPI app / orchestration loop —
not mocks of our own code.

| Check | Test(s) | Result |
|---|---|---|
| Anthropic request/response translation (message building, tool schema, error framing, parsing tool calls vs. final answers) | `test_llm_translation.py` (6 tests) | pass |
| Each tool executes against real data and stays tenant-scoped | `test_tools.py` (6 tests) | pass |
| Orchestration loop: tool call → real tool output fed back → final answer | `test_run_agent_executes_tool_then_returns_final_answer` | pass |
| A role lacking a tool's permission gets a recorded tool error, not a crash or a silent bypass | `test_run_agent_records_permission_denied_tool_error` | pass |
| Runaway tool-calling stops at `max_steps` rather than looping forever | `test_run_agent_stops_at_max_steps` | pass |
| Steps are actually persisted, tenant-tagged | `test_run_agent_persists_steps` | pass |
| `POST /agents/runs` without a configured provider returns 503, not a stack trace or a fake answer | `test_agent_run_requires_configured_provider` | pass |
| OPERATOR (lacks `agent.execute`) cannot start a run | `test_operator_cannot_start_agent_run` | pass |
| Run listing/lookup work and 404 correctly | `test_agents_api.py` (2 more tests) | pass |

`ruff check`, `ruff format --check`, and `mypy app` are all clean. The
`agent_runs`/`agent_steps` migration was applied and rolled back against a
real SQLite file, chained on top of the Phase 4 migration.

## What was NOT tested (honest limitation, and it's the important one)
**No live call to the Claude API was made.** `FORGE_ANTHROPIC_API_KEY` is
unset in this development environment, so `AnthropicProvider` — the part
of this phase that actually reasons about a question and decides what to
do — has never been run against a real model. Everything it depends on
(`anthropic` 1.4.0 is installed; connectivity to `api.anthropic.com` was
confirmed reachable) is exercised except the credentialed call itself.
What *is* tested, thoroughly, is everything around that call: the request
it would send (via the pure translation functions), the loop that would
drive it (via `ScriptedProvider`, a deterministic test double substituted
for the real provider specifically to validate iteration, persistence,
and permission enforcement independent of model behavior), and the API's
honest failure mode when no key is present (503, not a fabricated
response). Configuring `FORGE_ANTHROPIC_API_KEY` and running a real
question end-to-end is the one remaining verification step, and it should
happen before this phase is treated as "the agent gives good answers" —
only "the harness around the agent behaves correctly" has been verified.

Other, smaller limitations:
- **One tool call per step, not parallel tool use.** If a model response
  contains multiple `tool_use` blocks, `_response_to_action` only acts on
  the first; this keeps persistence/permission-checking per-step simple
  at the cost of extra round trips for models that would otherwise batch
  calls.
- **History is resent in full on every call** rather than kept
  provider-side — simple and correct, but not efficient for long-running
  investigations; a real deployment would want prompt caching (the
  system prompt and tool definitions are already stable/first, which is
  the right shape for it) once a real model is in the loop.
- **No streaming** — each step is a blocking, non-streaming
  `messages.create` call.
- **Steps are only persisted at the end of a run** (on the final commit),
  not incrementally — a crash mid-run loses that run's steps rather than
  leaving a partial trace.

## Gate status
The orchestration harness — tool execution, permission enforcement,
persistence, step-limit handling, and the API around it — is implemented
and tested end-to-end with a substitute reasoning provider. The real
reasoning provider is implemented and its request/response handling is
unit-tested, but has not been exercised against Claude live, because no
API key is available in this environment. That is the explicit, named gap
this phase leaves for whoever configures a key next.
