import asyncio
import uuid
from typing import Any

import sqlglot
from sqlalchemy import text
from sqlalchemy.engine import Dialect
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import exp

from app.models.enterprise import (
    Contract,
    Customer,
    Document,
    Employee,
    Invoice,
    Product,
    Subscription,
    SupportTicket,
    Transaction,
)

MAX_ROWS = 500
QUERY_TIMEOUT_SECONDS = 10

# Only tenant-scoped analytical tables are queryable through this tool.
# Identity/audit tables (users, organizations, audit_logs) are deliberately
# excluded — this tool is for business-data analysis, not for reading
# credentials or another subsystem's audit trail.
ALLOWED_TABLES = frozenset(
    {
        "customers",
        "products",
        "subscriptions",
        "transactions",
        "support_tickets",
        "contracts",
        "invoices",
        "employees",
        "documents",
    }
)

TABLE_MODELS: dict[str, type[Any]] = {
    "customers": Customer,
    "products": Product,
    "subscriptions": Subscription,
    "transactions": Transaction,
    "support_tickets": SupportTicket,
    "contracts": Contract,
    "invoices": Invoice,
    "employees": Employee,
    "documents": Document,
}


def _describe_table(table_name: str, model: type[Any]) -> str:
    columns = [c.name for c in model.__table__.columns if c.name != "organization_id"]
    return f"{table_name}({', '.join(columns)})"


# A caller (human or model) generating SQL against this tool needs to know
# the real column names — without this, a model will confidently guess
# plausible-but-wrong ones (found live: it guessed `invoices.paid` and
# `invoices.invoice_id` when the real columns are `status` and `id`).
SCHEMA_DESCRIPTION = "; ".join(
    _describe_table(name, model) for name, model in sorted(TABLE_MODELS.items())
)


class SQLValidationError(Exception):
    pass


def _organization_id_literal(organization_id: uuid.UUID, dialect: Dialect) -> str:
    """Render the UUID exactly as SQLAlchemy would store/compare it for this
    dialect (e.g. SQLite's `Uuid` type stores it as a 32-char hex string
    with no dashes, while Postgres uses its native UUID/dashed form) —
    comparing against `str(uuid)` unconditionally would silently match zero
    rows on backends that don't store the dashed form."""
    bind_processor = Customer.organization_id.type.bind_processor(dialect)
    value = bind_processor(organization_id) if bind_processor else str(organization_id)
    escaped = str(value).replace("'", "''")
    return escaped


def _tenant_scoped_source(
    table_name: str, alias: str, organization_id_literal: str
) -> exp.Subquery:
    """Build `(SELECT * FROM <table> WHERE organization_id = '<id>') AS <alias>`.

    Every reference to a tenant-scoped table is rewritten this way so the
    tenant filter is enforced by the tool itself, not by whatever WHERE
    clause the caller's SQL happens to contain. `alias` is the original
    query's own alias for this table if it gave one (e.g. `support_tickets
    st`), preserved so later references like `st.id` keep resolving —
    aliasing every rewritten subquery to the bare table name unconditionally
    would silently break any query using its own aliases, which is exactly
    what real model-generated SQL tends to do.
    """
    filtered = (
        exp.select("*")
        .from_(exp.to_table(table_name))
        .where(exp.condition(f"organization_id = '{organization_id_literal}'"))
    )
    return exp.Subquery(this=filtered, alias=exp.TableAlias(this=exp.to_identifier(alias)))


def validate_and_scope_query(raw_sql: str, organization_id: uuid.UUID, dialect: Dialect) -> str:
    """Validate untrusted, model-generated SQL and rewrite it to be safely
    tenant-scoped. Raises SQLValidationError for anything not a single,
    read-only SELECT against an allowed table."""
    try:
        statements = sqlglot.parse(raw_sql, read="sqlite")
    except sqlglot.errors.ParseError as exc:
        raise SQLValidationError(f"could not parse SQL: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SQLValidationError("exactly one SQL statement is allowed")

    stmt = statements[0]
    if not isinstance(stmt, exp.Select):
        raise SQLValidationError("only SELECT statements are allowed")

    tables = list(stmt.find_all(exp.Table))
    if not tables:
        raise SQLValidationError("query does not reference any table")

    org_literal = _organization_id_literal(organization_id, dialect)
    for table in tables:
        if table.name.lower() not in ALLOWED_TABLES:
            raise SQLValidationError(f"table not permitted: {table.name}")
        alias = table.alias_or_name
        table.replace(_tenant_scoped_source(table.name.lower(), alias, org_literal))

    existing_limit = stmt.args.get("limit")
    if existing_limit is None:
        stmt = stmt.limit(MAX_ROWS)
    else:
        try:
            requested = int(existing_limit.expression.this)
        except (AttributeError, ValueError, TypeError):
            requested = MAX_ROWS
        if requested > MAX_ROWS:
            stmt.set("limit", exp.Limit(expression=exp.Literal.number(MAX_ROWS)))

    return stmt.sql(dialect="sqlite")


async def execute_sql_tool(
    db: AsyncSession, *, raw_sql: str, organization_id: uuid.UUID
) -> list[dict]:
    dialect = db.get_bind().dialect
    safe_sql = validate_and_scope_query(raw_sql, organization_id, dialect)

    async def _run() -> list[dict]:
        result = await db.execute(text(safe_sql))
        return [dict(row._mapping) for row in result.fetchall()]

    try:
        return await asyncio.wait_for(_run(), timeout=QUERY_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        raise SQLValidationError("query exceeded timeout") from exc
    except DBAPIError as exc:
        # Syntactically valid, schema-invalid SQL (e.g. a nonexistent
        # column — found live, from a model guessing a plausible-but-wrong
        # name despite being given the real schema) reaches this far
        # before failing. Surface it the same way as any other rejected
        # query rather than letting a raw database error become an
        # unhandled 500 — this is also what lets the agent runtime see it
        # as a recoverable tool error and try a corrected query next.
        # Roll back first: this session is reused for later steps in the
        # same run, and SQLAlchemy refuses further use after a failed
        # flush/execute until the aborted transaction is rolled back.
        await db.rollback()
        raise SQLValidationError(f"query failed: {exc.orig}") from exc
