import pytest


async def _setup_admin(client, slug, email):
    await client.post("/auth/register-organization", json={"name": slug, "slug": slug})
    await client.post(
        "/auth/register",
        json={"organization_slug": slug, "email": email, "password": "hunter22", "role": "ADMIN"},
    )
    login = await client.post(
        "/auth/login", json={"organization_slug": slug, "email": email, "password": "hunter22"}
    )
    return login.json()["access_token"]


@pytest.mark.asyncio
async def test_document_ingest_and_read_roundtrip(client) -> None:
    token = await _setup_admin(client, "doc-org", "admin@doc-org.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/documents",
        json={"title": "Contract renewal notes", "content": "Customer plans to renew."},
        headers=headers,
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    resp = await client.get(f"/documents/{doc_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Contract renewal notes"


@pytest.mark.asyncio
async def test_documents_are_tenant_isolated(client) -> None:
    token_a = await _setup_admin(client, "doc-tenant-a", "admin@a.com")
    token_b = await _setup_admin(client, "doc-tenant-b", "admin@b.com")

    resp = await client.post(
        "/documents",
        json={"title": "Tenant A secret note", "content": "confidential"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc_id = resp.json()["id"]

    resp = await client.get(f"/documents/{doc_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_oversized_document_content_rejected(client) -> None:
    token = await _setup_admin(client, "oversize-org", "admin@oversize.com")
    resp = await client.post(
        "/documents",
        json={"title": "too big", "content": "x" * 2_000_001},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_viewer_cannot_write_documents(client) -> None:
    await client.post(
        "/auth/register-organization", json={"name": "viewer-org", "slug": "viewer-org"}
    )
    await client.post(
        "/auth/register",
        json={
            "organization_slug": "viewer-org",
            "email": "viewer@viewer-org.com",
            "password": "hunter22",
            "role": "VIEWER",
        },
    )
    login = await client.post(
        "/auth/login",
        json={
            "organization_slug": "viewer-org",
            "email": "viewer@viewer-org.com",
            "password": "hunter22",
        },
    )
    token = login.json()["access_token"]

    resp = await client.post(
        "/documents",
        json={"title": "x", "content": "y"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_data_query_endpoint_rejects_disallowed_table(client) -> None:
    token = await _setup_admin(client, "sql-org", "admin@sql-org.com")
    resp = await client.post(
        "/data/query",
        json={"sql": "SELECT * FROM users"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_data_catalog_lists_allowed_tables(client) -> None:
    token = await _setup_admin(client, "catalog-org", "admin@catalog-org.com")
    resp = await client.get("/data/catalog", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "customers" in resp.json()["tables"]
    assert "users" not in resp.json()["tables"]


@pytest.mark.asyncio
async def test_data_catalog_includes_real_column_names(client) -> None:
    # Regression test for a real bug found live: a model given only table
    # names (no columns) confidently guessed wrong column names
    # (`invoices.paid`, `invoices.invoice_id`) instead of the real ones.
    token = await _setup_admin(client, "catalog-schema-org", "admin@catalog-schema-org.com")
    resp = await client.get("/data/catalog", headers={"Authorization": f"Bearer {token}"})
    schema = resp.json()["schema"]
    assert "status" in schema["invoices"]
    assert "paid" not in schema["invoices"]
    assert "organization_id" not in schema["invoices"]
