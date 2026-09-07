# ADR-001: Monorepo Architecture

## Status
Accepted

## Context
FORGE consists of a frontend, a backend API, and (in later phases) several
service-boundary modules — agent runtime, retrieval, ingestion, evaluation,
audit. These components evolve together during early development: a change
to the evidence schema affects the API, the agent runtime, and the frontend
investigation view in the same commit.

## Decision
Use a single monorepo (`apps/`, `services/`, `packages/`, `infra/`, `tests/`,
`docs/`) rather than separate repositories per component.

## Consequences
- Positive: atomic cross-cutting changes, shared CI, single source of truth
  for schemas (`packages/schemas`), simpler local development.
- Negative: coarser-grained git history, CI must scope jobs per path
  (`working-directory` in `.github/workflows/ci.yml`) to avoid rebuilding
  everything on every change.
- Revisit if a component needs an independent release cadence or a separate
  team boundary with different access control.
