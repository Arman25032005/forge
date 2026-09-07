import uuid

import pytest

from app.models.decision import Decision


async def _setup_operator(client, slug, email):
    org_resp = await client.post("/auth/register-organization", json={"name": slug, "slug": slug})
    await client.post(
        "/auth/register",
        json={
            "organization_slug": slug,
            "email": email,
            "password": "hunter22",
            "role": "OPERATOR",
        },
    )
    login = await client.post(
        "/auth/login", json={"organization_slug": slug, "email": email, "password": "hunter22"}
    )
    return login.json()["access_token"], uuid.UUID(org_resp.json()["id"])


@pytest.mark.asyncio
async def test_action_cannot_reference_another_tenants_decision(client, db_session) -> None:
    token_a, org_a = await _setup_operator(client, "xref-tenant-a", "a@xrefa.com")
    _, org_b = await _setup_operator(client, "xref-tenant-b", "a@xrefb.com")

    other_tenants_decision = Decision(
        organization_id=org_b,
        run_id=uuid.uuid4(),
        conclusion="belongs to tenant B",
        confidence=0.9,
        evidence=[],
        recommended_actions=[],
    )
    db_session.add(other_tenants_decision)
    await db_session.commit()

    resp = await client.post(
        "/actions",
        json={
            "action_type": "manual_task",
            "description": "x",
            "parameters": {},
            "decision_id": str(other_tenants_decision.id),
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_action_can_reference_own_tenants_decision(client, db_session) -> None:
    token_a, org_a = await _setup_operator(client, "xref-own-org", "a@xrefown.com")

    own_decision = Decision(
        organization_id=org_a,
        run_id=uuid.uuid4(),
        conclusion="belongs to this tenant",
        confidence=0.9,
        evidence=[],
        recommended_actions=[],
    )
    db_session.add(own_decision)
    await db_session.commit()

    resp = await client.post(
        "/actions",
        json={
            "action_type": "manual_task",
            "description": "x",
            "parameters": {},
            "decision_id": str(own_decision.id),
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 201
    assert resp.json()["decision_id"] == str(own_decision.id)
