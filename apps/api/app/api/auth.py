from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    OrganizationCreate,
    RefreshRequest,
    TokenResponse,
    UserOut,
    UserRegister,
)
from app.services.audit import record_event
from app.services.rate_limit import get_rate_limiter
from app.services.refresh_tokens import (
    RefreshTokenError,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _get_organization_by_slug(db: AsyncSession, slug: str) -> Organization | None:
    result = await db.execute(select(Organization).where(Organization.slug == slug))
    return result.scalar_one_or_none()


@router.post("/register-organization", status_code=status.HTTP_201_CREATED)
async def register_organization(
    payload: OrganizationCreate, db: AsyncSession = Depends(get_db)
) -> dict:
    existing = await _get_organization_by_slug(db, payload.slug)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="slug already exists")

    org = Organization(name=payload.name, slug=payload.slug)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return {"id": str(org.id), "name": org.name, "slug": org.slug}


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserRegister, request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    settings = get_settings()
    allowed = await get_rate_limiter().check(
        f"register:{_client_ip(request)}",
        max_requests=settings.register_rate_limit_max,
        window_seconds=settings.register_rate_limit_window_seconds,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="too many registration attempts"
        )

    org = await _get_organization_by_slug(db, payload.organization_slug)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="organization not found")

    existing = await db.execute(
        select(User).where(User.organization_id == org.id, User.email == payload.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")

    user = User(
        organization_id=org.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await record_event(
        db,
        organization_id=org.id,
        user_id=user.id,
        action="user.register",
        resource=f"user:{user.id}",
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    settings = get_settings()
    allowed = await get_rate_limiter().check(
        f"login:{payload.organization_slug}:{payload.email}",
        max_requests=settings.login_rate_limit_max,
        window_seconds=settings.login_rate_limit_window_seconds,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="too many login attempts"
        )

    org = await _get_organization_by_slug(db, payload.organization_slug)
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
    )
    if org is None:
        raise generic_error

    result = await db.execute(
        select(User).where(User.organization_id == org.id, User.email == payload.email)
    )
    user = result.scalar_one_or_none()
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.hashed_password)
    ):
        await record_event(
            db,
            organization_id=org.id,
            user_id=user.id if user else None,
            action="user.login",
            resource="auth",
            outcome="failure",
        )
        raise generic_error

    await record_event(
        db, organization_id=org.id, user_id=user.id, action="user.login", resource="auth"
    )
    token = create_access_token(user_id=user.id, organization_id=org.id, role=user.role)
    refresh_token = await issue_refresh_token(
        db, user_id=user.id, organization_id=org.id, ttl_days=settings.refresh_token_days
    )
    await db.commit()
    return TokenResponse(access_token=token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    settings = get_settings()
    try:
        row, new_raw_token = await rotate_refresh_token(
            db, payload.refresh_token, ttl_days=settings.refresh_token_days
        )
    except RefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        ) from exc

    result = await db.execute(select(User).where(User.id == row.user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        )

    access_token = create_access_token(
        user_id=user.id, organization_id=row.organization_id, role=user.role
    )
    return TokenResponse(access_token=access_token, refresh_token=new_raw_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)) -> None:
    try:
        await revoke_refresh_token(db, payload.refresh_token)
    except RefreshTokenError:
        # Logging out with an already-invalid token has no observable
        # difference from a successful logout — both leave the token
        # unusable — so this doesn't leak whether the token ever existed.
        pass


@router.get("/me", response_model=UserOut)
async def read_current_user(
    auth: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)
) -> User:
    result = await db.execute(
        select(User).where(User.id == auth.user_id, User.organization_id == auth.organization_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user
