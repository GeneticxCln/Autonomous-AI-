"""
FastAPI Enterprise Application
Production-ready API server with authentication and security
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from .api_endpoints import api_router
from .api_security import (
    RateLimitMiddleware,
    SecurityMiddleware,
    api_security_config,
    create_error_response,
    log_api_access,
)
from .auth_models import db_manager as auth_db_manager
from .auth_service import auth_service
from .database_models import db_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("🚀 Starting Agent Enterprise API Server")

    try:
        # Initialize database
        db_manager.initialize()
        logger.info("✅ Database initialized successfully")

        # Initialize authentication database (separate manager)
        auth_db_manager.initialize()
        logger.info("✅ Authentication database initialized")

        # Setup authentication system
        auth_service.initialize()
        logger.info("✅ Authentication system initialized")

        # Log startup
        logger.info("🎉 FastAPI application startup completed")
        yield

    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        raise
    finally:
        # Shutdown
        logger.info("🔄 Shutting down Agent Enterprise API Server")
        db_manager.close()
        logger.info("✅ Application shutdown completed")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    # Create FastAPI app with custom settings
    app = FastAPI(
        title="Agent Enterprise API",
        description="""
        ## 🚀 Enterprise-Grade Autonomous Agent API

        This API provides secure, authenticated access to autonomous agent operations
        with role-based access control and comprehensive security features.

        ### 🔐 Authentication
        - JWT-based authentication with access/refresh tokens
        - API token support for programmatic access
        - Role-based access control (RBAC)

        ### 🛡️ Security Features
        - Rate limiting (100 requests/minute per IP)
        - CORS protection
        - Security headers
        - Request audit logging
        - Account lockout protection

        ### 👥 User Roles
        - **admin**: Full system access
        - **manager**: Elevated privileges
        - **user**: Standard access
        - **guest**: Limited access

        ### 🔑 API Token Usage
        Include tokens in the Authorization header:
        ```
        Authorization: Bearer <your-jwt-token>
        ```
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Add security middleware
    if api_security_config.rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware)
        logger.info("✅ Rate limiting middleware enabled")

    if api_security_config.security_headers_enabled:
        app.add_middleware(SecurityMiddleware)
        logger.info("✅ Security headers middleware enabled")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_security_config.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.info(f"✅ CORS middleware enabled for origins: {api_security_config.cors_origins}")

    # Add trusted host middleware for production
    if os.getenv("ENVIRONMENT") == "production":
        app.add_middleware(
            TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "*.yourdomain.com"]
        )
        logger.info("✅ Trusted host middleware enabled")

    # Include API router
    app.include_router(api_router)
    logger.info("✅ API routes included")

    # Global exception handler
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions with consistent error format."""
        log_api_access(request, status_code=exc.status_code)
        return create_error_response(
            message=exc.detail, error_type="HTTP_EXCEPTION", status_code=exc.status_code
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions."""
        logger.error(f"Unexpected error: {exc}", exc_info=True)
        log_api_access(request, status_code=500)
        return create_error_response(
            message="Internal server error", error_type="INTERNAL_ERROR", status_code=500
        )

    # Custom OpenAPI schema
    def custom_openapi():
        """Generate custom OpenAPI schema with security schemes."""
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title="Agent Enterprise API",
            version="1.0.0",
            description="Enterprise-grade API for autonomous agent operations",
            routes=app.routes,
        )

        # Add security schemes
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT access token",
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API token for programmatic access",
            },
        }

        # Add global security requirement
        openapi_schema["security"] = [{"BearerAuth": []}]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # Root endpoint
    @app.get("/", tags=["System"])
    async def root():
        """Root endpoint with API information."""
        return {
            "message": "🚀 Agent Enterprise API",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/api/v1/system/health",
        }

    # Health check endpoint (no auth required)
    @app.get("/health", tags=["System"])
    async def health_check():
        """Basic health check endpoint."""
        try:
            # Use auth service's database manager for consistency
            with auth_service.db.get_session() as session:
                from sqlalchemy import text

                session.execute(text("SELECT 1"))
            return {"status": "healthy", "database": "connected"}
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "database": "disconnected", "error": str(e)},
            )

    # API information endpoint
    @app.get("/api/info", tags=["System"])
    async def api_info():
        """Get API information and available endpoints."""
        return {
            "api": "Agent Enterprise API",
            "version": "1.0.0",
            "endpoints": {
                "authentication": {
                    "login": "POST /api/v1/auth/login",
                    "logout": "POST /api/v1/auth/logout",
                    "refresh": "POST /api/v1/auth/refresh",
                    "me": "GET /api/v1/auth/me",
                },
                "users": {"create": "POST /api/v1/users", "list": "GET /api/v1/users"},
                "agents": {
                    "create": "POST /api/v1/agents",
                    "list": "GET /api/v1/agents",
                    "get": "GET /api/v1/agents/{id}",
                    "execute": "POST /api/v1/agents/{id}/execute",
                },
                "goals": {"create": "POST /api/v1/goals", "list": "GET /api/v1/goals"},
                "api_tokens": {
                    "create": "POST /api/v1/api-tokens",
                    "list": "GET /api/v1/api-tokens",
                },
                "system": {
                    "health": "GET /api/v1/system/health",
                    "info": "GET /api/v1/system/info",
                },
            },
            "authentication": "JWT Bearer tokens or API keys",
            "rate_limit": "100 requests per minute per IP",
        }

    return app


# Create global app instance
app = create_app()

# Application entry points
if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Agent Enterprise API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")

    args = parser.parse_args()

    logger.info(f"Starting server on {args.host}:{args.port}")
    uvicorn.run(
        "agent_system.fastapi_app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level="info",
    )
