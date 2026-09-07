import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app

# Every model must be imported so Base.metadata.create_all sees its table.
from app.models import AuditLog, Organization, User  # noqa: F401
from app.services.rate_limit import get_rate_limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # get_rate_limiter() is a process-wide lru_cache singleton so rate
    # limits are shared across requests within one running server — but
    # that means state would otherwise leak between tests too, since the
    # test suite runs in a single process. Reset it before every test.
    get_rate_limiter.cache_clear()
    yield
    get_rate_limiter.cache_clear()


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with session_factory() as session:
            yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def anyio_backend():
    return "asyncio"
