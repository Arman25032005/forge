import uuid

import pytest

from app.models.agent import AgentRun
from app.models.decision import Decision


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
async def test_decision_requires_completed_run(client, db_session) -> None:
    token, org_id = await _setup_admin(client, "decision-org", "a@decision-org.com")
    run = AgentRun(organization_id=org_id, user_id=uuid.uuid4(), question="q", status="running")
    db_session.add(run)
    await db_session.commit()

    resp = await client.post(
        f"/agents/runs/{run.id}/decision", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_decision_requires_configured_provider(client, db_session) -> None:
    token, org_id = await _setup_admin(client, "decision-cfg-org", "a@decision-cfg-org.com")
    run = AgentRun(
        organization_id=org_id,
        user_id=uuid.uuid4(),
        question="q",
        status="completed",
        final_answer="done",
    )
    db_session.add(run)
    await db_session.commit()

    resp = await client.post(
        f"/agents/runs/{run.id}/decision", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_decision_endpoint_404_for_unknown_run(client) -> None:
    token, _ = await _setup_admin(client, "decision-404-org", "a@decision-404-org.com")
    resp = await client.get(
        f"/agents/runs/{uuid.uuid4()}/decision", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_decision_is_tenant_isolated(client, db_session) -> None:
    token_a, org_a = await _setup_admin(client, "decision-tenant-a", "a@da.com")
    token_b, _ = await _setup_admin(client, "decision-tenant-b", "a@db.com")

    run = AgentRun(
        organization_id=org_a,
        user_id=uuid.uuid4(),
        question="q",
        status="completed",
        final_answer="done",
    )
    db_session.add(run)
    await db_session.commit()

    resp = await client.get(
        f"/agents/runs/{run.id}/decision", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404

    resp_owner = await client.get(
        f"/agents/runs/{run.id}/decision", headers={"Authorization": f"Bearer {token_a}"}
    )
    # the owner's run exists, but no decision has been synthesized for it yet
    assert resp_owner.status_code == 404


@pytest.mark.asyncio
async def test_list_decisions_is_tenant_scoped(client, db_session) -> None:
    token_a, org_a = await _setup_admin(client, "decision-list-a", "a@dla.com")
    token_b, org_b = await _setup_admin(client, "decision-list-b", "a@dlb.com")

    for org_id in (org_a, org_b):
        run = AgentRun(
            organization_id=org_id, user_id=uuid.uuid4(), question="q", status="completed"
        )
        db_session.add(run)
        await db_session.flush()
        db_session.add(
            Decision(
                organization_id=org_id,
                run_id=run.id,
                conclusion="x",
                confidence=0.5,
                evidence=[],
                recommended_actions=[],
            )
        )
    await db_session.commit()

    resp_a = await client.get("/decisions", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200
    assert len(resp_a.json()) == 1

    resp_b = await client.get("/decisions", headers={"Authorization": f"Bearer {token_b}"})
    assert len(resp_b.json()) == 1
    assert resp_a.json()[0]["id"] != resp_b.json()[0]["id"]
