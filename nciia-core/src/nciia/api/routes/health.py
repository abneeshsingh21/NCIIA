"""
Health Check Endpoints for N-CIIA

Enterprise-grade health endpoints compatible with:
  - Kubernetes liveness/readiness probes
  - Prometheus scraping
  - AWS / GCP load-balancer health checks
  - Uptime monitoring tools (e.g., Datadog, Pingdom)
"""

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request

from nciia.utils import get_settings

router = APIRouter()

# Module-level start time so uptime can be calculated
_PROCESS_START = time.monotonic()


@router.get("/health", summary="Liveness probe")
async def health_check(request: Request) -> dict[str, Any]:
    """
    Lightweight liveness check.

    Returns HTTP 200 as long as the process is running.
    Use this for Kubernetes liveness probes.
    """
    settings = get_settings()
    uptime = time.monotonic() - _PROCESS_START
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.version,
        "environment": settings.environment,
        "uptime_seconds": round(uptime, 2),
        "request_id": getattr(request.state, "request_id", None),
    }


@router.get("/health/ready", summary="Readiness probe")
async def readiness_check(request: Request) -> dict[str, Any]:
    """
    Readiness probe — checks all critical dependencies.

    Returns HTTP 200 if ready to serve traffic, 503 otherwise.
    Use this for Kubernetes readiness probes and load-balancer health checks.
    """
    from fastapi.responses import JSONResponse
    from nciia.db import get_database

    settings = get_settings()
    uptime = time.monotonic() - _PROCESS_START
    issues: list[str] = []

    # ── Database check ─────────────────────────────────────────────────────
    db_status = "ok"
    try:
        db = await get_database()
        if not db._connection:
            raise RuntimeError("No active connection")
        await db._connection.execute("SELECT 1")
    except Exception as exc:
        db_status = f"error: {exc}"
        issues.append(f"database: {exc}")

    overall = "ready" if not issues else "not_ready"
    payload: dict[str, Any] = {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.version,
        "environment": settings.environment,
        "uptime_seconds": round(uptime, 2),
        "request_id": getattr(request.state, "request_id", None),
        "components": {
            "database": db_status,
            "api": "ok",
        },
        "config": {
            "osint_sources_enabled": len(settings.osint.enabled_sources),
            "llm_provider": settings.llm.provider,
            "rate_limit": settings.api.rate_limit,
        },
    }

    if issues:
        return JSONResponse(status_code=503, content=payload)
    return payload


# Keep backward-compat alias
@router.get("/health/detailed", include_in_schema=False)
async def detailed_health_check(request: Request) -> dict[str, Any]:
    """Deprecated — use /health/ready instead."""
    return await readiness_check(request)
