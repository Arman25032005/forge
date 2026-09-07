# Phase 3 — Enterprise Data

## Scope delivered
- **Enterprise schema** (`app/models/enterprise.py`): `Customer`, `Product`,
  `Subscription`, `Transaction`, `SupportTicket`, `Contract`, `Invoice`,
  `Employee`, `Document` — all tenant-scoped via a shared
  `TenantScopedMixin` (`id`, `organization_id`, `created_at`).
- **Migration**: Alembic autogenerate produced
  `alembic/versions/d00a00191413_add_enterprise_tables.py` for all 9 tables;
  applied and rolled back against a real SQLite file, chained correctly on
  top of the Phase 2 migration.
- **Synthetic dataset generator** (`scripts/generate_synthetic_data.py`):
  creates customers, products, subscriptions, transactions, support
  tickets, contracts, invoices, and documents for one organization. A
  configurable fraction of customers (default 15%) are seeded with a
  **deliberate churn pattern**: declining transaction volume over the most
  recent 3 months, an elevated rate of high/critical support tickets, a
  subscription downgrade, and a CRM note document mentioning a competitor —
  so that "why did revenue decline" has a real, discoverable answer in the
  data rather than a scripted one.
- **Document model + ingestion API** (`app/api/documents.py`): `POST
  /documents`, `GET /documents`, `GET /documents/{id}` — tenant-scoped,
  gated by `document.write`/`document.read` permissions. Chunking and
  embeddings are out of scope here and land in Phase 4.
- **SQL tool** (`app/services/sql_tool.py`): treats model/user-supplied SQL
  as untrusted input. Parses with `sqlglot`, rejects anything that isn't
  exactly one `SELECT` statement, rejects any table not on an explicit
  allowlist (`ALLOWED_TABLES` — deliberately excludes `users`,
  `organizations`, `audit_logs`), rewrites every table reference into a
  tenant-filtered subquery so the caller's own WHERE clause cannot override
  the tenant scope, caps result rows (`MAX_ROWS = 500`), and enforces a
  query timeout via `asyncio.wait_for`. Exposed at `POST /data/query`
  (gated by `data.query`) and `GET /data/catalog`.
- **Data catalog**: `GET /data/catalog` lists the tables the SQL tool will
  actually allow, so callers (human or agent) can discover the schema
  without guessing.

## A real bug found and fixed during this phase
While manually exercising the SQL tool against real (non-mocked) generated
data, the tenant filter matched **zero rows even for the correct tenant**.
Root cause: the filter embedded `str(organization_id)` (dashed UUID
format), but SQLAlchemy's `Uuid` column type stores UUIDs on SQLite as a
32-character hex string with no dashes — so the string comparison never
matched. Fixed by rendering the literal through the column's own
`bind_processor(dialect)` so the comparison always matches whatever the
active dialect actually stores (`_organization_id_literal` in
`sql_tool.py`). This is called out explicitly because it's exactly the
kind of silent-wrong-result bug that automated tests can miss if they only
check "no exception raised" — the query ran, returned successfully, and
returned nothing.

## What was actually tested, and how
34 tests in `apps/api/tests/` (up from 19 after Phase 2), all passing
against real SQLite (in-memory for the pytest suite, a real file for the
manual verification below) through the actual FastAPI app / SQL tool code
— not mocks.

| Check | Test(s) | Result |
|---|---|---|
| Query returns only the caller's tenant data | `test_query_returns_only_own_tenant_rows` | pass |
| Client-supplied `organization_id` in WHERE is overridden, not trusted | `test_client_supplied_org_filter_is_overridden_not_trusted` | pass |
| Multi-statement SQL injection (`; DROP TABLE ...`) rejected | `test_multi_statement_injection_rejected` | pass |
| DDL (`DROP TABLE`) rejected | `test_ddl_statement_rejected` | pass |
| Disallowed table (`users`) rejected | `test_disallowed_table_rejected` | pass |
| Audit log table not queryable via SQL tool | `test_audit_logs_not_queryable_via_sql_tool` | pass |
| UNION-based cross-table injection rejected | `test_union_based_cross_table_injection_rejected` | pass |
| Oversized `LIMIT` request capped, doesn't error | `test_row_limit_is_enforced` | pass |
| Malformed/unparseable SQL rejected | `test_malformed_sql_rejected` | pass |
| Document ingest/read roundtrip | `test_document_ingest_and_read_roundtrip` | pass |
| Documents are tenant-isolated (404, not leaked) | `test_documents_are_tenant_isolated` | pass |
| Oversized document content (>2MB) rejected (422) | `test_oversized_document_content_rejected` | pass |
| VIEWER role cannot write documents (403) | `test_viewer_cannot_write_documents` | pass |
| `/data/query` rejects disallowed table over HTTP | `test_data_query_endpoint_rejects_disallowed_table` | pass |
| `/data/catalog` lists only allowed tables | `test_data_catalog_lists_allowed_tables` | pass |

Additionally, the synthetic data generator was run end-to-end against a
real SQLite file (200 customers, 15% churn): it produced 1,200
transactions, 356 support tickets, and 30 CRM documents, and a raw SQL
check confirmed the churn pattern is real — at-risk customers' average
recent transaction amount ($3,232) is measurably lower than their older
average ($5,031), while active customers stayed flat (~$5,250 both
periods). This was verified with real aggregate queries against the
generated data, not asserted from the generator's intent.

`ruff check`, `ruff format --check`, and `mypy app` are all clean.

## What was NOT tested (honest limitations)
- **Not run against Postgres or at the 10,000+ customer scale** the spec
  ultimately calls for — verified at 200 customers on SQLite only (Docker
  is still unavailable in this environment, see Phase 1/2 reports). The
  generator batches commits every 50 customers and is parameterized
  (`--customers`), so scaling it up is expected to work, but that has not
  been executed or timed.
- **No connector abstraction / external API connector yet** — the spec
  calls for a pluggable connector layer (SQL, API, etc.); this phase only
  implements the SQL tool directly against the internal database. A
  connector abstraction is deferred rather than built as an unused stub.
- **Row-Level Security (RLS) at the database level is not used** — tenant
  isolation is enforced entirely in the application layer (the SQL tool's
  AST rewrite). This is a reasonable defense for the SQL tool's own
  entry point, but any *other* code path that queries these tables
  directly (e.g. a future service) must independently filter by
  `organization_id` — nothing at the database level currently prevents a
  buggy query elsewhere from crossing tenants. Worth revisiting (real
  Postgres RLS) before this handles production data.
- **No large-dataset / load test** was run against the SQL tool (e.g.
  behavior under thousands of concurrent queries, or a table with millions
  of rows) — only functional correctness was verified.

## Gate status
Per the phase plan: "All data tests must pass." Migrations, ingestion, SQL
validation/injection, tenant isolation, and malformed-data tests all pass
(14 tests specific to this phase, listed above). Large-dataset/load testing
and Postgres-specific verification are explicitly deferred and documented,
not silently skipped.
