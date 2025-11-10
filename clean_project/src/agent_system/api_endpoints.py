"""
FastAPI Authentication & Agent Operation Endpoints
Production-ready API with comprehensive OpenAPI documentation
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, AsyncIterator, Callable, Optional, ParamSpec, TypeVar, cast

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import text

# Import auth models to register them with SQLAlchemy
from . import auth_models  # noqa: F401
from .advanced_monitoring import monitoring_system

# Import comprehensive API schemas for OpenAPI documentation
from .api_schemas import (
    # Capabilities
    AgentCreate,
    APIError,
    # Base responses
    APIResponse,
    # API Tokens
    APITokenCreate,
    CapabilityRegisterRequest,
    GoalCreate,
    LoginRequest,
    LoginResponse,
    TokenData,
    TokenRefreshRequest,
    # User Management
    UserCreate,
    UserInfo,
)
from .api_security import (
    check_custom_rate_limit,
    create_api_response,
    create_error_response,
    get_current_security_context,
    require_permission,
)
from .async_utils import run_blocking
from .auth_models import (
    AccountLockedError,
    APITokenModel,
    AuthenticationError,
    InvalidCredentialsError,
    SecurityContext,
    UserModel,
    UserNotFoundError,
)
from .auth_service import auth_service
from .config_simple import settings
from .database_models import (
    ActionModel,
    AgentCapabilityModel,
    AgentModel,
    GoalModel,
)
from .database_models import (
    db_manager as app_db_manager,
)
from .distributed_message_queue import MessagePriority, distributed_message_queue
from .job_definitions import (
    AGENT_JOB_QUEUE,
    AgentExecutionPayload,
    JobPriority,
    JobQueueMessage,
    JobType,
)
from .job_manager import job_store
from .production_config import get_config

logger = logging.getLogger(__name__)

# Create main API router with comprehensive tags
api_router = APIRouter(
    prefix="/api/v1",
    tags=[
        "Authentication",
        "User Management",
        "Agent Operations",
        "Goal Management",
        "API Tokens",
        "System",
        "Capabilities",
    ],
)

# API envelope alias for backward compatibility
APIEnvelope = APIResponse

# Typed decorator wrappers to satisfy mypy for FastAPI route decorators
P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


def _typed_route(
    decorator_factory: Callable[..., Callable[[Callable[P, R]], Callable[..., Any]]],
) -> Callable[..., Callable[[Callable[P, R]], Callable[P, R]]]:
    def wrapper(*args: Any, **kwargs: Any) -> Callable[[Callable[P, R]], Callable[P, R]]:
        def inner(func: Callable[P, R]) -> Callable[P, R]:
            # FastAPI returns the function after registering the route; cast restores the original type
            return cast(Callable[P, R], decorator_factory(*args, **kwargs)(func))

        return inner

    return wrapper


class TypedRouter:
    def __init__(self, router: APIRouter) -> None:
        self._router = router
        self.get = _typed_route(router.get)
        self.post = _typed_route(router.post)
        self.put = _typed_route(router.put)
        self.delete = _typed_route(router.delete)
        self.patch = _typed_route(router.patch)


# Use typed wrappers for route decorators to avoid decorator-level ignores
typed_router = TypedRouter(api_router)


async def _with_app_session(func: Callable[[Any], T]) -> T:
    """Execute database work for the app DB in a threadpool."""

    def _run() -> T:
        with app_db_manager.get_session() as session:
            return func(session)

    return await run_blocking(_run)


async def _with_auth_session(func: Callable[[Any], T]) -> T:
    """Execute database work for the auth DB in a threadpool."""

    def _run() -> T:
        with auth_service.db.get_session() as session:
            return func(session)

    return await run_blocking(_run)


JOB_PRIORITY_TO_MESSAGE = {
    JobPriority.CRITICAL: MessagePriority.CRITICAL,
    JobPriority.HIGH: MessagePriority.HIGH,
    JobPriority.NORMAL: MessagePriority.NORMAL,
    JobPriority.LOW: MessagePriority.LOW,
}


async def _enqueue_job(
    job_id: str, *, job_type: JobType, priority: JobPriority = JobPriority.NORMAL
) -> None:
    """Publish a job message to the distributed queue."""
    await distributed_message_queue.initialize()
    message = JobQueueMessage(job_id=job_id, job_type=job_type, priority=priority)
    await distributed_message_queue.publish(
        AGENT_JOB_QUEUE,
        message.model_dump(),
        priority=JOB_PRIORITY_TO_MESSAGE.get(priority, MessagePriority.NORMAL),
        headers={"job_type": job_type.value},
    )


# Authentication Endpoints
@typed_router.post(
    "/auth/login",
    response_model=APIResponse,
    summary="User Authentication",
    description="""
    Authenticate user and receive JWT access/refresh tokens.

    **Authentication Flow:**
    1. Provide valid username/email and password
    2. Receive access_token (30 min expiry) and refresh_token (30 day expiry)
    3. Use access_token in Authorization header for API calls
    4. Use refresh_token to get new access_token when expired

    **Rate Limiting:** 5 login attempts per 15 minutes per IP

    **Security Notes:**
    - Account locks after 5 failed attempts for 30 minutes
    - Tokens are cryptographically signed and tamper-proof
    - Session is logged for security audit
    """,
    responses={
        200: {
            "model": APIResponse,
            "description": "Successful authentication",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "User authenticated successfully",
                        "timestamp": 1640995200.0,
                        "data": {
                            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                            "token_type": "bearer",
                            "expires_in": 1800,
                            "user": {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "username": "admin",
                                "email": "admin@example.com",
                                "full_name": "System Administrator",
                                "is_active": True,
                                "is_admin": True,
                                "roles": ["admin"],
                                "permissions": ["system.admin", "agent.read", "agent.write"],
                                "last_login": "2023-12-31T23:59:59Z",
                                "created_at": "2023-01-01T00:00:00Z",
                            },
                        },
                    }
                }
            },
        },
        401: {
            "model": APIError,
            "description": "Invalid credentials, account locked, or inactive account",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_credentials": {
                            "summary": "Invalid username or password",
                            "value": {
                                "success": False,
                                "error": "INVALID_CREDENTIALS",
                                "message": "Invalid username or password",
                                "timestamp": 1640995200.0,
                            },
                        },
                        "account_locked": {
                            "summary": "Account temporarily locked",
                            "value": {
                                "success": False,
                                "error": "ACCOUNT_LOCKED",
                                "message": "Account is temporarily locked due to multiple failed attempts",
                                "timestamp": 1640995200.0,
                            },
                        },
                        "inactive_account": {
                            "summary": "Account not active",
                            "value": {
                                "success": False,
                                "error": "ACCOUNT_INACTIVE",
                                "message": "Account is not active",
                                "timestamp": 1640995200.0,
                            },
                        },
                    }
                }
            },
        },
    },
)
async def login(request: Request, login_data: LoginRequest) -> JSONResponse:
    """
    Authenticate user and return JWT tokens with comprehensive user information.

    This endpoint validates user credentials and returns:
    - **access_token**: JWT token for API authentication (30 min expiry)
    - **refresh_token**: Token to get new access tokens (30 day expiry)
    - **user**: Complete user profile with roles and permissions

    **Example Usage:**
    ```bash
    curl -X POST http://localhost:8000/api/v1/auth/login \\
      -H "Content-Type: application/json" \\
      -d '{
        "username": "admin",
        "password": "admin123",
        "remember_me": false
      }'
    ```
    """
    try:
        cfg = get_config()
        if cfg.is_production():
            ip = request.client.host if request.client else "unknown"
            if await check_custom_rate_limit("login", f"{ip}:{login_data.username}", 5, 900):
                return create_error_response(
                    message="Too many login attempts. Please try again later.",
                    error_type="RATE_LIMIT_EXCEEDED",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )
        # Authenticate user with IP and user agent tracking
        security_context = await auth_service.authenticate_user_async(
            login_data.username,
            login_data.password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        # Create user session with tracking
        tokens = await auth_service.create_user_session_async(
            security_context.user.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        # Build comprehensive user info using UserInfo schema
        user_info = UserInfo(
            id=security_context.user.id,
            username=security_context.user.username,
            email=security_context.user.email,
            full_name=security_context.user.full_name,
            is_active=security_context.user.is_active,
            is_admin=security_context.is_admin,
            roles=[role.name for role in security_context.user.roles],
            permissions=security_context.permissions,
            last_login=security_context.user.last_login,
            created_at=security_context.user.created_at,
        )

        # Build login response
        login_response = LoginResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=tokens["expires_in"],
            user=user_info,
        )

        logger.info(
            f"✅ User {security_context.user.username} logged in successfully from {request.client.host}"
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": "User authenticated successfully",
                "timestamp": datetime.now(UTC).timestamp(),
                "data": login_response.model_dump(mode="json"),
            },
        )

    except (UserNotFoundError, InvalidCredentialsError) as e:
        logger.warning(f"🔒 Login failed for {login_data.username}: {str(e)}")
        return create_error_response(
            message="Invalid username or password",
            error_type="INVALID_CREDENTIALS",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    except AccountLockedError as e:
        logger.warning(f"🔒 Account locked for {login_data.username}: {str(e)}")
        return create_error_response(
            message=str(e), error_type="ACCOUNT_LOCKED", status_code=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logger.error(f"💥 Login error for {login_data.username}: {str(e)}")
        return create_error_response(
            message="Authentication service temporarily unavailable",
            error_type="AUTH_SERVICE_ERROR",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@typed_router.post(
    "/auth/refresh",
    response_model=APIResponse,
    summary="Refresh Access Token",
    description="""
    Exchange a valid refresh token for a new access token.

    **Token Lifecycle:**
    1. Access tokens expire after 30 minutes
    2. Refresh tokens expire after 30 days
    3. Use this endpoint to get new access tokens without re-authenticating

    **Security Notes:**
    - Refresh tokens are single-use
    - New refresh token provided with new access token
    - Invalid refresh tokens are logged for security audit
    """,
    responses={
        200: {
            "model": APIResponse,
            "description": "Token refreshed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Token refreshed successfully",
                        "timestamp": 1640995200.0,
                        "data": {
                            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                            "token_type": "bearer",
                            "expires_in": 1800,
                        },
                    }
                }
            },
        },
        401: {"model": APIError, "description": "Invalid, expired, or revoked refresh token"},
    },
)
async def refresh_token(request: Request, refresh_data: TokenRefreshRequest) -> JSONResponse:
    """
    Refresh access token using a valid refresh token.

    **Example Usage:**
    ```bash
    curl -X POST http://localhost:8000/api/v1/auth/refresh \\
      -H "Content-Type: application/json" \\
      -d '{
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
      }'
    ```
    """
    try:
        tokens = await auth_service.refresh_access_token_async(refresh_data.refresh_token)

        # Build token data response
        token_data = TokenData(
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token", refresh_data.refresh_token),
            token_type=tokens.get("token_type", "bearer"),
            expires_in=tokens.get("expires_in", 1800),
        )

        logger.info("🔄 Access token refreshed successfully")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": "Token refreshed successfully",
                "timestamp": datetime.now(UTC).timestamp(),
                "data": token_data.model_dump(),
            },
        )

    except AuthenticationError as e:
        logger.warning(f"🔒 Token refresh failed: {str(e)}")
        return create_error_response(
            message="Invalid or expired refresh token",
            error_type="INVALID_REFRESH_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    except Exception as e:
        logger.error(f"💥 Token refresh error: {str(e)}")
        return create_error_response(
            message="Token refresh service temporarily unavailable",
            error_type="REFRESH_SERVICE_ERROR",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@typed_router.post("/auth/logout", response_model=APIEnvelope)
async def logout(
    request: Request, security_context: SecurityContext = Depends(get_current_security_context)
) -> JSONResponse:
    """Logout user and invalidate session."""
    try:
        await auth_service.logout_async(security_context.user.id, security_context.session_id)

        logger.info(f"User {security_context.user.username} logged out successfully")

        return create_api_response(message="Logged out successfully")

    except Exception as e:
        logger.error(f"Logout failed for user {security_context.user.username}: {str(e)}")
        return create_error_response(message="Logout failed", error_type="LOGOUT_FAILED")


@typed_router.get("/auth/me", response_model=APIEnvelope)
async def get_current_user_info(
    security_context: SecurityContext = Depends(get_current_security_context),
) -> JSONResponse:
    """Get current user information."""
    try:
        user_data = {
            "id": security_context.user.id,
            "username": security_context.user.username,
            "email": security_context.user.email,
            "full_name": security_context.user.full_name,
            "is_active": security_context.user.is_active,
            "roles": [role.name for role in security_context.user.roles],
            "permissions": security_context.permissions,
            "is_admin": security_context.is_admin,
            "last_login": (
                security_context.user.last_login.isoformat()
                if security_context.user.last_login
                else None
            ),
            "created_at": security_context.user.created_at.isoformat(),
        }

        return create_api_response(
            data=user_data, message="User information retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Failed to get user info: {str(e)}")
        return create_error_response(
            message="Failed to retrieve user information", error_type="USER_INFO_FAILED"
        )


# User Management Endpoints
@typed_router.post("/users", response_model=APIResponse)
async def create_user(
    user_data: UserCreate,
    security_context: SecurityContext = Depends(require_permission("users", "write")),
) -> JSONResponse:
    """Create new user account (requires users.write permission)."""
    try:
        user = await auth_service.create_user_async(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role_names=user_data.role_names,
        )

        response_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "roles": [role.name for role in user.roles],
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }

        return create_api_response(
            data=response_data,
            message="User created successfully",
            status_code=status.HTTP_201_CREATED,
        )

    except ValueError as e:
        return create_error_response(
            message=str(e), error_type="VALIDATION_ERROR", status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"User creation failed: {str(e)}")
        return create_error_response(
            message="Failed to create user", error_type="USER_CREATION_FAILED"
        )


@typed_router.get("/users", response_model=APIEnvelope)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    security_context: SecurityContext = Depends(require_permission("users", "read")),
) -> JSONResponse:
    """List users (requires users.read permission)."""
    try:

        def _query(session):
            records = session.query(UserModel).offset(skip).limit(limit).all()
            result = []
            for user in records:
                result.append(
                    {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "full_name": user.full_name,
                        "is_active": user.is_active,
                        "roles": [role.name for role in user.roles],
                        "created_at": user.created_at.isoformat(),
                        "last_login": user.last_login.isoformat() if user.last_login else None,
                    }
                )
            return result

        user_list = await _with_auth_session(_query)
        return create_api_response(data=user_list, message="Users retrieved successfully")

    except Exception as e:
        logger.error(f"Failed to list users: {str(e)}")
        return create_error_response(
            message="Failed to retrieve users", error_type="USER_LIST_FAILED"
        )


# API Token Management
@typed_router.post("/api-tokens", response_model=APIResponse)
async def create_api_token(
    token_data: APITokenCreate,
    security_context: SecurityContext = Depends(get_current_security_context),
) -> JSONResponse:
    """Create API token for current user."""
    try:
        api_token = await auth_service.create_api_token_async(
            security_context.user.id,
            token_data.name,
            token_data.scopes,
            token_data.expires_days,
        )

        return create_api_response(
            data={
                "token": api_token,
                "prefix": api_token[:8],
                "name": token_data.name,
                "scopes": token_data.scopes,
            },
            message="API token created successfully",
            status_code=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error(f"API token creation failed: {str(e)}")
        return create_error_response(
            message="Failed to create API token", error_type="TOKEN_CREATION_FAILED"
        )


@typed_router.get("/api-tokens", response_model=APIEnvelope)
async def list_api_tokens(
    security_context: SecurityContext = Depends(get_current_security_context),
) -> JSONResponse:
    """List user's API tokens."""
    try:

        def _query(session):
            records = (
                session.query(APITokenModel)
                .filter(APITokenModel.user_id == security_context.user.id)
                .all()
            )
            token_data = []
            for token in records:
                token_data.append(
                    {
                        "id": token.id,
                        "name": token.name,
                        "token_prefix": token.token_prefix,
                        "scopes": token.scopes,
                        "created_at": token.created_at.isoformat(),
                        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                        "last_used": token.last_used.isoformat() if token.last_used else None,
                        "usage_count": token.usage_count,
                    }
                )
            return token_data

        token_list = await _with_auth_session(_query)

        return create_api_response(data=token_list, message="API tokens retrieved successfully")

    except Exception as e:
        logger.error(f"Failed to list API tokens: {str(e)}")
        return create_error_response(
            message="Failed to retrieve API tokens", error_type="TOKEN_LIST_FAILED"
        )


# Agent Operation Endpoints
@typed_router.post("/agents", response_model=APIResponse)
async def create_agent(
    agent_data: AgentCreate,
    security_context: SecurityContext = Depends(require_permission("agent", "write")),
) -> JSONResponse:
    """Create new agent (requires agent.write permission)."""
    try:
        agent = AgentModel(
            name=agent_data.name,
            description=agent_data.description,
            goals=agent_data.goals,
            memory_capacity=agent_data.memory_capacity,
            created_by=security_context.user.id,
        )

        async def _persist():
            def _op(session):
                session.add(agent)
                session.commit()
                session.refresh(agent)
                return agent

            return await _with_app_session(_op)

        agent = await _persist()

        agent_response = {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "status": agent.status,
            "goals": agent.goals,
            "memory_usage": len(agent.memory) if agent.memory else 0,
            "created_at": agent.created_at.isoformat(),
            "updated_at": agent.updated_at.isoformat(),
        }

        logger.info(f"Agent {agent.name} created by {security_context.user.username}")

        return create_api_response(
            data=agent_response,
            message="Agent created successfully",
            status_code=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error(f"Agent creation failed: {str(e)}")
        return create_error_response(
            message="Failed to create agent", error_type="AGENT_CREATION_FAILED"
        )


@typed_router.get("/agents", response_model=APIEnvelope)
async def list_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    security_context: SecurityContext = Depends(require_permission("agent", "read")),
) -> JSONResponse:
    """List agents (requires agent.read permission)."""
    try:

        def _query(session):
            records = session.query(AgentModel).offset(skip).limit(limit).all()
            agent_list = []
            for agent in records:
                agent_list.append(
                    {
                        "id": agent.id,
                        "name": agent.name,
                        "description": agent.description,
                        "status": agent.status,
                        "goals": agent.goals,
                        "memory_usage": len(agent.memory) if agent.memory else 0,
                        "created_at": agent.created_at.isoformat(),
                        "updated_at": agent.updated_at.isoformat(),
                    }
                )
            return agent_list

        agent_list = await _with_app_session(_query)

        return create_api_response(data=agent_list, message="Agents retrieved successfully")

    except Exception as e:
        logger.error(f"Failed to list agents: {str(e)}")
        return create_error_response(
            message="Failed to retrieve agents", error_type="AGENT_LIST_FAILED"
        )


@typed_router.get("/agents/{agent_id}", response_model=APIEnvelope)
async def get_agent(
    agent_id: str, security_context: SecurityContext = Depends(require_permission("agent", "read"))
) -> JSONResponse:
    """Get specific agent details (requires agent.read permission)."""
    try:

        def _query(session):
            return session.query(AgentModel).filter(AgentModel.id == agent_id).first()

        agent = await _with_app_session(_query)
        if not agent:
            return create_error_response(
                message="Agent not found",
                error_type="AGENT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        agent_data = {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "status": agent.status,
            "goals": agent.goals,
            "memory": agent.memory,
            "memory_usage": len(agent.memory) if agent.memory else 0,
            "created_at": agent.created_at.isoformat(),
            "updated_at": agent.updated_at.isoformat(),
        }

        return create_api_response(data=agent_data, message="Agent details retrieved successfully")

    except Exception as e:
        logger.error(f"Failed to get agent {agent_id}: {str(e)}")
        return create_error_response(
            message="Failed to retrieve agent details", error_type="AGENT_GET_FAILED"
        )


@typed_router.post("/agents/{agent_id}/execute")
async def execute_agent(
    agent_id: str,
    security_context: SecurityContext = Depends(require_permission("agent", "execute")),
) -> JSONResponse:
    """Execute agent operations (requires agent.execute permission)."""
    try:

        def _create_action(session):
            record = session.query(AgentModel).filter(AgentModel.id == agent_id).first()
            if not record:
                return None, None
            action = ActionModel(
                action_id=str(uuid.uuid4()),
                agent_id=agent_id,
                action_type="manual_execution",
                description=f"Agent execution requested by {security_context.user.username}",
                user_id=security_context.user.id,
                status="queued",
            )
            session.add(action)
            session.commit()
            session.refresh(action)
            return record, action

        agent, action = await _with_app_session(_create_action)
        if not agent:
            return create_error_response(
                message="Agent not found",
                error_type="AGENT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        payload = AgentExecutionPayload(
            agent_id=agent_id,
            max_cycles=getattr(settings, "MAX_CYCLES", 100),
            max_concurrent_goals=getattr(settings, "MAX_CONCURRENT_GOALS", 1),
            requested_by=security_context.user.username,
            tenant_id=getattr(security_context.user, "tenant_id", None),
            metadata={"action_id": action.id},
        )

        job_record = await job_store.create_job(
            job_type=JobType.AGENT_EXECUTION,
            priority=JobPriority.HIGH,
            queue_name=AGENT_JOB_QUEUE,
            payload=payload.model_dump(),
            requested_by=security_context.user.username,
            tenant_id=getattr(security_context.user, "tenant_id", None),
            agent_id=agent_id,
        )

        try:
            await _enqueue_job(
                job_record["id"],
                job_type=JobType.AGENT_EXECUTION,
                priority=JobPriority.HIGH,
            )
        except Exception as queue_error:
            logger.error("Failed to enqueue job %s: %s", job_record["id"], queue_error)
            await job_store.mark_job_failed(job_record["id"], error=str(queue_error))
            return create_error_response(
                message="Failed to enqueue agent job",
                error_type="AGENT_JOB_ENQUEUE_FAILED",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info(
            "Queued agent execution job %s for %s by %s",
            job_record["id"],
            agent.name,
            security_context.user.username,
        )

        return create_api_response(
            data={
                "job_id": job_record["id"],
                "agent_id": agent_id,
                "status": job_record["status"],
                "queue": job_record["queue_name"],
                "priority": job_record["priority"],
            },
            message="Agent execution queued",
            status_code=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Agent execution failed for {agent_id}: {str(e)}")
        return create_error_response(
            message="Failed to execute agent", error_type="AGENT_EXECUTION_FAILED"
        )


# Job Management Endpoints
@typed_router.get("/jobs/{job_id}", response_model=APIEnvelope)
async def get_job_status(
    job_id: str,
    security_context: SecurityContext = Depends(require_permission("agent", "read")),
) -> JSONResponse:
    """Retrieve background job status."""
    job = await job_store.get_job(job_id)
    if not job:
        return create_error_response(
            message="Job not found",
            error_type="JOB_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return create_api_response(data=job, message="Job status retrieved")


@typed_router.get("/agents/{agent_id}/jobs", response_model=APIEnvelope)
async def list_agent_jobs(
    agent_id: str,
    limit: int = Query(20, ge=1, le=100),
    security_context: SecurityContext = Depends(require_permission("agent", "read")),
) -> JSONResponse:
    """List recent jobs for an agent."""
    jobs = await job_store.list_jobs(agent_id=agent_id, limit=limit)
    return create_api_response(data=jobs, message="Agent jobs retrieved")


# Job status streaming (SSE)
@typed_router.get("/jobs/{job_id}/stream")
async def stream_job_status(
    job_id: str,
    security_context: SecurityContext = Depends(require_permission("agent", "read")),
) -> StreamingResponse:
    """Stream job status updates via Server-Sent Events."""

    async def event_gen() -> AsyncIterator[str]:
        import asyncio
        import json

        deadline = asyncio.get_event_loop().time() + 300  # 5 minutes
        last_payload = None
        while asyncio.get_event_loop().time() < deadline:
            job = await job_store.get_job(job_id)
            if job is None:
                yield "event: error\n" + f"data: {json.dumps({'error': 'JOB_NOT_FOUND'})}\n\n"
                break
            payload = {
                "id": job.get("id"),
                "status": job.get("status"),
                "result": job.get("result", {}),
                "error": job.get("error"),
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
            }
            if payload != last_payload:
                yield "data: " + json.dumps(payload) + "\n\n"
                last_payload = payload
            if job.get("status") in {"succeeded", "failed"}:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# Capability discovery (ADR-002)
@typed_router.get("/agents/capabilities", response_model=APIEnvelope)
async def list_capabilities(
    role: Optional[str] = Query(None),
    security_context: SecurityContext = Depends(require_permission("agent", "read")),
) -> JSONResponse:
    try:

        def _query(session):
            query = session.query(AgentCapabilityModel)
            if role:
                query = query.filter(AgentCapabilityModel.role == role)
            records = query.order_by(AgentCapabilityModel.updated_at.desc()).limit(200).all()
            items = []
            for r in records:
                items.append(
                    {
                        "id": r.id,
                        "instance_id": r.instance_id,
                        "agent_name": r.agent_name,
                        "role": r.role,
                        "capabilities": r.capabilities or [],
                        "expertise_domains": r.expertise_domains or [],
                        "capacity": r.capacity,
                        "tool_scopes": r.tool_scopes or [],
                        "metadata": r.capability_metadata or {},
                        "heartbeat_at": r.heartbeat_at.isoformat() if r.heartbeat_at else None,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                    }
                )
            return items

        items = await _with_app_session(_query)
        return create_api_response(data=items, message="Capabilities retrieved")
    except Exception as e:
        logger.error(f"Failed to list capabilities: {e}")
        return create_error_response(
            message="Failed to retrieve capabilities", error_type="CAPABILITY_LIST_FAILED"
        )


@typed_router.post("/agents/capabilities/register", response_model=APIEnvelope)
async def register_capability(
    spec: CapabilityRegisterRequest,
    security_context: SecurityContext = Depends(require_permission("agent", "write")),
) -> JSONResponse:
    try:

        def _upsert(session):
            existing = (
                session.query(AgentCapabilityModel)
                .filter(AgentCapabilityModel.instance_id == spec.instance_id)
                .first()
            )
            if existing:
                existing.agent_name = spec.agent_name
                existing.role = spec.role
                existing.capabilities = [c.model_dump() for c in spec.capabilities]
                existing.expertise_domains = spec.expertise_domains
                existing.capacity = spec.capacity
                existing.tool_scopes = spec.tool_scopes
                existing.capability_metadata = spec.metadata
                existing.heartbeat_at = datetime.now(UTC)
                session.add(existing)
            else:
                rec = AgentCapabilityModel(
                    instance_id=spec.instance_id,
                    agent_name=spec.agent_name,
                    role=spec.role,
                    capabilities=[c.model_dump() for c in spec.capabilities],
                    expertise_domains=spec.expertise_domains,
                    capacity=spec.capacity,
                    tool_scopes=spec.tool_scopes,
                    capability_metadata=spec.metadata,
                )
                session.add(rec)
            session.commit()
            return True

        await _with_app_session(_upsert)
        return create_api_response(message="Capability registered", data=True)
    except Exception as e:
        logger.error(f"Capability registration failed: {e}")
        return create_error_response(
            message="Capability registration failed", error_type="CAPABILITY_REGISTER_FAILED"
        )


# Goal Management Endpoints
@typed_router.post("/goals", response_model=APIResponse)
async def create_goal(
    goal_data: GoalCreate,
    security_context: SecurityContext = Depends(require_permission("goals", "write")),
) -> JSONResponse:
    """Create new goal (requires goals.write permission)."""
    try:
        goal = GoalModel(
            title=goal_data.title,
            description=goal_data.description,
            priority=goal_data.priority,
            target_date=goal_data.target_date,
            created_by=security_context.user.id,
        )

        def _persist(session):
            session.add(goal)
            session.commit()
            session.refresh(goal)
            return goal

        goal = await _with_app_session(_persist)

        goal_response = {
            "id": goal.id,
            "title": goal.title,
            "description": goal.description,
            "status": goal.status,
            "priority": goal.priority,
            "progress": goal.progress,
            "created_at": goal.created_at.isoformat(),
            "target_date": goal.target_date.isoformat() if goal.target_date else None,
        }

        logger.info(f"Goal '{goal.title}' created by {security_context.user.username}")

        return create_api_response(
            data=goal_response,
            message="Goal created successfully",
            status_code=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error(f"Goal creation failed: {str(e)}")
        return create_error_response(
            message="Failed to create goal", error_type="GOAL_CREATION_FAILED"
        )


@typed_router.get("/goals", response_model=APIEnvelope)
async def list_goals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    security_context: SecurityContext = Depends(require_permission("goals", "read")),
) -> JSONResponse:
    """List goals (requires goals.read permission)."""
    try:

        def _query(session):
            records = session.query(GoalModel).offset(skip).limit(limit).all()
            goal_list = []
            for goal in records:
                goal_list.append(
                    {
                        "id": goal.id,
                        "title": goal.title,
                        "description": goal.description,
                        "status": goal.status,
                        "priority": goal.priority,
                        "progress": goal.progress,
                        "created_at": goal.created_at.isoformat(),
                        "target_date": goal.target_date.isoformat() if goal.target_date else None,
                    }
                )
            return goal_list

        goal_list = await _with_app_session(_query)

        return create_api_response(data=goal_list, message="Goals retrieved successfully")

    except Exception as e:
        logger.error(f"Failed to list goals: {str(e)}")
        return create_error_response(
            message="Failed to retrieve goals", error_type="GOAL_LIST_FAILED"
        )


# System Information Endpoints
@typed_router.get("/system/health")
async def system_health() -> JSONResponse:
    """System health check endpoint."""

    async def _probe_db(session_factory: Callable[[], Any]) -> bool:
        try:

            def _task():
                with session_factory() as session:
                    session.execute(text("SELECT 1"))
                return True

            return await run_blocking(_task)
        except Exception as exc:  # pragma: no cover - diagnostics
            logger.error("Database probe failed: %s", exc)
            return False

    auth_db_ok, app_db_ok = await asyncio.gather(
        _probe_db(auth_service.db.get_session), _probe_db(app_db_manager.get_session)
    )
    overall_ok = auth_db_ok and app_db_ok

    health_data = {
        "status": "healthy" if overall_ok else "degraded",
        "databases": {
            "auth": "connected" if auth_db_ok else "error",
            "application": "connected" if app_db_ok else "error",
        },
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "1.0.0",
    }

    if overall_ok:
        return create_api_response(data=health_data, message="System is healthy")

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "success": False,
            "error": "HEALTH_CHECK_FAILED",
            "message": "System health check failed",
            "timestamp": datetime.now(UTC).timestamp(),
            "data": health_data,
        },
    )


@typed_router.get("/system/info")
async def system_info(
    security_context: SecurityContext = Depends(require_permission("system", "read"))
) -> JSONResponse:
    """Get system information (requires system.read permission)."""
    try:
        user_count = await _with_auth_session(lambda session: session.query(UserModel).count())

        def _counts(session):
            return (
                session.query(AgentModel).count(),
                session.query(GoalModel).count(),
                session.query(ActionModel).count(),
            )

        agent_count, goal_count, action_count = await _with_app_session(_counts)

        system_data = {
            "users": user_count,
            "agents": agent_count,
            "goals": goal_count,
            "actions": action_count,
            "uptime": "running",
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return create_api_response(
            data=system_data, message="System information retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Failed to get system info: {str(e)}")
        cfg = get_config()
        if cfg.is_production():
            return create_error_response(
                message="Failed to retrieve system information",
                error_type="SYSTEM_INFO_FAILED",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        system_data = {
            "users": 0,
            "agents": 0,
            "goals": 0,
            "actions": 0,
            "uptime": "unknown",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        return create_api_response(
            data=system_data, message="System information degraded due to backend error"
        )


@typed_router.post(
    "/system/alerts/webhook",
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
async def alertmanager_webhook(request: Request) -> JSONResponse:
    """Receive Alertmanager notifications and mirror them into local metrics/logs."""
    expected_token = getattr(settings, "ALERTMANAGER_WEBHOOK_TOKEN", None)
    provided_token = request.headers.get("X-Alertmanager-Token")

    if expected_token and provided_token != expected_token:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "error": "INVALID_WEBHOOK_TOKEN"},
        )

    try:
        payload = await request.json()
    except Exception as exc:
        logger.error(f"Invalid Alertmanager payload: {exc}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "INVALID_PAYLOAD"},
        )

    alerts = payload.get("alerts", []) if isinstance(payload, dict) else []
    processed = 0

    for alert in alerts:
        labels = alert.get("labels", {}) if isinstance(alert, dict) else {}
        severity = labels.get("severity", "info")
        source = labels.get("alertname", "unknown")
        monitoring_system.record_alert_event(severity, source)
        processed += 1

    logger.info("Alertmanager webhook received %s alerts", processed)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"success": True, "alerts_processed": processed},
    )
