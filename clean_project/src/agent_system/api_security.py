"""
FastAPI Security Middleware
Enterprise-grade security for API endpoints
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from typing import Any, DefaultDict, List, Optional, cast

try:
    from .production_config import get_config

    _cfg = get_config()
    RATE_LIMIT_REQUESTS = int(_cfg.rate_limit_requests)
    RATE_LIMIT_WINDOW = int(_cfg.rate_limit_window)
    _CORS_ORIGINS = _cfg.get_cors_origins()
except Exception:
    # Safe fallbacks
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_WINDOW = 60
    _CORS_ORIGINS = ["*"]

from fastapi import Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from .auth_models import AuthorizationError, SecurityContext, UserModel
from .auth_service import AuthenticationError, auth_service

logger = logging.getLogger(__name__)

# Security scheme for OpenAPI documentation
security = HTTPBearer()

# Rate limiting storage (in production, use Redis)
rate_limit_store: DefaultDict[str, List[float]] = defaultdict(list)
_custom_rate_limit_store: DefaultDict[str, List[float]] = defaultdict(list)
_custom_rl_redis: Any | None = None
_custom_rl_enabled: bool = False
_custom_rl_inited: bool = False


def _init_custom_rl() -> None:
    """Initialize Redis client for custom rate limits if REDIS_URL/URI is set."""
    global _custom_rl_inited, _custom_rl_enabled, _custom_rl_redis
    if _custom_rl_inited:
        return
    _custom_rl_inited = True
    redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_URI")
    if not redis_url:
        return
    try:
        import redis

        _custom_rl_redis = redis.Redis.from_url(redis_url, decode_responses=True)
        _custom_rl_redis.ping()
        _custom_rl_enabled = True
        logger.info("Custom rate-limit: using Redis backend")
    except Exception as e:
        logger.warning(f"Custom rate-limit: Redis unavailable, using memory: {e}")


def check_custom_rate_limit(namespace: str, key: str, limit: int, window_seconds: int) -> bool:
    """Return True if rate limit exceeded for custom buckets (e.g., login)."""
    _init_custom_rl()
    now = time.time()
    if _custom_rl_enabled and _custom_rl_redis is not None:
        bucket = int(now // window_seconds)
        redis_key = f"rl:{namespace}:{key}:{bucket}"
        try:
            count = cast(int, _custom_rl_redis.incr(redis_key))
            if count == 1:
                _custom_rl_redis.expire(redis_key, window_seconds)
            return count > limit
        except Exception as e:
            logger.warning(f"Custom rate-limit redis error: {e}; falling back to memory")

    # In-memory fallback
    mem_key = f"{namespace}:{key}"
    _custom_rate_limit_store[mem_key] = [
        t for t in _custom_rate_limit_store[mem_key] if now - t < window_seconds
    ]
    if len(_custom_rate_limit_store[mem_key]) >= limit:
        return True
    _custom_rate_limit_store[mem_key].append(now)
    return False


class RateLimitMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    """Rate limiting middleware with optional Redis backend."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._redis: Any | None = None
        self._redis_enabled: bool = False
        redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_URI")
        if redis_url:
            try:
                import redis

                self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                self._redis_enabled = True
                logger.info("RateLimitMiddleware: using Redis backend")
            except Exception as e:
                logger.warning(
                    f"RateLimitMiddleware: Redis unavailable, falling back to in-memory: {e}"
                )

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Prefer Redis if configured and healthy; in-memory only if Redis unavailable
        if self._redis_enabled and self._redis is not None:
            bucket = int(current_time // RATE_LIMIT_WINDOW)
            key = f"ratelimit:{client_ip}:{bucket}"
            try:
                count = self._redis.incr(key)
                if count == 1:
                    self._redis.expire(key, RATE_LIMIT_WINDOW)
                if count > RATE_LIMIT_REQUESTS:
                    logger.warning(f"Rate limit exceeded (redis) for IP: {client_ip}")
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "error": "Rate limit exceeded",
                            "message": f"Maximum {RATE_LIMIT_REQUESTS} requests per minute allowed",
                        },
                    )
                # Redis path OK - proceed without touching in-memory store
                response = await call_next(request)
                return response
            except Exception as e:
                logger.warning(f"RateLimitMiddleware: Redis error, using in-memory fallback: {e}")

        # In-memory fallback
        rate_limit_store[client_ip] = [
            t for t in rate_limit_store[client_ip] if current_time - t < RATE_LIMIT_WINDOW
        ]
        if len(rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {RATE_LIMIT_REQUESTS} requests per minute allowed",
                },
            )
        rate_limit_store[client_ip].append(current_time)

        response = await call_next(request)
        return response


class SecurityMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    """Security middleware for additional protections."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        start_time = time.time()

        # Add security headers
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # X-XSS-Protection is deprecated; rely on CSP instead
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Content Security Policy
        try:
            from .production_config import get_config

            cfg = get_config()
            if cfg.is_production():
                csp = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; object-src 'none'"
            else:
                csp = "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; img-src 'self' data:"
            response.headers["Content-Security-Policy"] = csp
        except Exception:
            pass

        # Log API access
        process_time = time.time() - start_time
        logger.info(
            f"API Access: {request.method} {request.url.path} - "
            f"IP: {request.client.host if request.client else 'unknown'} - "
            f"Time: {process_time:.3f}s"
        )

        return response


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserModel:
    """Get current authenticated user from JWT token."""
    try:
        token = credentials.credentials
        security_context = auth_service.verify_token(token)
        return security_context.user
    except (AuthenticationError, AuthorizationError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_security_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> SecurityContext:
    """Get current security context with permissions."""
    try:
        token = credentials.credentials
        security_context = auth_service.verify_token(token)
        return security_context
    except (AuthenticationError, AuthorizationError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_permission(resource: str, action: str) -> Any:
    """Dependency to require specific permission."""

    async def permission_checker(
        security_context: SecurityContext = Depends(get_current_security_context),
    ) -> SecurityContext:
        if not security_context.has_permission(resource, action):
            logger.warning(
                f"Permission denied: {security_context.user.username} "
                f"attempted {resource}.{action}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {resource}.{action}",
            )
        return security_context

    return permission_checker


def require_admin() -> Any:
    """Dependency to require admin privileges."""

    async def admin_checker(
        security_context: SecurityContext = Depends(get_current_security_context),
    ) -> SecurityContext:
        if not security_context.is_admin:
            logger.warning(f"Admin access denied: {security_context.user.username}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
            )
        return security_context

    return admin_checker


class APISecurityConfig:
    """API security configuration."""

    def __init__(self) -> None:
        self.cors_origins: List[str] = _CORS_ORIGINS
        self.rate_limit_enabled: bool = True
        self.security_headers_enabled: bool = True
        self.audit_logging_enabled: bool = True

    def get_cors_middleware(self) -> Any:
        """Get configured CORS middleware."""
        allow_creds = not (self.cors_origins == ["*"] or "*" in self.cors_origins)
        return CORSMiddleware(
            allow_origins=self.cors_origins,
            allow_credentials=allow_creds,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )


def create_security_error_response(
    error_type: str, message: str, status_code: int = 400
) -> JSONResponse:
    """Create standardized security error response."""
    return JSONResponse(
        status_code=status_code,
        content={"error": error_type, "message": message, "timestamp": time.time()},
    )


def log_api_access(request: Request, user: Optional[UserModel] = None, status_code: int = 200) -> None:
    """Log API access for security auditing."""
    log_data = {
        "timestamp": time.time(),
        "method": request.method,
        "path": str(request.url.path),
        "ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent"),
        "status_code": status_code,
    }

    if user:
        log_data["user_id"] = user.id
        log_data["username"] = user.username

    logger.info(f"API Access: {json.dumps(log_data)}")


def create_api_response(
    data: Any = None, message: str = "Success", status_code: int = 200
) -> JSONResponse:
    """Create standardized API response."""
    response_data = {"success": True, "message": message, "timestamp": time.time()}

    if data is not None:
        response_data["data"] = data

    return JSONResponse(status_code=status_code, content=response_data)


def create_error_response(
    message: str, error_type: str = "API_ERROR", status_code: int = 400
) -> JSONResponse:
    """Create standardized error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": error_type,
            "message": message,
            "timestamp": time.time(),
        },
    )


# Global security configuration
api_security_config = APISecurityConfig()
