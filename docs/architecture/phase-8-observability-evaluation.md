# Phase 8 — Observability + Evaluation

## Scope delivered

### Observability
- **`GET /metrics`** (`app/core/metrics.py`, wired in `app/main.py`):
  Prometheus text-format counters and a histogram —
  `forge_http_requests_total` / `forge_http_request_duration_seconds`
  (labeled by method and the *matched route template*, e.g.
  `/agents/runs/{run_id}`, not the raw URL — so per-request UUIDs don't
  create unbounded label cardinality), `forge_agent_runs_total` (by final
  status), `forge_agent_tool_calls_total` (by tool name and outcome),
  `forge_decisions_synthesized_total` (by outcome), and
  `forge_actions_total` (by action type and resulting status). These are
  incremented at the actual point of state change inside
  `agent_runtime.py`, `decisions.py`, and `actions.py` — not derived
  after the fact from logs.
- Existing structured logging (`structlog`, request-id correlation) from
  Phase 1 was left as-is; it already covers per-request logging
  correctly, and this phase's job was metrics, not replacing that.

### Evaluation
- **A real, runnable retrieval evaluation** (`scripts/evaluate_retrieval.py`):
  unlike the agent/decision layers, retrieval search is fully
  deterministic (Phase 4's hashed bag-of-words embedding), so this can
  actually execute without any credentials. `generate_synthetic_data.py`
  gives many at-risk customers *byte-identical* CRM note content (same
  product, same competitor template) — so "did retrieval find this exact
  customer's document" isn't a fair question for those customers, since
  any document in their group is an equally correct answer. This groups
  documents by (product, competitor), builds a differently-worded query
  per group, and measures whether the right group's document is retrieved.
- **A regression test embedding the same property**
  (`tests/test_retrieval_evaluation.py`): seeds three structurally
  identical-except-for-entities documents and asserts a paraphrased query
  ranks the correct one first — this runs in CI, unlike the standalone
  script, and would catch a future regression in retrieval quality that
  a "finds *a* relevant document" test (already in `test_retrieval_and_
  knowledge_graph.py`) would miss.
- **An agent evaluation harness** (`scripts/evaluate_agent.py`): a small
  golden question set with expected keywords and a minimum tool-call
  count per question. Implemented and ready to run, but — like
  `AnthropicProvider` and `AnthropicDecisionSynthesizer` in Phases 5 and
  6 — it drives a real model and requires `FORGE_ANTHROPIC_API_KEY`,
  which is not set in this environment. It has not been executed.

## What was actually tested, and how
104 tests in `apps/api/tests/` (up from 99 after Phase 7), all passing
against real SQLite through the actual FastAPI app — not mocks.

| Check | Test(s) | Result |
|---|---|---|
| `/metrics` serves Prometheus text format | `test_metrics_endpoint_exposes_prometheus_text_format` | pass |
| A real HTTP request increments the real counter | `test_http_requests_total_increments_on_real_traffic` | pass |
| Proposing a real action increments the real counter | `test_actions_total_increments_on_propose` | pass |
| Metric label names are correctly declared | `test_agent_runs_total_has_expected_label_names` | pass |
| A paraphrased query (not exact-text match) correctly ranks the right document first among structurally near-identical ones | `test_paraphrased_query_ranks_correct_document_first` | pass |

Beyond pytest, `scripts/evaluate_retrieval.py` was actually run against
real generated data, twice, at different scales — these are real,
reproducible numbers, not estimates:

| Dataset | Docs | Groups | Group top-1 accuracy | Mean top-k precision |
|---|---|---|---|---|
| 100 customers, seed 7 | 15 | 8 | **100%** (8/8) | 37.5% (top-5) |
| 300 customers, seed 42 | 45 | 12 | **100%** (12/12) | 80.6% (top-3) / 65.0% (top-5) |

**Reading these honestly**: top-1 accuracy of 100% means the hashed
bag-of-words embedding reliably ranks a document from the *correct*
(product, competitor) group first, even under a differently-worded query
— it is not doing literal string matching. Top-k precision is
mechanically lower for small groups (a group of 1 matching document
scored against `top_k=5` results in at most 20% precision *even with a
perfect ranking*, because 4 of the 5 returned slots are necessarily other
groups) — this is an artifact of how the metric is defined at these group
sizes, not evidence the embedding is imprecise. The 300-customer run's
higher top-3 precision than top-5 precision for the same reason confirms
this: smaller `k` naturally raises precision when true-positive counts
are small relative to `k`.

`ruff check`, `ruff format --check`, and `mypy app` are all clean.

## What was NOT tested (honest limitations)
- **The agent evaluation was not run.** `scripts/evaluate_agent.py`
  exists and is believed correct (it reuses the same `run_agent` and
  `AgentStep` querying pattern already tested in Phases 5–7), but it has
  never actually executed against a live model, because
  `FORGE_ANTHROPIC_API_KEY` is unset here. This is the same named gap as
  Phases 5 and 6, now extended to the evaluation layer: nothing about
  *agent answer quality* has been measured, only harness correctness.
- **No tracing.** There is no distributed tracing (OpenTelemetry spans
  across the agent → tool → DB call chain); the request-id correlation
  from Phase 1's logging is the only cross-cutting request identifier.
- **Metrics are in-process only** — `/metrics` exposes whatever this
  single process has counted since it started; there's no
  Prometheus server, remote-write, or Grafana dashboard actually running
  or configured to scrape it (consistent with Docker/Postgres being
  unavailable in this environment since Phase 1).
- **The retrieval evaluation measures one specific property** (group
  disambiguation under paraphrase) on one specific, template-generated
  dataset. It is not a general-purpose retrieval benchmark and its exact
  numbers are a property of `generate_synthetic_data.py`'s current
  templates (3 competitors × 4 products) — a different synthetic dataset
  shape would produce different numbers, though the same *mechanism*
  (small true-positive-count-per-`k` mechanically caps precision) would
  still apply.

## Gate status
Real, code-instrumented metrics exist and are tested end-to-end including
over real HTTP traffic. A genuine, non-circular retrieval-quality
evaluation was designed, executed against real generated data at two
scales, and its results are reported and explained rather than just
asserted — with a version of the same check embedded as a CI regression
test. The agent/decision evaluation layer is implemented but, like the
providers it evaluates, has not been run against a live model — that gap
is explicitly inherited from, not new to, this phase.
