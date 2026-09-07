import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_refresh_token, hash_refresh_token
from app.models.refresh_token import RefreshToken


class RefreshTokenError(Exception):
    """Raised for any invalid, expired, or revoked refresh token — kept
    generic on purpose so callers don't leak which reason applied."""


async def issue_refresh_token(
    db: AsyncSession, *, user_id: uuid.UUID, organization_id: uuid.UUID, ttl_days: int
) -> str:
    raw_token = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user_id,
            organization_id=organization_id,
            token_hash=hash_refresh_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(days=ttl_days),
        )
    )
    await db.flush()
    return raw_token


def _as_aware_utc(value: datetime) -> datetime:
    # SQLite (unlike Postgres) doesn't round-trip timezone info through a
    # DateTime(timezone=True) column — values read back are naive, even
    # though they were written as UTC-aware. Comparing a naive value
    # against datetime.now(UTC) raises TypeError, so normalize first.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def _get_valid_token_row(db: AsyncSession, raw_token: str) -> RefreshToken:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise RefreshTokenError("invalid refresh token")
    if row.revoked_at is not None:
        raise RefreshTokenError("refresh token has been revoked")
    if _as_aware_utc(row.expires_at) <= datetime.now(UTC):
        raise RefreshTokenError("refresh token has expired")
    return row


async def rotate_refresh_token(
    db: AsyncSession, raw_token: str, *, ttl_days: int
) -> tuple[RefreshToken, str]:
    """Validate `raw_token`, revoke it, and issue a new one for the same
    user — rotation means a stolen-and-already-used refresh token cannot
    be replayed even once it's noticed, since it stops working the moment
    the legitimate client uses it. Returns the new row and its raw token
    (the raw value is never stored, so it can only be handed back here,
    at the moment it's generated)."""
    row = await _get_valid_token_row(db, raw_token)
    row.revoked_at = datetime.now(UTC)

    new_raw_token = await issue_refresh_token(
        db, user_id=row.user_id, organization_id=row.organization_id, ttl_days=ttl_days
    )
    await db.commit()

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(new_raw_token))
    )
    return result.scalar_one(), new_raw_token


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    row = await _get_valid_token_row(db, raw_token)
    row.revoked_at = datetime.now(UTC)
    await db.commit()
