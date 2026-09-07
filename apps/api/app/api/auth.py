from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    OrganizationCreate,
    TokenResponse,
    UserOut,
    UserRegister,
)
from app.services.audit import record_event

router = APIRouter(prefix="/auth", tags=["auth"])


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
async def register_user(payload: UserRegister, db: AsyncSession = Depends(get_db)) -> User:
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
    return TokenResponse(access_token=token)


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
