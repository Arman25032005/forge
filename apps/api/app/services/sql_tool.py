import asyncio
import uuid

import sqlglot
from sqlalchemy import text
from sqlalchemy.engine import Dialect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import exp

from app.models.enterprise import Customer

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


def _tenant_scoped_source(table_name: str, organization_id_literal: str) -> exp.Subquery:
    """Build `(SELECT * FROM <table> WHERE organization_id = '<id>') AS <table>`.

    Every reference to a tenant-scoped table is rewritten this way so the
    tenant filter is enforced by the tool itself, not by whatever WHERE
    clause the caller's SQL happens to contain.
    """
    filtered = (
        exp.select("*")
        .from_(exp.to_table(table_name))
        .where(exp.condition(f"organization_id = '{organization_id_literal}'"))
    )
    return exp.Subquery(this=filtered, alias=exp.TableAlias(this=exp.to_identifier(table_name)))


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
        table.replace(_tenant_scoped_source(table.name.lower(), org_literal))

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
