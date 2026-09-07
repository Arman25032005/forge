from datetime import UTC

import pytest


async def _setup_tenant(client, slug, email):
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
async def test_audit_logs_are_scoped_to_caller_organization(client) -> None:
    token_a = await _setup_tenant(client, "tenant-a", "admin@tenant-a.com")
    token_b = await _setup_tenant(client, "tenant-b", "admin@tenant-b.com")

    # Generate an audit event unique to tenant A (its own registration/login).
    logs_a = await client.get("/audit/logs", headers={"Authorization": f"Bearer {token_a}"})
    logs_b = await client.get("/audit/logs", headers={"Authorization": f"Bearer {token_b}"})

    assert logs_a.status_code == 200
    assert logs_b.status_code == 200

    ids_a = {log["id"] for log in logs_a.json()}
    ids_b = {log["id"] for log in logs_b.json()}

    # No audit log record is visible to both tenants.
    assert ids_a.isdisjoint(ids_b)
    assert len(ids_a) > 0
    assert len(ids_b) > 0


@pytest.mark.asyncio
async def test_login_cannot_cross_tenant_boundary_with_correct_password(client) -> None:
    """A user registered under tenant A must not be able to authenticate by
    presenting tenant B's slug, even with the correct password."""
    await client.post("/auth/register-organization", json={"name": "A", "slug": "tenant-a"})
    await client.post("/auth/register-organization", json={"name": "B", "slug": "tenant-b"})
    await client.post(
        "/auth/register",
        json={
            "organization_slug": "tenant-a",
            "email": "shared@example.com",
            "password": "hunter22",
            "role": "ADMIN",
        },
    )

    resp = await client.post(
        "/auth/login",
        json={
            "organization_slug": "tenant-b",
            "email": "shared@example.com",
            "password": "hunter22",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_from_one_tenant_cannot_read_another_tenant_via_forged_org_id(client) -> None:
    """Even if an attacker forges a token's org_id claim to point at another
    tenant, the user row lookup (id + organization_id) must fail because the
    user does not belong to that organization, so the request is rejected
    rather than silently serving another tenant's data."""
    from datetime import datetime, timedelta

    import jwt as pyjwt

    from app.core.config import get_settings

    await client.post("/auth/register-organization", json={"name": "A", "slug": "tenant-a"})
    await client.post("/auth/register-organization", json={"name": "B", "slug": "tenant-b"})
    reg = await client.post(
        "/auth/register",
        json={
            "organization_slug": "tenant-a",
            "email": "victim@tenant-a.com",
            "password": "hunter22",
            "role": "ADMIN",
        },
    )
    user = reg.json()

    reg_b = await client.post(
        "/auth/register",
        json={
            "organization_slug": "tenant-b",
            "email": "someone@tenant-b.com",
            "password": "hunter22",
            "role": "ADMIN",
        },
    )
    other_org_id = reg_b.json()["organization_id"]

    settings = get_settings()
    forged_payload = {
        "sub": user["id"],  # real user id from tenant A
        "org_id": other_org_id,  # forged: claim to belong to tenant B
        "role": "ADMIN",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    forged_token = pyjwt.encode(
        forged_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert resp.status_code == 401
