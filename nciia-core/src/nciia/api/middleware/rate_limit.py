"""
In-Memory Sliding-Window Rate Limiter Middleware for N-CIIA

Limits incoming requests per client IP address using a sliding-window
counter stored in a shared asyncio-safe dictionary.

Configuration via environment variables:
    NCIIA_API_RATE_LIMIT  – max requests allowed per window (default: 100)
    NCIIA_API_RATE_WINDOW – window size in seconds (default: 60)

Usage in server.py:
    app.add_middleware(RateLimitMiddleware)
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from nciia.utils import get_logger, get_settings

logger = get_logger(__name__)

# Exempt health checks from rate limiting
_EXEMPT_PREFIXES = ("/health",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter keyed on client IP.

    For each IP, we maintain a deque of timestamps. On each request:
      1. Evict timestamps older than the window.
      2. If count >= limit → 429.
      3. Else record timestamp and proceed.
    """

    def __init__(self, app, *, limit: int | None = None, window: int = 60) -> None:
        super().__init__(app)
        settings = get_settings()
        self._limit: int = limit or settings.api.rate_limit or 100
        self._window: int = window  # seconds
        self._lock = asyncio.Lock()
        # IP → deque of request timestamps
        self._timestamps: dict[str, Deque[float]] = defaultdict(deque)

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP, honouring X-Forwarded-For."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # Exempt health-check routes
        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.monotonic()
        window_start = now - self._window

        async with self._lock:
            timestamps = self._timestamps[client_ip]

            # Evict stale timestamps outside the current window
            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()

            if len(timestamps) >= self._limit:
                retry_after = int(self._window - (now - timestamps[0]))
                logger.warning(
                    "rate_limit_exceeded",
                    client_ip=client_ip,
                    path=path,
                    count=len(timestamps),
                    limit=self._limit,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too Many Requests",
                        "detail": f"Rate limit of {self._limit} req/{self._window}s exceeded.",
                        "retry_after": retry_after,
                    },
                    headers={
                        "Retry-After": str(max(retry_after, 1)),
                        "X-RateLimit-Limit": str(self._limit),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            timestamps.append(now)
            remaining = self._limit - len(timestamps)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = str(self._window)
        return response
