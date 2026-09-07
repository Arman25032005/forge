import datetime

import pytest
from sqlalchemy import select

from app.models.refresh_token import RefreshToken


async def _register_and_login(client, slug, email):
    await client.post("/auth/register-organization", json={"name": slug, "slug": slug})
    await client.post(
        "/auth/register",
        json={"organization_slug": slug, "email": email, "password": "hunter22", "role": "ADMIN"},
    )
    return await client.post(
        "/auth/login", json={"organization_slug": slug, "email": email, "password": "hunter22"}
    )


@pytest.mark.asyncio
async def test_login_returns_a_refresh_token(client) -> None:
    resp = await _register_and_login(client, "refresh-org", "a@refresh-org.com")
    assert resp.status_code == 200
    body = resp.json()
    assert "refresh_token" in body
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_issues_a_new_access_token(client) -> None:
    login = await _register_and_login(client, "refresh-issue-org", "a@refresh-issue-org.com")
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"] != refresh_token  # rotated


@pytest.mark.asyncio
async def test_reusing_a_rotated_refresh_token_fails(client) -> None:
    login = await _register_and_login(client, "refresh-reuse-org", "a@refresh-reuse-org.com")
    refresh_token = login.json()["refresh_token"]

    first = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert first.status_code == 200

    replay = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert replay.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_the_refresh_token(client) -> None:
    login = await _register_and_login(client, "logout-org", "a@logout-org.com")
    refresh_token = login.json()["refresh_token"]

    logout_resp = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 204

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_with_unknown_token_still_returns_204(client) -> None:
    resp = await client.post("/auth/logout", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_expired_refresh_token_is_rejected(client, db_session) -> None:
    login = await _register_and_login(client, "expired-org", "a@expired-org.com")
    refresh_token = login.json()["refresh_token"]

    from app.core.security import hash_refresh_token

    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
    )
    row = result.scalar_one()
    row.expires_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)
    await db_session.commit()

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_garbage_token_is_rejected(client) -> None:
    resp = await client.post("/auth/refresh", json={"refresh_token": "garbage"})
    assert resp.status_code == 401
