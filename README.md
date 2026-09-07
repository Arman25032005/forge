# FORGE — Enterprise AI Deployment & Decision Platform

FORGE connects organizational data sources and lets controlled AI agents
investigate business questions, reason over structured and unstructured
data, produce evidence-backed conclusions, recommend actions, obtain human
approval, and execute authorized actions.

This repository is being built incrementally across 10 phases (see
`docs/architecture/`). **Phase 1 (Foundation) is complete**; later phases
(identity/security, enterprise data, retrieval + knowledge graph, agent
runtime, decision intelligence, actions + approval, observability +
evaluation, red-team hardening, deployment) have not been implemented yet.

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
