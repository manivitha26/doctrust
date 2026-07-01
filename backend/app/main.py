import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.core.logging import setup_logging, get_logger
from app.database import create_indexes, ping_db
from app.routers import documents, query


# Initialize logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    logger.info("docutrust_starting", version=settings.APP_VERSION)
    db_ok = await ping_db()
    if db_ok:
        logger.info("mongodb_connected")
        await create_indexes()
    else:
        logger.warning("mongodb_unreachable")
    yield
    logger.info("docutrust_shutdown")


# Rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise Advanced RAG Platform with Automated Self-Correction",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    structlog.contextvars.bind_contextvars(request_id=request_id)
    start = time.perf_counter()
    response = await call_next(request)
    latency = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        latency_ms=latency,
    )
    structlog.contextvars.clear_contextvars()
    return response

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers

app.include_router(documents.router, prefix=settings.API_V1_PREFIX)
# Auth router omitted for auth‑less mode
app.include_router(query.router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check():
    db_ok = await ping_db()
    return {
        "status": "healthy" if db_ok else "degraded",
        "version": settings.APP_VERSION,
        "database": "connected" if db_ok else "unreachable",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
