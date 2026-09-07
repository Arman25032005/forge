# FORGE — Enterprise AI Deployment & Decision Platform

FORGE connects organizational data sources and lets controlled AI agents
investigate business questions, reason over structured and unstructured
data, produce evidence-backed conclusions, recommend actions, obtain human
approval, and execute authorized actions.

This repository is being built incrementally across 10 phases (see
`docs/architecture/`). **Phases 1–9 (Foundation, Identity + Security,
Enterprise Data, Retrieval + Knowledge Graph, Agent Runtime, Decision
Intelligence, Actions + Approval, Observability + Evaluation, Red-Team
Hardening) are complete**; only deployment has not been implemented yet.
Note: Phases 5 and 6's real Claude-backed providers (and Phase 8's agent
evaluation and Phase 9's prompt-injection hardening, both of which depend
on them) have not been exercised against a live model — see
`docs/architecture/phase-5-agent-runtime.md`,
`docs/architecture/phase-6-decision-intelligence.md`,
`docs/architecture/phase-8-observability-evaluation.md`, and
`docs/architecture/phase-9-red-team-hardening.md`.

## Repository layout
```
apps/web/        Next.js + TypeScript + Tailwind frontend
apps/api/        FastAPI backend
services/        Service-boundary modules (populated in later phases)
packages/        Shared schemas/config/observability/security libraries
infra/           Docker Compose, Kubernetes, Terraform
data/            Synthetic data and evaluation datasets
tests/           Cross-cutting test suites (unit/integration/e2e/security/...)
docs/            Architecture, ADRs, security, deployment, evaluation docs
```

## Local development

### Backend (`apps/api`)
```bash
cd apps/api
python3 -m venv ../../.venv && source ../../.venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```
- `GET /healthz` — liveness
- `GET /readyz` — readiness (checks Postgres + Redis connectivity)

Run tests: `pytest -q`
Lint/format/type-check: `ruff check .`, `ruff format .`, `mypy app`

Apply migrations: `alembic upgrade head`

Generate synthetic enterprise data for a demo organization:
```bash
python scripts/generate_synthetic_data.py --org-slug acme --customers 200
```
This seeds customers/products/subscriptions/transactions/support
tickets/contracts/invoices/documents (chunked and embedded, so they're
searchable via `/retrieval/search`), with a configurable fraction of
customers given a deliberate revenue-decline pattern (see
`docs/architecture/phase-3-enterprise-data.md` and
`docs/architecture/phase-4-retrieval-knowledge-graph.md`).

Run an investigation agent (requires `FORGE_ANTHROPIC_API_KEY`; without it
`POST /agents/runs` returns 503):
```bash
curl -X POST localhost:8000/agents/runs -H "Authorization: Bearer $TOKEN" \
  -d '{"question": "Why did revenue decline this quarter?"}'
```
The agent can call three tools — SQL query, document search, and
knowledge-graph lookup — over the tenant's own data; see
`docs/architecture/phase-5-agent-runtime.md`.

Once a run's `status` is `completed`, turn its trace into a structured,
evidence-backed conclusion:
```bash
curl -X POST localhost:8000/agents/runs/$RUN_ID/decision -H "Authorization: Bearer $TOKEN"
```
This returns a conclusion, a confidence score, evidence citations back
into the run's own steps (a citation to a step that doesn't exist in the
run is rejected, not trusted), and recommended actions; see
`docs/architecture/phase-6-decision-intelligence.md`.

Propose and approve an action (maker-checker: the proposer cannot approve
their own proposal):
```bash
curl -X POST localhost:8000/actions -H "Authorization: Bearer $PROPOSER_TOKEN" \
  -d '{"action_type": "flag_customer_at_risk", "description": "...", "parameters": {"customer_id": "..."}}'
curl -X POST localhost:8000/actions/$ACTION_ID/approve -H "Authorization: Bearer $APPROVER_TOKEN"
curl -X POST localhost:8000/actions/$ACTION_ID/execute -H "Authorization: Bearer $APPROVER_TOKEN"
```
Only two action types have a real side effect against this app's own
data (`flag_customer_at_risk`, `create_support_ticket`) — there's no
external CRM/email integration to execute against; see
`docs/architecture/phase-7-actions-approval.md`.

Prometheus metrics are exposed at `GET /metrics`. Evaluate retrieval
quality against real generated data (no API key needed — this is fully
deterministic):
```bash
python scripts/evaluate_retrieval.py --org-slug acme
```
`scripts/evaluate_agent.py` evaluates agent answer quality the same way
but requires `FORGE_ANTHROPIC_API_KEY` and has not been run in this
environment; see `docs/architecture/phase-8-observability-evaluation.md`
for real, measured retrieval-quality numbers.

Auth now issues a refresh token alongside the access token, with
rotation on every use and revocation on logout:
```bash
curl -X POST localhost:8000/auth/refresh -d '{"refresh_token": "..."}'
curl -X POST localhost:8000/auth/logout -d '{"refresh_token": "..."}'
```
`/auth/login` and `/auth/register` are rate-limited (429 after repeated
attempts); see `docs/architecture/phase-9-red-team-hardening.md` for the
two real bugs found and fixed while building this phase.

### Frontend (`apps/web`)
```bash
cd apps/web
npm install
npm run dev
```
Lint/build: `npm run lint`, `npm run build`

### Infrastructure
```bash
cp .env.example .env
docker compose -f infra/docker/docker-compose.yml up --build
```
**Note:** this Compose stack has not been executed in this development
environment (no local Docker installation) — see
`docs/architecture/phase-1-foundation.md` for exactly what has and hasn't
been verified.

## Configuration
Backend settings are environment variables prefixed `FORGE_` (see
`.env.example` and `apps/api/app/core/config.py`).

## Status and honesty policy
This project reports only what has actually been implemented and tested.
Each phase's doc under `docs/architecture/` states explicitly what was
verified, how, and what remains unverified — no fabricated metrics, test
results, or "done" claims for untested functionality.
