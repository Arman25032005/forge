import pytest


async def _setup_user(client, slug, email, role):
    await client.post("/auth/register-organization", json={"name": slug, "slug": slug})
    await client.post(
        "/auth/register",
        json={"organization_slug": slug, "email": email, "password": "hunter22", "role": role},
    )
    login = await client.post(
        "/auth/login", json={"organization_slug": slug, "email": email, "password": "hunter22"}
    )
    return login.json()["access_token"]


@pytest.mark.asyncio
async def test_agent_run_requires_configured_provider(client) -> None:
    token = await _setup_user(client, "agent-org", "admin@agent-org.com", "ADMIN")
    resp = await client.post(
        "/agents/runs",
        json={"question": "why did revenue decline?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503
    assert "FORGE_ANTHROPIC_API_KEY" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_operator_cannot_start_agent_run(client) -> None:
    token = await _setup_user(client, "agent-op-org", "op@agent-op-org.com", "OPERATOR")
    resp = await client.post(
        "/agents/runs",
        json={"question": "anything"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_runs_empty_for_new_org(client) -> None:
    token = await _setup_user(client, "agent-list-org", "a@agent-list-org.com", "ANALYST")
    resp = await client.get("/agents/runs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_unknown_run_returns_404(client) -> None:
    import uuid

    token = await _setup_user(client, "agent-404-org", "a@agent-404-org.com", "ANALYST")
    resp = await client.get(
        f"/agents/runs/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
