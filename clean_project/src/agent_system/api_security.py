"""
FastAPI Security Middleware
Enterprise-grade security for API endpoints
"""

# ruff: noqa: I001

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from logging import getLogger
from typing import Any, Callable, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from .auth_models import AuthenticationError, SecurityContext as AuthSecurityContext, TokenExpiredError
from .auth_service import auth_service
from .production_config import get_config

logger = getLogger(__name__)


class APIError(Exception):
    """Custom API error for unified error responses."""

    def __init__(self, message: str, *, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(message)
        self.status_code = status_code


http_bearer = HTTPBearer(auto_error=False)


SecurityContext = AuthSecurityContext


def create_error_response(
    *, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, error_type: Optional[str] = None
) -> JSONResponse:
    payload: Dict[str, Any] = {
        "success": False,
        "error": error_type or "ERROR",
        "message": message,
        "timestamp": datetime.now(UTC).timestamp(),
        "status": status_code,
    }
    return JSONResponse(status_code=status_code, content=payload)


def create_api_response(
    data: Any,
    *,
    status_code: int = status.HTTP_200_OK,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    payload: Dict[str, Any] = {
        "success": True,
        "data": data,
        "status": status_code,
        "timestamp": datetime.now(UTC).timestamp(),
    }
    if message:
        payload["message"] = message
    if metadata:
        payload["meta"] = metadata
    return JSONResponse(status_code=status_code, content=payload)


async def get_current_security_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Optional[SecurityContext]:
    """Extract the authenticated security context from the Authorization header."""
    if not credentials:
        return None

    token = credentials.credentials
    try:
        return auth_service.verify_token(token)
    except (TokenExpiredError, AuthenticationError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def require_permission(resource: str, action: str) -> Callable[[SecurityContext], SecurityContext]:
    """Dependency to enforce that a request has the specified permission."""

    def _checker(ctx: Optional[SecurityContext] = Depends(get_current_security_context)) -> SecurityContext:
        if ctx is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        if not ctx.has_permission(resource, action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return ctx

    return _checker


# --------------------- FastAPI middleware helpers ---------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """No-op rate limiter placeholder; integrate real limiter if needed."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        response = await call_next(request)
        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    """Adds a minimal set of security headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


@dataclass
class APISecurityConfig:
    rate_limit_enabled: bool = False
    security_headers_enabled: bool = True
    cors_origins: list[str] = None

    def __post_init__(self) -> None:
        if self.cors_origins is None:
            self.cors_origins = ["*"]


def _load_api_security_config() -> APISecurityConfig:
    cfg = get_config()
    cors_origins = list(getattr(cfg, "cors_origins", ["*"])) if cfg else ["*"]
    return APISecurityConfig(
        rate_limit_enabled=bool(getattr(cfg, "enable_rate_limiting", False)),
        security_headers_enabled=True,
        cors_origins=cors_origins,
    )


api_security_config = _load_api_security_config()


def log_api_access(request: Request, *, status_code: int) -> None:
    """Structured API access logging."""
    try:
        logger.info(
            "access",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "client": getattr(request.client, "host", None),
            },
        )
    except Exception:
        # Logging must not break requests
        pass


async def check_custom_rate_limit(
    namespace: str,
    key: str,
    limit: int,
    window_seconds: int,
) -> bool:
    """Placeholder rate limiter; returns False when under limit."""
    # TODO: Implement Redis-based rate limiting with counters per namespace/key
    return False
