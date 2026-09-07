from datetime import UTC

import pytest


async def _register_org(client, slug="acme", name="Acme Inc"):
    resp = await client.post("/auth/register-organization", json={"name": name, "slug": slug})
    assert resp.status_code == 201
    return resp.json()


async def _register_user(
    client, slug="acme", email="alice@acme.com", password="hunter22", role="VIEWER"
):
    return await client.post(
        "/auth/register",
        json={"organization_slug": slug, "email": email, "password": password, "role": role},
    )


async def _login(client, slug="acme", email="alice@acme.com", password="hunter22"):
    return await client.post(
        "/auth/login", json={"organization_slug": slug, "email": email, "password": password}
    )


@pytest.mark.asyncio
async def test_register_and_login_success(client) -> None:
    await _register_org(client)
    await _register_user(client)

    resp = await _login(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client) -> None:
    await _register_org(client)
    await _register_user(client)

    resp = await _login(client, password="wrong-password")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_organization_rejected(client) -> None:
    resp = await _login(client, slug="does-not-exist")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_email_registration_rejected(client) -> None:
    await _register_org(client)
    await _register_user(client)

    resp = await _register_user(client)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_me_requires_valid_token(client) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_malformed_token(client) -> None:
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_expired_token(client, monkeypatch) -> None:
    import jwt as pyjwt

    from app.core.config import get_settings

    await _register_org(client)
    reg_resp = await _register_user(client)
    user = reg_resp.json()
    settings = get_settings()

    from datetime import datetime, timedelta

    expired_payload = {
        "sub": user["id"],
        "org_id": user["organization_id"],
        "role": user["role"],
        "iat": datetime.now(UTC) - timedelta(hours=2),
        "exp": datetime.now(UTC) - timedelta(hours=1),
    }
    expired_token = pyjwt.encode(
        expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client) -> None:
    await _register_org(client)
    await _register_user(client)
    login_resp = await _login(client)
    token = login_resp.json()["access_token"]

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@acme.com"
