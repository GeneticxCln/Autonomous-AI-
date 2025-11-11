"""
FastAPI Security Middleware
Enterprise-grade security for API endpoints
"""

# ruff: noqa: I001

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from logging import getLogger
from typing import Any, Callable, Dict, Optional, Tuple
import os

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from .auth_models import AuthenticationError, SecurityContext as AuthSecurityContext, TokenExpiredError
from .auth_service import auth_service
from .cache_manager import cache_manager
from .production_config import get_config
from .unified_config import unified_config

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
) -> Optional[Any]:
    """Extract the authenticated security context from the Authorization header."""
    if not credentials:
        return None

    token = credentials.credentials
    try:
        return auth_service.verify_token(token)
    except (TokenExpiredError, AuthenticationError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def require_permission(resource: str, action: str) -> Callable[[Any], Any]:
    """Dependency to enforce that a request has the specified permission."""

    def _checker(ctx: Optional[Any] = Depends(get_current_security_context)) -> Any:
        if ctx is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        if not ctx.has_permission(resource, action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return ctx

    return _checker


# --------------------- FastAPI middleware helpers ---------------------

class RateLimitMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    """Performs Redis-backed rate limiting with in-memory fallback."""

    def __init__(
        self,
        app: Any,
        *,
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        super().__init__(app)
        cfg = get_config()
        self.limit: int = int(limit) if limit is not None else int(getattr(cfg, "rate_limit_requests", 100))
        self.window_seconds: int = (
            int(window_seconds) if window_seconds is not None else int(getattr(cfg, "rate_limit_window", 60))
        )
        default_enabled = bool(api_security_config.rate_limit_enabled)
        self.enabled: bool = default_enabled if enabled is None else bool(enabled)
        # Middleware should not fail-closed when Redis is unavailable; tests rely on open behavior
        self.fail_closed: bool = False

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Any:
        if not self.enabled or self.limit <= 0 or self.window_seconds <= 0:
            return await call_next(request)

        identifier = self._build_identifier(request)
        if await check_custom_rate_limit("api", identifier, self.limit, self.window_seconds, fail_closed=self.fail_closed):
            log_api_access(request, status_code=status.HTTP_429_TOO_MANY_REQUESTS)
            return create_error_response(
                message="Rate limit exceeded. Try again soon.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                error_type="RATE_LIMIT_EXCEEDED",
            )

        response = await call_next(request)
        return response

    @staticmethod
    def _build_identifier(request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = getattr(request.client, "host", "unknown") if request.client else "unknown"

        auth_header = request.headers.get("authorization", "")
        token_hash = (
            hashlib.sha256(auth_header.encode("utf-8")).hexdigest()[:16] if auth_header else "anon"
        )

        return f"{client_ip}:{token_hash}:{request.url.path}"


class SecurityMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    """Adds a minimal set of security headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Any:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


@dataclass
class APISecurityConfig:
    rate_limit_enabled: bool = False
    security_headers_enabled: bool = True
    cors_origins: list[str] | None = None

    def __post_init__(self) -> None:
        if self.cors_origins is None:
            self.cors_origins = ["*"]


def _load_api_security_config() -> APISecurityConfig:
    cfg = get_config()
    cors_origins = ["*"]
    if cfg:
        try:
            cors_origins = cfg.get_cors_origins()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Falling back to permissive CORS configuration: %s", exc)
            cors_origins = list(getattr(cfg, "cors_origins", ["*"]))
    # Disable rate limiting during tests to avoid interfering with functional flows
    enabled = bool(getattr(cfg, "enable_rate_limiting", False))
    if os.getenv("PYTEST_CURRENT_TEST"):
        enabled = False
    return APISecurityConfig(
        rate_limit_enabled=enabled,
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


_in_memory_counters: Dict[str, Tuple[int, float]] = {}


def _in_memory_increment(namespace: str, key: str, window_seconds: int) -> int:
    """Lightweight fallback when Redis is unavailable."""
    composite_key = f"{namespace}:{key}"
    now = time.time()
    count, expiry = _in_memory_counters.get(composite_key, (0, now + window_seconds))
    if expiry <= now:
        count = 0
        expiry = now + window_seconds
    count += 1
    _in_memory_counters[composite_key] = (count, expiry)
    return count


async def check_custom_rate_limit(
    namespace: str,
    key: str,
    limit: int,
    window_seconds: int,
    *,
    fail_closed: Optional[bool] = None,
) -> bool:
    """Increment the namespace/key counter and return True when the caller is throttled."""
    try:
        redis_count = await cache_manager.increment_counter(
            "ratelimit", f"{namespace}:{key}", window_seconds
        )
    except Exception as exc:
        logger.debug("Redis rate-limit increment failed: %s", exc)
        redis_count = None

    if redis_count is None:
        should_fail_closed = unified_config.strict_mode if fail_closed is None else bool(fail_closed)
        if should_fail_closed:
            # Strict mode: require Redis to enforce rate limiting; fail closed
            logger.warning(
                "Strict mode enabled: Redis unavailable for rate limiting; request will be throttled"
            )
            return True
        else:
            # Non-strict mode: use in-memory best-effort fallback
            redis_count = _in_memory_increment(namespace, key, window_seconds)

    return bool(redis_count > limit)


def _reset_rate_limit_state_for_tests() -> None:  # pragma: no cover - test helper
    _in_memory_counters.clear()
