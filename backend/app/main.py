"""FastAPI application entrypoint."""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import engine, init_db

logging.getLogger("app").setLevel(logging.INFO)
settings = get_settings()
logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add X-Request-ID to each request and response; set request.state.request_id for logging."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class CORSDebugMiddleware(BaseHTTPMiddleware):
    """Log CORS preflight (OPTIONS) requests for debugging."""

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            logger.info(
                "CORS Preflight: method=%s path=%s origin=%s "
                "access-control-request-method=%s access-control-request-headers=%s",
                request.method,
                request.url.path,
                request.headers.get("origin"),
                request.headers.get("access-control-request-method"),
                request.headers.get("access-control-request-headers"),
            )
        response = await call_next(request)
        if request.method == "OPTIONS":
            logger.info(
                "CORS Preflight Response: status=%s allow-origin=%s allow-methods=%s allow-headers=%s",
                response.status_code,
                response.headers.get("access-control-allow-origin"),
                response.headers.get("access-control-allow-methods"),
                response.headers.get("access-control-allow-headers"),
            )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    # shutdown if needed


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log 422 validation errors with full detail."""
    request_id = getattr(request.state, "request_id", None)
    logger.warning(
        "Request validation failed: request_id=%s path=%s method=%s errors=%s",
        request_id, request.url.path, request.method, exc.errors(),
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


app.add_middleware(RequestIDMiddleware)
# With allow_credentials=True, "*" is invalid per CORS spec — use explicit origins so preflight succeeds
_origins_raw = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
if not _origins_raw or _origins_raw == ["*"]:
    _origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
else:
    _origins = _origins_raw
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness():
    """Readiness: checks DB connectivity. Returns 503 if not ready."""
    checks = {"database": "unknown"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e!s}"
        return JSONResponse(status_code=503, content={"status": "not ready", "checks": checks})
    return {"status": "ready", "checks": checks}
