# ADR-002: Database Selection

## Status
Accepted

## Context
FORGE needs: transactional storage for tenants/users/documents/audit records,
vector similarity search over document chunks, and a low-latency cache for
session/state data. Later phases add graph traversal (ADR-004).

## Decision
- **PostgreSQL** as the primary relational store for all tenant-scoped
  entities, using SQLAlchemy (async) + Alembic for schema migrations.
- **pgvector** (Postgres extension) for embedding storage and similarity
  search, introduced in Phase 4 — avoids running a separate vector database
  for the majority of retrieval needs while data volume is moderate.
- **Redis** for cache and ephemeral state (session tokens, rate limiting
  counters, short-lived task state).

## Consequences
- Positive: one relational engine to operate, back up, and secure with
  row-level tenant filtering; pgvector keeps evidence provenance joins
  (chunk → document → tenant) in the same transactional store as the data
  it describes, instead of a separate eventually-consistent index.
- Negative: pgvector's ANN performance is weaker than a dedicated vector
  database (e.g. Qdrant/Pinecone) at very large scale (100M+ vectors); if
  retrieval volume outgrows Postgres, we would introduce a dedicated vector
  store behind the same retrieval-service interface without changing
  callers.
- Redis is treated as a cache, not a system of record — nothing durable is
  stored only in Redis.
