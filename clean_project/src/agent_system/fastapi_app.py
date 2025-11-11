"""
FastAPI Enterprise Application
Production-ready API server with authentication and security
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Mapping,
    Optional,
    Tuple,
    Union,
    cast,
)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, Response

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Histogram,
        generate_latest,
    )

    _PROM = True
except Exception:
    _PROM = False

from .api_endpoints import api_router
from .api_schemas import (
    AgentCapabilityDescriptor,
    AgentCreate,
    AgentExecute,
    AgentExecutionResponse,
    AgentResponse,
    APIError,
    APIResponse,
    APITokenCreate,
    APITokenResponse,
    BulkOperationRequest,
    BulkOperationResponse,
    CapabilityRecord,
    CapabilityRegisterRequest,
    ErrorDetail,
    GoalCreate,
    GoalResponse,
    LoginRequest,
    LoginResponse,
    PaginatedResponse,
    PaginationInfo,
    RateLimitInfo,
    RoleLevel,
    SecurityEventResponse,
    SecurityEventType,
    SecuritySeverity,
    SystemHealth,
    SystemInfo,
    TokenData,
    TokenRefreshRequest,
    UserCreate,
    UserInfo,
    UserResponse,
    UserStatus,
    UserUpdate,
    WebhookEvent,
)
from .api_security import (
    RateLimitMiddleware,
    SecurityMiddleware,
    api_security_config,
    create_error_response,
    log_api_access,
)
from .async_utils import run_blocking
from .auth_models import db_manager as auth_db_manager
from .auth_service import auth_service
from .config_simple import get_api_key, settings
from .database_models import db_manager
from .infrastructure_manager import agent_shutdown_integration, agent_startup_integration
from .production_config import get_config
from .unified_config import unified_config

# Prometheus metrics state (module-level), created lazily

_PROMETHEUS_METRICS_CREATED = False
REQUEST_COUNT: Optional["Counter"] = None
REQUEST_LATENCY: Optional["Histogram"] = None
PROM_REGISTRY: Optional["CollectorRegistry"] = None

# Predeclare optional monitoring variables for type-checking
if TYPE_CHECKING:
    from .advanced_monitoring import AdvancedMonitoringSystem

_mon: Optional["AdvancedMonitoringSystem"]
_init_mon: Optional[Callable[[], Awaitable[bool]]]

if _PROM:
    from .advanced_monitoring import initialize_monitoring as _init_mon
    from .advanced_monitoring import monitoring_system as _mon
else:
    _mon = None
    _init_mon = None

monitoring: Any | None = _mon
initialize_monitoring: Callable[[], Awaitable[bool]] | None = _init_mon

# Set test-friendly infra skip after all imports
if "PYTEST_CURRENT_TEST" in os.environ:
    os.environ.setdefault("SKIP_INFRA_STARTUP", "true")

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan events."""
    # Startup
    logger.info("🚀 Starting Agent Enterprise API Server")
    cfg = get_config()

    try:
        # Initialize database (prefer DATABASE_URL env)
        primary_db_url = os.getenv("DATABASE_URL") or cfg.get_database_url()
        db_manager.database_url = primary_db_url
        db_manager.configure_pool(
            pool_size=cfg.db_pool_size,
            max_overflow=cfg.db_max_overflow,
            pool_timeout=cfg.db_pool_timeout,
            pool_recycle=cfg.db_pool_recycle,
        )
        logger.debug("Initializing primary database")
        await run_blocking(db_manager.initialize)
        logger.debug("Primary database ready")
        logger.info("✅ Database initialized successfully")

        # Initialize authentication database (prefer AUTH_DATABASE_URL or fallback to DATABASE_URL)
        auth_db_url = os.getenv("AUTH_DATABASE_URL") or primary_db_url
        auth_db_manager.database_url = auth_db_url
        auth_db_manager.configure_pool(
            pool_size=cfg.db_pool_size,
            max_overflow=cfg.db_max_overflow,
            pool_timeout=cfg.db_pool_timeout,
            pool_recycle=cfg.db_pool_recycle,
        )
        logger.debug("Initializing auth database")
        await run_blocking(auth_db_manager.initialize)
        logger.debug("Auth database ready")
        logger.info("✅ Authentication database initialized")

        # Setup authentication system
        logger.debug("Initializing auth service defaults")
        await run_blocking(auth_service.initialize)
        logger.debug("Auth service ready")
        logger.info("✅ Authentication system initialized")

        # Initialize infrastructure stack (cache, queue, distributed services)
        if os.getenv("SKIP_INFRA_STARTUP", "false").lower() == "true":
            logger.info("⚙️  Infrastructure startup skipped via SKIP_INFRA_STARTUP")
        else:
            await agent_startup_integration()
            logger.info("✅ Infrastructure stack initialized")

        if _PROM and initialize_monitoring is not None:
            await initialize_monitoring()
            logger.info("✅ Monitoring system initialized")

        # Initialize distributed tracing (optional)
        try:
            if str(os.getenv("ENABLE_TRACING", "false")).lower() == "true":
                from .distributed_tracing import initialize_tracing, tracing_manager

                jaeger_host = os.getenv("JAEGER_HOST", "localhost")
                jaeger_port = int(os.getenv("JAEGER_PORT", "14268"))
                if initialize_tracing(
                    jaeger_host=jaeger_host,
                    jaeger_port=jaeger_port,
                    service_name="agent-enterprise-api",
                ):
                    try:
                        tracing_manager.instrument_sqlalchemy(db_manager.engine)
                    except Exception:
                        logger.debug("SQLAlchemy tracing init failed", exc_info=True)
                    try:
                        tracing_manager.instrument_requests()
                    except Exception:
                        logger.debug("Requests tracing init failed", exc_info=True)
                    try:
                        tracing_manager.instrument_redis()
                    except Exception:
                        logger.debug("Redis tracing init failed", exc_info=True)
                    try:
                        # FastAPI instrumentation requires app instance
                        tracing_manager.instrument_fastapi(app)
                    except Exception:
                        logger.debug("FastAPI tracing init failed", exc_info=True)
                    logger.info("✅ Distributed tracing initialized")
        except Exception:
            logger.debug("Tracing initialization skipped", exc_info=True)

        # Log startup
        logger.info("🎉 FastAPI application startup completed")
        yield

    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        raise
    finally:
        # Shutdown
        logger.info("🔄 Shutting down Agent Enterprise API Server")
        if os.getenv("SKIP_INFRA_STARTUP", "false").lower() != "true":
            await agent_shutdown_integration()
        await run_blocking(db_manager.close)
        await run_blocking(auth_db_manager.close)
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
        allow_origins=list(api_security_config.cors_origins or []),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.info(f"✅ CORS middleware enabled for origins: {api_security_config.cors_origins}")

    # Add trusted host middleware for production
    cfg = get_config()
    if cfg.is_production():
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=cfg.get_allowed_hosts())
        logger.info("✅ Trusted host middleware enabled")

    # Include API router
    app.include_router(api_router)
    logger.info("✅ API routes included")

    if _PROM:
        # Basic Prometheus metrics (create once per process)
        global _PROMETHEUS_METRICS_CREATED, REQUEST_COUNT, REQUEST_LATENCY
        if not _PROMETHEUS_METRICS_CREATED:
            PROM_REGISTRY = CollectorRegistry()
            REQUEST_COUNT = Counter(
                "http_requests_total", "Total HTTP requests", ["method", "path", "status"], registry=PROM_REGISTRY
            )
            REQUEST_LATENCY = Histogram(
                "http_request_duration_seconds", "Request latency", ["method", "path"], registry=PROM_REGISTRY
            )
            _PROMETHEUS_METRICS_CREATED = True

        def _extract_content_length(headers: Mapping[str, str]) -> Optional[int]:
            try:
                raw_value = headers.get("content-length")
                if raw_value is None:
                    return None
                return int(raw_value)
            except Exception:
                return None

        @app.middleware("http")  # type: ignore[misc]
        async def metrics_middleware(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            start = time.perf_counter()
            response = None
            try:
                response = await call_next(request)
                return response
            finally:
                duration = time.perf_counter() - start
                try:
                    route = getattr(request.scope.get("route"), "path", request.url.path)
                    status_code = response.status_code if response else 500
                    if REQUEST_COUNT is not None:
                        REQUEST_COUNT.labels(request.method, route, str(status_code)).inc()
                    if REQUEST_LATENCY is not None:
                        REQUEST_LATENCY.labels(request.method, route).observe(duration)

                    if monitoring is not None:
                        monitoring.record_request(
                            method=request.method,
                            endpoint=route,
                            status_code=status_code,
                            duration=duration,
                            request_size=_extract_content_length(request.headers),
                            response_size=(
                                _extract_content_length(response.headers)
                                if response is not None
                                else None
                            ),
                        )
                except Exception:
                    logger.debug("Failed to record Prometheus metrics", exc_info=True)

        if cfg.enable_metrics:

            @app.get("/metrics")  # type: ignore[misc]
            async def metrics() -> Response:
                # Use module-level custom registry to avoid default registry duplication across imports
                return Response(generate_latest(PROM_REGISTRY), media_type=CONTENT_TYPE_LATEST)

    # Global exception handler
    @app.exception_handler(HTTPException)  # type: ignore[misc]
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Handle HTTP exceptions with consistent error format."""
        log_api_access(request, status_code=exc.status_code)
        return create_error_response(
            message=exc.detail, error_type="HTTP_EXCEPTION", status_code=exc.status_code
        )

    @app.exception_handler(Exception)  # type: ignore[misc]
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle general exceptions."""
        logger.error(f"Unexpected error: {exc}", exc_info=True)
        log_api_access(request, status_code=500)
        if _PROM and monitoring is not None:
            try:
                monitoring.record_error(error_type=type(exc).__name__, severity="critical")
            except Exception:
                logger.debug("Failed to record error metric", exc_info=True)
        return create_error_response(
            message="Internal server error", error_type="INTERNAL_ERROR", status_code=500
        )

    # Custom OpenAPI schema
    def custom_openapi() -> Dict[str, Any]:
        """Generate custom OpenAPI schema with security schemes."""
        if app.openapi_schema:
            schema: Dict[str, Any] = cast(Dict[str, Any], app.openapi_schema)
            return schema

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

        # Explicitly include important schemas that are used in envelope `data`
        # so they appear in the OpenAPI components for documentation/tests.
        try:
            schemas = openapi_schema.setdefault("components", {}).setdefault("schemas", {})
            # Pydantic models to include explicitly (used inside envelope 'data')
            models_to_include = [
                # Auth
                LoginRequest,
                LoginResponse,
                TokenRefreshRequest,
                TokenData,
                UserInfo,
                UserCreate,
                UserResponse,
                UserUpdate,
                # Agents & Goals
                AgentCreate,
                AgentResponse,
                AgentExecute,
                AgentExecutionResponse,
                GoalCreate,
                GoalResponse,
                # Tokens
                APITokenCreate,
                APITokenResponse,
                # System
                SystemHealth,
                SystemInfo,
                # Base / Misc
                APIResponse,
                APIError,
                ErrorDetail,
                PaginationInfo,
                PaginatedResponse,
                RateLimitInfo,
                SecurityEventResponse,
                BulkOperationRequest,
                BulkOperationResponse,
                WebhookEvent,
                # Capabilities
                AgentCapabilityDescriptor,
                CapabilityRegisterRequest,
                CapabilityRecord,
            ]
            for model in models_to_include:
                name = getattr(model, "__name__", str(model))
                schema_fn = getattr(model, "model_json_schema", None)
                if callable(schema_fn):
                    schemas[name] = schema_fn()

            # Enum types (not Pydantic models)
            enums: list[type[Enum]] = [UserStatus, RoleLevel, SecurityEventType, SecuritySeverity]
            for enum_cls in enums:
                schemas[enum_cls.__name__] = {
                    "title": enum_cls.__name__,
                    "type": "string",
                    "enum": [str(member.value) for member in enum_cls],
                }
        except Exception:
            pass

        app.openapi_schema = openapi_schema
        return cast(Dict[str, Any], app.openapi_schema)

    app.openapi = custom_openapi

    # Root endpoint
    @app.get("/", tags=["System"])  # type: ignore[misc]
    async def root() -> Dict[str, Any]:
        """Root endpoint with API information."""
        return {
            "message": "🚀 Agent Enterprise API",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/api/v1/system/health",
            "admin_providers": "/admin/providers",
        }

    # Health check endpoint (no auth required)
    @app.get("/health", tags=["System"])  # type: ignore[misc]
    async def health_check() -> JSONResponse:
        """Basic health check endpoint with DB, cache, and provider readiness."""
        db_ok = False
        cache_ok = False
        providers = []
        try:
            # DB probe
            async def _probe_db() -> bool:
                from sqlalchemy import text

                def _task() -> bool:
                    with auth_service.db.get_session() as session:
                        session.execute(text("SELECT 1"))
                    return True

                return cast(bool, await run_blocking(_task))

            db_ok = await _probe_db()
        except Exception:
            db_ok = False

        try:
            # Cache/Redis probe
            from .cache_manager import cache_manager

            cache_ok = await cache_manager.is_healthy()
        except Exception:
            cache_ok = False

        hints = []
        try:
            # Providers check and readiness
            providers = unified_config.get_configured_providers()
            order = list(unified_config.api.search_provider_order or ["serpapi", "bing", "google"])
            disabled = list(unified_config.api.disabled_search_providers or [])
            keys_present = {p: bool(get_api_key(p)) for p in ("serpapi", "bing", "google")}
            google_cse_configured = bool(
                (os.getenv("GOOGLE_CSE_ID") or os.getenv("GOOGLE_SEARCH_CX") or "").strip()
            )
            if keys_present.get("google") and not google_cse_configured:
                hints.append("Set GOOGLE_CSE_ID or GOOGLE_SEARCH_CX for Google Custom Search")
            enabled = [p for p in providers if p not in disabled and p in ("serpapi", "bing", "google")]
            if not enabled and not getattr(settings, "TERMINAL_ONLY", False):
                hints.append("Configure SERPAPI_KEY, BING_SEARCH_KEY, or GOOGLE_SEARCH_KEY to enable web search")
        except Exception:
            providers = []
            order = ["serpapi", "bing", "google"]
            disabled = []
            keys_present = {p: False for p in ("serpapi", "bing", "google")}
            google_cse_configured = False

        overall = db_ok and (cache_ok or not cfg.is_production())
        status_code = 200 if overall else 503
        payload = {
            "status": "healthy" if overall else "unhealthy",
            "database": "connected" if db_ok else "disconnected",
            "cache": "connected" if cache_ok else "disconnected",
            "providers": providers,
            "provider_order": order,
            "providers_disabled": disabled,
            "provider_keys_present": keys_present,
            "google_cse_configured": google_cse_configured,
        }
        if not cache_ok and (cfg.is_production() or unified_config.strict_mode):
            hints.append("Configure REDIS_URL and ensure Redis is reachable")
        if hints:
            payload["hints"] = hints
        if status_code != 200 and not cfg.is_production():
            # More permissive in non-production
            payload["status"] = "degraded"
            status_code = 200

        return JSONResponse(status_code=status_code, content=payload)

    # Worker health check endpoints (to replace pgrep probes in Kubernetes)
    @app.get("/health/worker", tags=["System"], response_model=None)  # type: ignore[misc]
    async def worker_health_check() -> Union[Dict[str, Any], JSONResponse]:
        """Worker health check endpoint for Kubernetes probes."""
        try:

            import psutil

            def _collect() -> Tuple[Dict[str, Any], float, float]:
                process_count = len(psutil.pids())
                memory_info = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent(interval=1)
                health_status = {
                    "status": "healthy",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "processes": process_count,
                    "memory_available_gb": round(memory_info.available / (1024**3), 2),
                    "cpu_usage_percent": cpu_percent,
                    "worker_active": True,
                }
                return health_status, memory_info.percent, cpu_percent

            health_status, mem_pct, cpu_percent = await run_blocking(_collect)

            # In production, return unhealthy status if resources are critically low
            if cfg.is_production():
                if mem_pct > 95 or cpu_percent > 95:
                    return JSONResponse(
                        status_code=503,
                        content={
                            **health_status,
                            "status": "unhealthy",
                            "reason": "Resource usage too high",
                        },
                    )

            return health_status

        except Exception as e:
            if cfg.is_production():
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "unhealthy",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "worker_active": False,
                    },
                )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "worker_active": False,
                    "error": str(e),
                },
            )

    @app.get("/health/worker/ready", tags=["System"], response_model=None)  # type: ignore[misc]
    async def worker_readiness_check() -> Union[Dict[str, Any], JSONResponse]:
        """Worker readiness check for Kubernetes readiness probes."""
        try:
            # Check database connectivity
            from sqlalchemy import text

            async def _probe() -> bool:
                def _task() -> bool:
                    with auth_service.db.get_session() as session:
                        session.execute(text("SELECT 1"))
                    return True

                return cast(bool, await run_blocking(_task))

            await _probe()

            # Check if monitoring system is available
            try:
                from .advanced_monitoring import monitoring_system as _ms

                if not _ms.is_initialized:
                    raise Exception("Monitoring system not initialized")
            except Exception:
                pass  # Not critical for readiness

            return {
                "status": "ready",
                "timestamp": datetime.now(UTC).isoformat(),
                "database": "connected",
                "readiness": True,
            }

        except Exception as e:
            if cfg.is_production():
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "not_ready",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "readiness": False,
                    },
                )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "readiness": False,
                    "error": str(e),
                },
            )

    @app.get("/health/worker/live", tags=["System"], response_model=None)  # type: ignore[misc]
    async def worker_liveness_check() -> Union[Dict[str, Any], JSONResponse]:
        """Worker liveness check for Kubernetes liveness probes."""
        try:
            # Simple liveness check - if this endpoint responds, the process is alive
            return {
                "status": "alive",
                "timestamp": datetime.now(UTC).isoformat(),
                "liveness": True,
                "pid": os.getpid(),
            }
        except Exception as e:
            if cfg.is_production():
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "dead",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "liveness": False,
                    },
                )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "dead",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "liveness": False,
                    "error": str(e),
                },
            )

    # API information endpoint
    @app.get("/api/info", tags=["System"])  # type: ignore[misc]
    async def api_info() -> Dict[str, Any]:
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
                    "providers_admin": "GET /admin/providers",
                },
            },
            "authentication": "JWT Bearer tokens or API keys",
            "rate_limit": "100 requests per minute per IP",
        }

    # Admin: provider configuration UI (simple HTML)
    @app.get("/admin/providers", include_in_schema=False)  # type: ignore[misc]
    async def providers_admin_page() -> HTMLResponse:
        html = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Search Providers Admin</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    .row { margin-bottom: 12px; }
    input[type=text], input[type=password] { width: 420px; padding: 6px; }
    button { padding: 6px 12px; margin-left: 6px; }
    code { background: #f2f2f2; padding: 2px 4px; border-radius: 3px; }
    pre { background: #f8f8f8; padding: 10px; border: 1px solid #ddd; max-width: 820px; overflow-x: auto; }
    .hint { color: #555; font-size: 0.9em; }
    .ok { color: #0a0; }
    .err { color: #a00; }
  </style>
</head>
<body>
  <h2>Search Provider Configuration</h2>
  <div class=\"row\">
    <label>JWT Token:</label><br />
    <input id=\"token\" type=\"text\" placeholder=\"Paste Bearer token here (admin/manager required)\" />
    <button onclick=\"loadStatus()\">Load</button>
  </div>
  <div class=\"row\">
    <label>Quick Login (dev):</label><br />
    <input id=\"username\" type=\"text\" placeholder=\"Username (e.g., admin)\" />
    <input id=\"password\" type=\"password\" placeholder=\"Password\" />
    <button onclick=\"loginAndSetToken()\">Login</button>
    <span id=\"loginStatus\" class=\"hint\"></span>
  </div>
  <div class=\"row\">
    <label>Order (comma-separated):</label><br />
    <input id=\"order\" type=\"text\" value=\"serpapi,bing,google\" />
  </div>
  <div class=\"row\">
    <label>Disabled (comma-separated):</label><br />
    <input id=\"disabled\" type=\"text\" placeholder=\"e.g. google\" />
  </div>
  <div class=\"row\">
    <button onclick=\"saveConfig()\">Save</button>
  </div>
  <h3>Current Status</h3>
  <pre id=\"status\">Click Load to fetch status...</pre>
  <script>
    async function loginAndSetToken() {
      const u = document.getElementById('username').value.trim();
      const p = document.getElementById('password').value;
      const statusEl = document.getElementById('loginStatus');
      statusEl.textContent = '';
      try {
        const resp = await fetch('/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: u, password: p, remember_me: false })
        });
        if (!resp.ok) {
          const text = await resp.text();
          statusEl.textContent = ' Login failed';
          statusEl.className = 'hint err';
          return;
        }
        const data = await resp.json();
        const token = (data && data.data && data.data.access_token) ? data.data.access_token : '';
        if (token) {
          document.getElementById('token').value = token;
          statusEl.textContent = ' Logged in';
          statusEl.className = 'hint ok';
        } else {
          statusEl.textContent = ' Invalid response';
          statusEl.className = 'hint err';
        }
      } catch (e) {
        statusEl.textContent = ' ' + (e && e.message ? e.message : 'Login error');
        statusEl.className = 'hint err';
      }
    }

    async function loadStatus() {
      const t = document.getElementById('token').value.trim();
      const headers = t ? { 'Authorization': 'Bearer ' + t } : {};
      const resp = await fetch('/api/v1/system/providers/search-config', { headers });
      const data = await resp.json();
      if (data && data.data) {
        const st = data.data;
        document.getElementById('order').value = (st.order || []).join(',');
        document.getElementById('disabled').value = (st.disabled || []).join(',');
        document.getElementById('status').textContent = JSON.stringify(st, null, 2);
      } else {
        document.getElementById('status').textContent = JSON.stringify(data, null, 2);
      }
    }

    async function saveConfig() {
      const t = document.getElementById('token').value.trim();
      if (!t) { alert('Paste a Bearer token first or use Quick Login'); return; }
      const headers = { 'Authorization': 'Bearer ' + t, 'Content-Type': 'application/json' };
      const order = document.getElementById('order').value.split(',').map(s => s.trim()).filter(Boolean);
      const disabled = document.getElementById('disabled').value.split(',').map(s => s.trim()).filter(Boolean);
      const payload = { order, disabled };
      const resp = await fetch('/api/v1/system/providers/search-config', { method: 'PUT', headers, body: JSON.stringify(payload) });
      const data = await resp.json();
      document.getElementById('status').textContent = JSON.stringify(data, null, 2);
    }
  </script>
</body>
</html>
        """
        return HTMLResponse(html)

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
    target = None
    if args.reload:
        import importlib.util as _importlib_util

        for _mod in ("agent_system.fastapi_app", "src.agent_system.fastapi_app"):
            if _importlib_util.find_spec(_mod) is not None:
                target = f"{_mod}:app"
                break
    if target:
        uvicorn.run(
            target,
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers if not args.reload else 1,
            log_level="info",
        )
    else:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=False,
            workers=args.workers,
            log_level="info",
        )
