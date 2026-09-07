import datetime
import uuid

import pytest

from app.models.enterprise import Customer, Subscription, SupportTicket


async def _setup_admin(client, slug, email):
    org_resp = await client.post("/auth/register-organization", json={"name": slug, "slug": slug})
    await client.post(
        "/auth/register",
        json={"organization_slug": slug, "email": email, "password": "hunter22", "role": "ADMIN"},
    )
    login = await client.post(
        "/auth/login", json={"organization_slug": slug, "email": email, "password": "hunter22"}
    )
    return login.json()["access_token"], uuid.UUID(org_resp.json()["id"])


@pytest.mark.asyncio
async def test_search_finds_relevant_chunk(client) -> None:
    token, _ = await _setup_admin(client, "retrieval-org", "admin@retrieval-org.com")
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/documents",
        json={
            "title": "Support call notes",
            "content": "The customer mentioned they are evaluating a competitor product "
            "due to pricing concerns and a recent outage.",
        },
        headers=headers,
    )
    await client.post(
        "/documents",
        json={
            "title": "Unrelated memo",
            "content": "The office kitchen will be closed for renovation next week.",
        },
        headers=headers,
    )

    resp = await client.post(
        "/retrieval/search",
        json={"query": "competitor pricing concerns", "top_k": 3},
        headers=headers,
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) > 0
    assert results[0]["document_title"] == "Support call notes"


@pytest.mark.asyncio
async def test_search_is_tenant_isolated(client) -> None:
    token_a, _ = await _setup_admin(client, "retrieval-tenant-a", "admin@ra.com")
    token_b, _ = await _setup_admin(client, "retrieval-tenant-b", "admin@rb.com")

    await client.post(
        "/documents",
        json={"title": "Tenant A secret", "content": "confidential churn risk analysis"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    resp = await client.post(
        "/retrieval/search",
        json={"query": "confidential churn risk analysis", "top_k": 5},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.asyncio
async def test_viewer_can_search_but_not_query_knowledge_graph(client) -> None:
    await client.post(
        "/auth/register-organization", json={"name": "kg-viewer-org", "slug": "kg-viewer-org"}
    )
    await client.post(
        "/auth/register",
        json={
            "organization_slug": "kg-viewer-org",
            "email": "viewer@kg-viewer-org.com",
            "password": "hunter22",
            "role": "VIEWER",
        },
    )
    login = await client.post(
        "/auth/login",
        json={
            "organization_slug": "kg-viewer-org",
            "email": "viewer@kg-viewer-org.com",
            "password": "hunter22",
        },
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    search_resp = await client.post(
        "/retrieval/search", json={"query": "anything", "top_k": 1}, headers=headers
    )
    assert search_resp.status_code == 200

    graph_resp = await client.get(f"/knowledge-graph/customers/{uuid.uuid4()}", headers=headers)
    assert graph_resp.status_code == 403


@pytest.mark.asyncio
async def test_knowledge_graph_neighborhood_for_unknown_entity_type(client) -> None:
    token, _ = await _setup_admin(client, "kg-bad-type-org", "admin@kg-bad-type-org.com")
    resp = await client.get(
        f"/knowledge-graph/not-a-real-type/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_knowledge_graph_neighborhood_not_found(client) -> None:
    token, _ = await _setup_admin(client, "kg-missing-org", "admin@kg-missing-org.com")
    resp = await client.get(
        f"/knowledge-graph/customers/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_knowledge_graph_returns_connected_entities(client, db_session) -> None:
    token, org_id = await _setup_admin(client, "kg-org", "admin@kg-org.com")
    headers = {"Authorization": f"Bearer {token}"}

    customer = Customer(organization_id=org_id, name="Acme Corp", segment="enterprise")
    db_session.add(customer)
    await db_session.flush()

    subscription = Subscription(
        organization_id=org_id,
        customer_id=customer.id,
        product_id=uuid.uuid4(),
        started_at=datetime.date(2025, 1, 1),
    )
    ticket = SupportTicket(
        organization_id=org_id,
        customer_id=customer.id,
        subject="Billing dispute",
        severity="high",
        opened_on=datetime.date(2025, 6, 1),
    )
    db_session.add_all([subscription, ticket])
    await db_session.commit()

    resp = await client.get(f"/knowledge-graph/customers/{customer.id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()

    node_keys = {(n["type"], n["id"]) for n in body["nodes"]}
    assert ("customers", str(customer.id)) in node_keys
    assert ("subscriptions", str(subscription.id)) in node_keys
    assert ("support_tickets", str(ticket.id)) in node_keys
    assert len(body["edges"]) == 2


@pytest.mark.asyncio
async def test_knowledge_graph_is_tenant_isolated(client, db_session) -> None:
    _, org_a = await _setup_admin(client, "kg-tenant-a", "admin@kga.com")
    token_b, _ = await _setup_admin(client, "kg-tenant-b", "admin@kgb.com")

    customer = Customer(organization_id=org_a, name="Tenant A Customer")
    db_session.add(customer)
    await db_session.commit()

    resp = await client.get(
        f"/knowledge-graph/customers/{customer.id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
