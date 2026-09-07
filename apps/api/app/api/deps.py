import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import role_has_permission
from app.core.security import TokenError, decode_access_token
from app.db.session import get_db
from app.models.user import Role, User

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: Role


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        user_id = uuid.UUID(payload["sub"])
        organization_id = uuid.UUID(payload["org_id"])
        Role(payload["role"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="malformed token"
        ) from exc

    result = await db.execute(
        select(User).where(User.id == user_id, User.organization_id == organization_id)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found or inactive"
        )

    # Role is re-read from the database rather than trusted from the token,
    # so a role change/downgrade takes effect immediately without waiting
    # for token expiry.
    return AuthContext(user_id=user.id, organization_id=user.organization_id, role=user.role)


def require_permission(permission: str):
    async def _dependency(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not role_has_permission(auth.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"missing required permission: {permission}",
            )
        return auth

    return _dependency
