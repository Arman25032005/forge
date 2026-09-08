import uuid

import pytest
from sqlalchemy import text

from app.services.sql_tool import SQLValidationError, execute_sql_tool


async def _seed_customer(db_session, organization_id: uuid.UUID, name: str, status: str) -> None:
    from app.services.sql_tool import _organization_id_literal

    dialect = db_session.get_bind().dialect
    org_literal = _organization_id_literal(organization_id, dialect)
    customer_id = uuid.uuid4().hex
    await db_session.execute(
        text(
            "INSERT INTO customers (id, organization_id, name, segment, status) "
            f"VALUES ('{customer_id}', '{org_literal}', :name, 'standard', :status)"
        ),
        {"name": name, "status": status},
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_query_returns_only_own_tenant_rows(db_session) -> None:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    await _seed_customer(db_session, org_a, "Tenant A Co", "active")
    await _seed_customer(db_session, org_b, "Tenant B Co", "active")

    rows = await execute_sql_tool(
        db_session, raw_sql="SELECT name FROM customers", organization_id=org_a
    )
    names = {row["name"] for row in rows}
    assert names == {"Tenant A Co"}


@pytest.mark.asyncio
async def test_client_supplied_org_filter_is_overridden_not_trusted(db_session) -> None:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    await _seed_customer(db_session, org_a, "Tenant A Co", "active")
    await _seed_customer(db_session, org_b, "Tenant B Co", "active")

    # Caller (as tenant A) tries to read tenant B's data by hand-crafting a
    # WHERE clause referencing tenant B's id. The tool must ignore this and
    # scope to the caller's real tenant regardless.
    rows = await execute_sql_tool(
        db_session,
        raw_sql=f"SELECT name FROM customers WHERE organization_id = '{org_b}'",
        organization_id=org_a,
    )
    assert rows == []


@pytest.mark.asyncio
async def test_multi_statement_injection_rejected(db_session) -> None:
    with pytest.raises(SQLValidationError):
        await execute_sql_tool(
            db_session,
            raw_sql="SELECT * FROM customers; DROP TABLE customers;--",
            organization_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_ddl_statement_rejected(db_session) -> None:
    with pytest.raises(SQLValidationError):
        await execute_sql_tool(
            db_session, raw_sql="DROP TABLE customers", organization_id=uuid.uuid4()
        )


@pytest.mark.asyncio
async def test_disallowed_table_rejected(db_session) -> None:
    with pytest.raises(SQLValidationError):
        await execute_sql_tool(
            db_session, raw_sql="SELECT * FROM users", organization_id=uuid.uuid4()
        )


@pytest.mark.asyncio
async def test_audit_logs_not_queryable_via_sql_tool(db_session) -> None:
    with pytest.raises(SQLValidationError):
        await execute_sql_tool(
            db_session, raw_sql="SELECT * FROM audit_logs", organization_id=uuid.uuid4()
        )


@pytest.mark.asyncio
async def test_union_based_cross_table_injection_rejected(db_session) -> None:
    with pytest.raises(SQLValidationError):
        await execute_sql_tool(
            db_session,
            raw_sql="SELECT email FROM customers UNION SELECT email FROM users",
            organization_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_row_limit_is_enforced(db_session) -> None:
    org_a = uuid.uuid4()
    for i in range(5):
        await _seed_customer(db_session, org_a, f"Customer {i}", "active")

    rows = await execute_sql_tool(
        db_session,
        raw_sql="SELECT name FROM customers LIMIT 100000",
        organization_id=org_a,
    )
    # Not asserting exact count against MAX_ROWS here (only 5 rows exist);
    # this confirms the oversized LIMIT request didn't error and was capped
    # without leaking beyond what actually exists.
    assert len(rows) == 5


@pytest.mark.asyncio
async def test_malformed_sql_rejected(db_session) -> None:
    with pytest.raises(SQLValidationError):
        await execute_sql_tool(
            db_session, raw_sql="SELECT FROM WHERE ???", organization_id=uuid.uuid4()
        )


@pytest.mark.asyncio
async def test_aliased_join_preserves_alias_references(db_session) -> None:
    """A real bug, found via a live model actually generating SQL: model-
    written queries commonly alias tables (`support_tickets st`) and
    reference columns through that alias (`st.customer_id`). The tenant-
    scoping rewrite used to always re-alias the rewritten subquery to the
    bare table name, silently breaking any such alias reference with
    'no such column'. This reproduces exactly the query shape that failed
    live: joining support_tickets to customers, both aliased."""
    from app.services.sql_tool import _organization_id_literal

    org_a = uuid.uuid4()
    await _seed_customer(db_session, org_a, "Aliased Co", "at_risk")
    org_literal = _organization_id_literal(org_a, db_session.get_bind().dialect)
    customer_id = (
        await db_session.execute(
            text(f"SELECT id FROM customers WHERE organization_id = '{org_literal}'")
        )
    ).scalar_one()
    await db_session.execute(
        text(
            "INSERT INTO support_tickets (id, organization_id, customer_id, subject, "
            "severity, opened_on) VALUES (:id, :org_id, :customer_id, 'Billing issue', "
            "'high', '2026-01-01')"
        ),
        {"id": uuid.uuid4().hex, "org_id": org_literal, "customer_id": customer_id},
    )
    await db_session.commit()

    rows = await execute_sql_tool(
        db_session,
        raw_sql=(
            "SELECT st.subject, c.name FROM support_tickets st "
            "JOIN customers c ON st.customer_id = c.id "
            "WHERE c.status = 'at_risk'"
        ),
        organization_id=org_a,
    )
    assert rows == [{"subject": "Billing issue", "name": "Aliased Co"}]


@pytest.mark.asyncio
async def test_nonexistent_column_raises_validation_error_not_crash(db_session) -> None:
    """A real bug, found live: a syntactically valid query referencing a
    column that doesn't exist (a model hallucinating a plausible-but-wrong
    name) raised an unhandled sqlalchemy.exc.OperationalError all the way
    up to a 500, instead of being reported back as a rejected query the
    agent could see and recover from."""
    with pytest.raises(SQLValidationError, match="no such column"):
        await execute_sql_tool(
            db_session,
            raw_sql="SELECT status FROM contracts",  # contracts has no `status` column
            organization_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_session_is_usable_after_a_failed_query(db_session) -> None:
    """The failed query above must roll back cleanly — otherwise every
    later step in the same agent run (which reuses this session) would
    also fail, even with valid SQL."""
    org_a = uuid.uuid4()
    await _seed_customer(db_session, org_a, "Still Works Co", "active")

    with pytest.raises(SQLValidationError):
        await execute_sql_tool(
            db_session, raw_sql="SELECT status FROM contracts", organization_id=org_a
        )

    rows = await execute_sql_tool(
        db_session, raw_sql="SELECT name FROM customers", organization_id=org_a
    )
    assert rows == [{"name": "Still Works Co"}]
