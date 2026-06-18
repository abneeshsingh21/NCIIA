"""
FastAPI Server for N-CIIA

Enterprise-grade server with:
  - X-Request-ID tracing middleware
  - API key authentication (optional)
  - Sliding-window rate limiting
  - Strict CORS configuration
  - Detailed structured logging
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from nciia.api.routes import (
    signals, personas, cases, evidence,
    assistant, health, ingestion, response, intelligence, threats,
)
from nciia.api.websocket import websocket_router
from nciia.api.middleware import APIKeyMiddleware, RateLimitMiddleware
from nciia.db import get_database, close_database
from nciia.utils import get_settings, setup_logging, get_logger

logger = get_logger(__name__)

# ============================================================================
# Application lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager — startup / shutdown hooks."""
    settings = get_settings()

    # Configure structured logging first so all startup logs are captured
    setup_logging(
        level=settings.logging.level,
        format=settings.logging.format,
        file_path=settings.logging.file_path,
        include_timestamp=settings.logging.include_timestamp,
    )

    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=settings.version,
        environment=settings.environment,
    )

    # ── Database ──────────────────────────────────────────────────────────
    await get_database(settings.database.path)
    logger.info("database_initialized", path=settings.database.path)

    # ── OSINT Collector ───────────────────────────────────────────────────
    from nciia.ingestion.collector import get_collector
    collector = await get_collector()
    await collector.start()
    logger.info("collector_started")

    # ── Hunter Agent ──────────────────────────────────────────────────────
    from nciia.hunter.agent import get_hunter
    hunter = get_hunter()
    await hunter.start()
    logger.info("hunter_started")

    # Record startup time for uptime tracking
    app.state.started_at = time.monotonic()

    yield  # ── Running ────────────────────────────────────────────────────

    # ── Teardown ──────────────────────────────────────────────────────────
    from nciia.ingestion.collector import get_collector as _gc
    (await _gc()).stop() and None  # type: ignore[func-returns-value]
    logger.info("collector_stopped")

    from nciia.hunter.agent import get_hunter as _gh
    await _gh().stop()
    logger.info("hunter_stopped")

    await close_database()
    logger.info("application_shutdown")


# ============================================================================
# Application factory
# ============================================================================

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="N-CIIA API",
        description=(
            "National Cyber Investigation & Intelligence Assistant — "
            "Enterprise Threat Intelligence Platform"
        ),
        version=settings.version,
        docs_url="/docs" if settings.api.debug else None,
        redoc_url="/redoc" if settings.api.debug else None,
        openapi_url="/openapi.json" if settings.api.debug else None,
        lifespan=lifespan,
    )

    # ── CORS (strict) ─────────────────────────────────────────────────────
    # In production: set NCIIA_API_CORS_ORIGINS to your exact frontend origin.
    # Wildcard '*' is NOT permitted here.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )

    # ── Rate limiting ─────────────────────────────────────────────────────
    app.add_middleware(RateLimitMiddleware)

    # ── API key authentication ────────────────────────────────────────────
    app.add_middleware(APIKeyMiddleware)

    # ── X-Request-ID tracing ──────────────────────────────────────────────
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Routes ────────────────────────────────────────────────────────────
    app.include_router(health.router, tags=["Health"])
    app.include_router(signals.router,      prefix="/api/signals",      tags=["Signals"])
    app.include_router(personas.router,     prefix="/api/personas",     tags=["Personas"])
    app.include_router(cases.router,        prefix="/api/cases",        tags=["Cases"])
    app.include_router(evidence.router,     prefix="/api/evidence",     tags=["Evidence"])
    app.include_router(assistant.router,    prefix="/api/assistant",    tags=["AI Assistant"])
    app.include_router(ingestion.router,    prefix="/api/ingestion",    tags=["OSINT Ingestion"])
    app.include_router(response.router,     prefix="/api/response",     tags=["Response"])
    app.include_router(intelligence.router, prefix="/api/intelligence", tags=["Intelligence"])
    app.include_router(threats.router,      prefix="/api/threats",      tags=["Threat Intelligence"])
    app.include_router(websocket_router,    prefix="/ws",               tags=["WebSocket"])

    # ── Global exception handler ──────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "unhandled_exception",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "request_id": request_id,
                "detail": str(exc) if settings.api.debug else None,
            },
            headers={"X-Request-ID": request_id},
        )

    return app


# ============================================================================
# Application instance
# ============================================================================

app = create_app()


def run() -> None:
    """Run the server using uvicorn."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "nciia.api.server:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.debug,
        log_level="debug" if settings.api.debug else "warning",
        access_log=settings.api.debug,
    )


if __name__ == "__main__":
    run()
