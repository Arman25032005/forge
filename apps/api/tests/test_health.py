import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_root() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "forge-api"


@pytest.mark.asyncio
async def test_liveness() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_reports_dependency_status() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "database" in body["checks"]
    assert "redis" in body["checks"]


@pytest.mark.asyncio
async def test_request_id_header_present() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert "x-request-id" in response.headers
