import pytest

from app.core.metrics import actions_total, agent_runs_total, http_requests_total


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_prometheus_text_format(client) -> None:
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "forge_http_requests_total" in resp.text


@pytest.mark.asyncio
async def test_http_requests_total_increments_on_real_traffic(client) -> None:
    before = http_requests_total.labels(
        method="GET", path="/healthz", status_code="200"
    )._value.get()

    resp = await client.get("/healthz")
    assert resp.status_code == 200

    after = http_requests_total.labels(
        method="GET", path="/healthz", status_code="200"
    )._value.get()
    assert after == before + 1


@pytest.mark.asyncio
async def test_actions_total_increments_on_propose(client) -> None:
    await client.post(
        "/auth/register-organization",
        json={"name": "metrics-actions-org", "slug": "metrics-actions-org"},
    )
    await client.post(
        "/auth/register",
        json={
            "organization_slug": "metrics-actions-org",
            "email": "a@metrics-actions-org.com",
            "password": "hunter22",
            "role": "OPERATOR",
        },
    )
    login = await client.post(
        "/auth/login",
        json={
            "organization_slug": "metrics-actions-org",
            "email": "a@metrics-actions-org.com",
            "password": "hunter22",
        },
    )
    token = login.json()["access_token"]

    before = actions_total.labels(action_type="manual_task", status="proposed")._value.get()

    resp = await client.post(
        "/actions",
        json={"action_type": "manual_task", "description": "x", "parameters": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201

    after = actions_total.labels(action_type="manual_task", status="proposed")._value.get()
    assert after == before + 1


def test_agent_runs_total_has_expected_label_names() -> None:
    # Registering a labelled child validates the metric's declared label
    # names without needing a full agent run.
    agent_runs_total.labels(status="completed")
