# Phase 4 — Retrieval + Knowledge Graph

## Scope delivered
- **Chunking** (`app/services/chunking.py`): splits document content into
  word-boundary-safe chunks (default 800 characters, 100-character
  overlap) so a sentence spanning a chunk boundary still appears intact in
  at least one chunk. Pure function, no I/O.
- **Embeddings** (`app/services/embeddings.py`): a deterministic, hashed
  bag-of-words vectorizer (256 dimensions, L2-normalized) — not a learned
  semantic model. It has no vocabulary to download and needs no network
  access, and it correctly ranks "shares vocabulary with the query" higher
  than unrelated text, but it has no notion of synonymy (see the module
  docstring). `embed()` is the only integration point a real model (local
  sentence-transformer, or an API-based one) would replace.
- **Document ingestion now chunks and embeds** (`app/api/documents.py`):
  `POST /documents` chunks the submitted content and stores one
  `DocumentChunk` row per chunk (tenant-scoped, FK to the parent document)
  in the same transaction as the document itself.
- **Retrieval search** (`app/api/retrieval.py`): `POST /retrieval/search`
  takes a query string and an optional `customer_id` filter, embeds the
  query, scores it against the caller's own tenant's chunks by cosine
  similarity, and returns the top-k. Gated by `document.read` (the same
  permission that gates reading the underlying documents).
- **Knowledge graph** (`app/services/knowledge_graph.py`,
  `app/api/knowledge_graph.py`): `GET /knowledge-graph/{entity_type}/{id}`
  returns the entities connected to a given customer, subscription,
  product, transaction, support ticket, contract, invoice, or document, up
  to a requested depth (1–3). There is no separate graph store — nodes and
  edges are derived on demand from the same tenant-scoped relational
  tables the SQL tool queries, by walking the known foreign keys
  (`customer_id`, `product_id`). Gated by `data.query`.
- **Synthetic data generator updated**: the CRM note document it creates
  for at-risk customers is now chunked and embedded exactly the way the
  ingestion API does it, so generated data is actually searchable rather
  than only present in the `documents` table.

## What was actually tested, and how
53 tests in `apps/api/tests/` (up from 34 after Phase 3), all passing
against real SQLite through the actual FastAPI app — not mocks.

| Check | Test(s) | Result |
|---|---|---|
| Chunking never drops or duplicates content, respects size/overlap | `test_chunking.py` (6 tests) | pass |
| Embeddings are deterministic, unit-normalized, rank shared-vocabulary text higher | `test_embeddings.py` (6 tests) | pass |
| Search finds the relevant document over an unrelated one | `test_search_finds_relevant_chunk` | pass |
| Search results never cross tenants | `test_search_is_tenant_isolated` | pass |
| VIEWER can search (has `document.read`) but not query the knowledge graph (lacks `data.query`) | `test_viewer_can_search_but_not_query_knowledge_graph` | pass |
| Unknown entity type rejected (400) | `test_knowledge_graph_neighborhood_for_unknown_entity_type` | pass |
| Unknown/wrong-tenant entity id returns 404, not an empty graph | `test_knowledge_graph_neighborhood_not_found`, `test_knowledge_graph_is_tenant_isolated` | pass |
| Graph traversal returns the actual connected rows (subscription, ticket) with correct edges | `test_knowledge_graph_returns_connected_entities` | pass |

Beyond the pytest suite, the full path was exercised manually against
data produced by the (updated) synthetic generator: 60 customers were
generated (9 at-risk) against a real SQLite file, `/retrieval/search` for
"customer evaluating a competitor due to pricing concerns" correctly
surfaced the CRM notes for at-risk customers by relevance score, and
`/knowledge-graph/customers/{id}?depth=2` returned that customer's real
subscription, transactions, support tickets, contract, invoice, and
document — confirmed against the actual response, not asserted from
intent. `ruff check`, `ruff format --check`, and `mypy app` are all clean.

## What was NOT tested (honest limitations)
- **The embedding model is a hashed bag-of-words vectorizer, not a
  learned semantic model.** It ranks shared vocabulary well but has no
  notion of synonyms or paraphrase — "inexpensive" will not score highly
  against a query for "cheap" unless the underlying words overlap. This
  is a deliberate, documented placeholder (see the module docstring in
  `embeddings.py`); swapping in a real model is a single-function change.
- **Retrieval search is an unindexed, in-memory linear scan** over up to
  `MAX_CANDIDATE_CHUNKS` (5,000) chunks per tenant per query — there is no
  vector index (e.g. pgvector, FAISS). This is fine at the current
  synthetic-data scale but will not scale to a large document corpus
  without adding one.
- **Knowledge graph traversal at depth > 1 produces symmetric back-edges**
  (e.g. `customer -> subscription` and, one hop later,
  `subscription -> customer`) rather than deduplicating the underlying
  relationship into a single undirected edge. This makes the response
  noisier than necessary but does not lose or fabricate any relationship.
- **No live Postgres was used** — same limitation as Phases 2 and 3;
  Docker/Postgres remain unavailable in this development environment. The
  new `document_chunks` migration was applied and rolled back against a
  real SQLite file, chained correctly on top of the Phase 3 migration, but
  Postgres-specific behavior (e.g. its native JSON type vs. SQLite's) has
  not been verified.
- **No real vector database or graph database is used** — both features
  are built directly on the existing relational schema, which is a
  reasonable phase-4 scope but is not what a production deployment at
  scale would ultimately use.

## Gate status
Documents ingested through the API are chunked and embedded; a semantic
search endpoint returns tenant-scoped, ranked results over real generated
data; a knowledge-graph endpoint returns a correct, tenant-scoped
neighborhood of connected entities for any of the 8 enterprise entity
types. All listed limitations are scale/fidelity gaps in an otherwise
working, tested implementation, not unbuilt functionality.
