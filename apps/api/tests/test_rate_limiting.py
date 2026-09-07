import pytest


@pytest.mark.asyncio
async def test_login_is_rate_limited_after_repeated_attempts(client) -> None:
    await client.post(
        "/auth/register-organization", json={"name": "rl-login-org", "slug": "rl-login-org"}
    )
    await client.post(
        "/auth/register",
        json={
            "organization_slug": "rl-login-org",
            "email": "victim@rl-login-org.com",
            "password": "hunter22",
            "role": "VIEWER",
        },
    )

    login_payload = {
        "organization_slug": "rl-login-org",
        "email": "victim@rl-login-org.com",
        "password": "wrong-password",
    }

    statuses = []
    for _ in range(7):
        resp = await client.post("/auth/login", json=login_payload)
        statuses.append(resp.status_code)

    assert statuses[:5] == [401] * 5
    assert 429 in statuses[5:]


@pytest.mark.asyncio
async def test_login_rate_limit_is_scoped_per_account(client) -> None:
    await client.post(
        "/auth/register-organization", json={"name": "rl-scope-org", "slug": "rl-scope-org"}
    )
    for email in ("a@rl-scope-org.com", "b@rl-scope-org.com"):
        await client.post(
            "/auth/register",
            json={
                "organization_slug": "rl-scope-org",
                "email": email,
                "password": "hunter22",
                "role": "VIEWER",
            },
        )

    # Exhaust account A's login attempts.
    for _ in range(5):
        await client.post(
            "/auth/login",
            json={
                "organization_slug": "rl-scope-org",
                "email": "a@rl-scope-org.com",
                "password": "wrong",
            },
        )
    blocked = await client.post(
        "/auth/login",
        json={"organization_slug": "rl-scope-org", "email": "a@rl-scope-org.com", "password": "x"},
    )
    assert blocked.status_code == 429

    # Account B is unaffected.
    resp_b = await client.post(
        "/auth/login",
        json={
            "organization_slug": "rl-scope-org",
            "email": "b@rl-scope-org.com",
            "password": "hunter22",
        },
    )
    assert resp_b.status_code == 200


@pytest.mark.asyncio
async def test_register_is_rate_limited_after_repeated_attempts(client) -> None:
    statuses = []
    for i in range(7):
        resp = await client.post(
            "/auth/register-organization",
            json={"name": f"rl-register-org-{i}", "slug": f"rl-register-org-{i}"},
        )
        assert resp.status_code == 201
        resp = await client.post(
            "/auth/register",
            json={
                "organization_slug": f"rl-register-org-{i}",
                "email": f"a@rl-register-org-{i}.com",
                "password": "hunter22",
                "role": "VIEWER",
            },
        )
        statuses.append(resp.status_code)

    assert statuses[:5] == [201] * 5
    assert 429 in statuses[5:]
