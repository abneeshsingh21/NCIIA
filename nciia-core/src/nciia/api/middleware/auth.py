"""
API Key Authentication Middleware for N-CIIA

If NCIIA_API_API_KEY is set in the environment, every incoming request must
carry a matching 'X-API-Key' header. Requests to /health and /docs are
exempt so monitoring tooling and developer documentation always remain
accessible.

Usage in server.py:
    app.add_middleware(APIKeyMiddleware)
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from nciia.utils import get_logger, get_settings

logger = get_logger(__name__)

# Routes that bypass API-key enforcement
_EXEMPT_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Bearer-style API key enforcement middleware.

    Activated only when settings.api.api_key is non-None / non-empty.
    Validates the 'X-API-Key' request header against the configured value.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        settings = get_settings()

        # Skip enforcement when no API key is configured
        configured_key = settings.api.api_key
        if not configured_key:
            return await call_next(request)

        # Exempt monitoring / docs routes
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES):
            return await call_next(request)

        # Validate header
        provided_key = request.headers.get("X-API-Key", "")
        if not provided_key or provided_key != configured_key:
            logger.warning(
                "api_key_rejected",
                path=path,
                client=request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "detail": "Missing or invalid X-API-Key header.",
                },
                headers={"WWW-Authenticate": "ApiKey"},
            )

        return await call_next(request)
