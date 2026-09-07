import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.api.actions import router as actions_router
from app.api.agents import router as agents_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.data import router as data_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.knowledge_graph import router as knowledge_graph_router
from app.api.retrieval import router as retrieval_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.metrics import http_request_duration_seconds, http_requests_total, render_metrics

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
app.include_router(data_router)
app.include_router(documents_router)
app.include_router(retrieval_router)
app.include_router(knowledge_graph_router)
app.include_router(agents_router)
app.include_router(actions_router)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    start = time.monotonic()
    response = await call_next(request)
    duration_seconds = time.monotonic() - start
    response.headers["x-request-id"] = request_id

    # Use the matched route's path template (e.g. "/agents/runs/{run_id}"),
    # not the raw URL, so per-request UUIDs don't blow up label cardinality.
    route = request.scope.get("route")
    path_label = route.path if route is not None else request.url.path

    http_requests_total.labels(
        method=request.method, path=path_label, status_code=str(response.status_code)
    ).inc()
    http_request_duration_seconds.labels(method=request.method, path=path_label).observe(
        duration_seconds
    )

    logger.info(
        "request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_seconds * 1000, 2),
    )
    return response


@app.get("/metrics")
async def metrics() -> Response:
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


@app.get("/")
async def root() -> dict:
    return {"service": "forge-api", "status": "running"}
