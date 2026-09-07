# Phase 1 — Foundation

## Scope delivered
- Monorepo layout: `apps/api` (FastAPI), `apps/web` (Next.js), plus placeholder
  directories for `services/`, `packages/`, `infra/`, `tests/`, `docs/` that
  later phases populate.
- Backend: FastAPI app with structured (JSON) logging via `structlog`,
  request-ID + latency middleware, Pydantic settings loaded from environment
  (`FORGE_` prefix), async SQLAlchemy engine/session factory, Alembic wired
  for async migrations, `/healthz` (liveness) and `/readyz` (dependency
  readiness: Postgres + Redis) endpoints.
- Frontend: Next.js 16 (App Router) + TypeScript + Tailwind CSS, minimal
  landing page, ESLint configured.
- Docker Compose (`infra/docker/docker-compose.yml`) defining Postgres, Redis,
  API, and web services with health checks and startup ordering.
- CI (`.github/workflows/ci.yml`): separate `api` and `web` jobs running lint,
  format check, type check (mypy), and tests on push/PR.
- ADR-001 (monorepo) and ADR-002 (database selection).

## What was actually tested, and how
| Check | Command | Result |
|---|---|---|
| API unit tests | `pytest -q` (apps/api) | 4 passed |
| API lint | `ruff check .` | clean |
| API format | `ruff format .` | clean |
| API types | `mypy app` | no issues, 6 source files |
| Web lint | `npm run lint` | clean |
| Web build | `npm run build` | succeeds, static pages generated |

## What was NOT tested (honest limitations)
- **Docker/Docker Compose startup was not verified.** The Docker CLI is not
  installed in this development environment (`docker: command not found`).
  The Compose file and Dockerfiles are written but unexecuted — they should
  be validated (`docker compose up`, then hitting `/readyz`) before relying
  on them, e.g. in CI or by a developer with Docker installed.
- **Live Postgres/Redis connectivity was not verified.** `/readyz` was
  exercised via the FastAPI test client with no Postgres/Redis running, so it
  correctly reports `checks.database`/`checks.redis` as errors rather than
  crashing — but the "successful connection" path is untested locally.
- **CI has not run on GitHub** — the workflow YAML is written and the jobs
  mirror the locally-run commands above, but has not been observed executing
  in GitHub Actions itself.
- No migrations exist yet (no models beyond `Base` are defined), so
  `alembic upgrade head` has nothing to apply and was not exercised.

## Gate status
Local application code (API + web) builds, lints, type-checks, and its unit
tests pass. Docker-based infrastructure startup is implemented but unverified
in this environment — flag this before treating Phase 1's infra as proven.
