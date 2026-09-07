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
async def test_analyst_can_propose_but_not_approve(client) -> None:
    token = await _setup_user(client, "actions-analyst-org", "a@actions-analyst.com", "ANALYST")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/actions",
        json={"action_type": "manual_task", "description": "follow up", "parameters": {}},
        headers=headers,
    )
    assert resp.status_code == 201
    action_id = resp.json()["id"]

    approve_resp = await client.post(f"/actions/{action_id}/approve", headers=headers)
    assert approve_resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_propose_actions(client) -> None:
    token = await _setup_user(client, "actions-viewer-org", "v@actions-viewer.com", "VIEWER")
    resp = await client.post(
        "/actions",
        json={"action_type": "manual_task", "description": "x", "parameters": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unknown_action_type_rejected(client) -> None:
    token = await _setup_user(client, "actions-badtype-org", "a@actions-badtype.com", "OPERATOR")
    resp = await client.post(
        "/actions",
        json={"action_type": "delete_everything", "description": "x", "parameters": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_operator_can_propose_approve_and_execute_a_different_users_action(client) -> None:
    slug = "actions-op-org"
    await client.post("/auth/register-organization", json={"name": slug, "slug": slug})
    await client.post(
        "/auth/register",
        json={
            "organization_slug": slug,
            "email": "proposer@op.com",
            "password": "hunter22",
            "role": "ANALYST",
        },
    )
    await client.post(
        "/auth/register",
        json={
            "organization_slug": slug,
            "email": "approver@op.com",
            "password": "hunter22",
            "role": "OPERATOR",
        },
    )
    proposer_login = await client.post(
        "/auth/login",
        json={"organization_slug": slug, "email": "proposer@op.com", "password": "hunter22"},
    )
    approver_login = await client.post(
        "/auth/login",
        json={"organization_slug": slug, "email": "approver@op.com", "password": "hunter22"},
    )
    proposer_headers = {"Authorization": f"Bearer {proposer_login.json()['access_token']}"}
    approver_headers = {"Authorization": f"Bearer {approver_login.json()['access_token']}"}

    resp = await client.post(
        "/actions",
        json={"action_type": "manual_task", "description": "call the customer", "parameters": {}},
        headers=proposer_headers,
    )
    action_id = resp.json()["id"]

    approve_resp = await client.post(f"/actions/{action_id}/approve", headers=approver_headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    execute_resp = await client.post(f"/actions/{action_id}/execute", headers=approver_headers)
    assert execute_resp.status_code == 200
    assert execute_resp.json()["status"] == "executed"


@pytest.mark.asyncio
async def test_actions_are_tenant_isolated(client) -> None:
    token_a = await _setup_user(client, "actions-tenant-a", "a@ata.com", "OPERATOR")
    token_b = await _setup_user(client, "actions-tenant-b", "a@atb.com", "OPERATOR")

    resp = await client.post(
        "/actions",
        json={"action_type": "manual_task", "description": "x", "parameters": {}},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    action_id = resp.json()["id"]

    resp_b = await client.get(
        f"/actions/{action_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp_b.status_code == 404
