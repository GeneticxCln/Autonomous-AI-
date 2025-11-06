"""
FastAPI Security Middleware
Enterprise-grade security for API endpoints
"""
from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import json
from collections import defaultdict

from .auth_service import auth_service, AuthenticationError, AuthorizationError, SecurityContext
from .auth_models import UserModel

logger = logging.getLogger(__name__)

# Security scheme for OpenAPI documentation
security = HTTPBearer()

# Rate limiting storage (in production, use Redis)
rate_limit_store = defaultdict(list)
RATE_LIMIT_REQUESTS = 100  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Clean old entries
        rate_limit_store[client_ip] = [
            timestamp for timestamp in rate_limit_store[client_ip]
            if current_time - timestamp < RATE_LIMIT_WINDOW
        ]

        # Check rate limit
        if len(rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {RATE_LIMIT_REQUESTS} requests per minute allowed"
                }
            )

        # Add current request
        rate_limit_store[client_ip].append(current_time)

        response = await call_next(request)
        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for additional protections."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Add security headers
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Log API access
        process_time = time.time() - start_time
        logger.info(
            f"API Access: {request.method} {request.url.path} - "
            f"IP: {request.client.host if request.client else 'unknown'} - "
            f"Time: {process_time:.3f}s"
        )

        return response


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
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
    credentials: HTTPAuthorizationCredentials = Depends(security)
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


def require_permission(resource: str, action: str):
    """Dependency to require specific permission."""
    async def permission_checker(security_context: SecurityContext = Depends(get_current_security_context)):
        if not security_context.has_permission(resource, action):
            logger.warning(
                f"Permission denied: {security_context.user.username} "
                f"attempted {resource}.{action}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {resource}.{action}"
            )
        return security_context
    return permission_checker


def require_admin():
    """Dependency to require admin privileges."""
    async def admin_checker(security_context: SecurityContext = Depends(get_current_security_context)):
        if not security_context.is_admin:
            logger.warning(
                f"Admin access denied: {security_context.user.username}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        return security_context
    return admin_checker


class APISecurityConfig:
    """API security configuration."""

    def __init__(self):
        self.cors_origins = ["*"]  # Configure appropriately for production
        self.rate_limit_enabled = True
        self.security_headers_enabled = True
        self.audit_logging_enabled = True

    def get_cors_middleware(self):
        """Get configured CORS middleware."""
        return CORSMiddleware(
            allow_origins=self.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )


def create_security_error_response(error_type: str, message: str, status_code: int = 400) -> JSONResponse:
    """Create standardized security error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_type,
            "message": message,
            "timestamp": time.time()
        }
    )


def log_api_access(request: Request, user: Optional[UserModel] = None, status_code: int = 200):
    """Log API access for security auditing."""
    log_data = {
        "timestamp": time.time(),
        "method": request.method,
        "path": str(request.url.path),
        "ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent"),
        "status_code": status_code
    }

    if user:
        log_data["user_id"] = user.id
        log_data["username"] = user.username

    logger.info(f"API Access: {json.dumps(log_data)}")


def create_api_response(data: Any = None, message: str = "Success", status_code: int = 200) -> JSONResponse:
    """Create standardized API response."""
    response_data = {
        "success": True,
        "message": message,
        "timestamp": time.time()
    }

    if data is not None:
        response_data["data"] = data

    return JSONResponse(status_code=status_code, content=response_data)


def create_error_response(message: str, error_type: str = "API_ERROR", status_code: int = 400) -> JSONResponse:
    """Create standardized error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": error_type,
            "message": message,
            "timestamp": time.time()
        }
    )


# Global security configuration
api_security_config = APISecurityConfig()
