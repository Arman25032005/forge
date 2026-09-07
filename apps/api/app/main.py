import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", environment=settings.environment)
    yield
    logger.info("shutdown")


app = FastAPI(title="FORGE API", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(audit_router)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    response.headers["x-request-id"] = request_id
    logger.info(
        "request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    return response


@app.get("/")
async def root() -> dict:
    return {"service": "forge-api", "status": "running"}
