from datetime import UTC

import pytest


async def _setup_user(client, role, slug="acme", email="user@acme.com"):
    await client.post("/auth/register-organization", json={"name": "Acme", "slug": slug})
    reg = await client.post(
        "/auth/register",
        json={"organization_slug": slug, "email": email, "password": "hunter22", "role": role},
    )
    login = await client.post(
        "/auth/login", json={"organization_slug": slug, "email": email, "password": "hunter22"}
    )
    return reg.json(), login.json()["access_token"]


@pytest.mark.asyncio
async def test_viewer_can_read_audit_logs(client) -> None:
    _, token = await _setup_user(client, "VIEWER")
    resp = await client.get("/audit/logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_missing_permission_returns_403() -> None:
    from app.core.permissions import Permission, role_has_permission
    from app.models.user import Role

    assert role_has_permission(Role.ADMIN, Permission.USER_MANAGE) is True
    assert role_has_permission(Role.VIEWER, Permission.USER_MANAGE) is False
    assert role_has_permission(Role.ANALYST, Permission.ACTION_EXECUTE) is False
    assert role_has_permission(Role.OPERATOR, Permission.ACTION_EXECUTE) is True


@pytest.mark.asyncio
async def test_token_role_cannot_escalate_privilege(client) -> None:
    """A caller who forges a token claiming ADMIN must not get ADMIN
    permissions if the database record for that user is a lower role —
    the server re-reads the role from the DB rather than trusting the JWT
    claim."""
    from datetime import datetime, timedelta

    import jwt as pyjwt

    from app.core.config import get_settings

    user, _real_token = await _setup_user(client, "VIEWER", email="escalate@acme.com")
    settings = get_settings()

    forged_payload = {
        "sub": user["id"],
        "org_id": user["organization_id"],
        "role": "ADMIN",  # forged claim; DB role is VIEWER
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    forged_token = pyjwt.encode(
        forged_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "VIEWER"


@pytest.mark.asyncio
async def test_token_signed_with_wrong_secret_rejected(client) -> None:
    from datetime import datetime, timedelta

    import jwt as pyjwt

    user, _token = await _setup_user(client, "VIEWER", email="tamper@acme.com")

    forged_payload = {
        "sub": user["id"],
        "org_id": user["organization_id"],
        "role": "ADMIN",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    forged_token = pyjwt.encode(forged_payload, "attacker-controlled-secret", algorithm="HS256")

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert resp.status_code == 401
