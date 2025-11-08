"""
FastAPI Authentication & Agent Operation Endpoints
Production-ready API with comprehensive OpenAPI documentation
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

# Import auth models to register them with SQLAlchemy
from . import auth_models  # noqa: F401

# Import comprehensive API schemas for OpenAPI documentation
from .api_schemas import (
    # Agent Management
    AgentCreate,
    APIError,
    # Base responses
    APIResponse,
    # API Tokens
    APITokenCreate,
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
    create_api_response,
    create_error_response,
    get_current_security_context,
    require_permission,
    check_custom_rate_limit,
)
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
from .database_models import ActionModel, AgentModel, GoalModel
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
    ],
)

# API envelope alias for backward compatibility
APIEnvelope = APIResponse


# Authentication Endpoints
@api_router.post(
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
async def login(request: Request, login_data: LoginRequest):
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
            if check_custom_rate_limit("login", f"{ip}:{login_data.username}", 5, 900):
                return create_error_response(
                    message="Too many login attempts. Please try again later.",
                    error_type="RATE_LIMIT_EXCEEDED",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )
        # Authenticate user with IP and user agent tracking
        security_context = auth_service.authenticate_user(
            login_data.username,
            login_data.password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        # Create user session with tracking
        tokens = auth_service.create_user_session(
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


@api_router.post(
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
async def refresh_token(request: Request, refresh_data: TokenRefreshRequest):
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
        tokens = auth_service.refresh_access_token(refresh_data.refresh_token)

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
                "data": token_data.dict(),
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


@api_router.post("/auth/logout", response_model=APIEnvelope)
async def logout(
    request: Request, security_context: SecurityContext = Depends(get_current_security_context)
):
    """Logout user and invalidate session."""
    try:
        auth_service.logout(security_context.user.id, security_context.session_id)

        logger.info(f"User {security_context.user.username} logged out successfully")

        return create_api_response(message="Logged out successfully")

    except Exception as e:
        logger.error(f"Logout failed for user {security_context.user.username}: {str(e)}")
        return create_error_response(message="Logout failed", error_type="LOGOUT_FAILED")


@api_router.get("/auth/me", response_model=APIEnvelope)
async def get_current_user_info(
    security_context: SecurityContext = Depends(get_current_security_context),
):
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
@api_router.post("/users", response_model=APIResponse)
async def create_user(
    user_data: UserCreate,
    security_context: SecurityContext = Depends(require_permission("users", "write")),
):
    """Create new user account (requires users.write permission)."""
    try:
        user = auth_service.create_user(
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


@api_router.get("/users", response_model=APIEnvelope)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    security_context: SecurityContext = Depends(require_permission("users", "read")),
):
    """List users (requires users.read permission)."""
    try:
        with auth_service.db.get_session() as session:
            users = session.query(UserModel).offset(skip).limit(limit).all()

            user_list = []
            for user in users:
                user_data = {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_active": user.is_active,
                    "roles": [role.name for role in user.roles],
                    "created_at": user.created_at.isoformat(),
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                }
                user_list.append(user_data)

            return create_api_response(data=user_list, message="Users retrieved successfully")

    except Exception as e:
        logger.error(f"Failed to list users: {str(e)}")
        return create_error_response(
            message="Failed to retrieve users", error_type="USER_LIST_FAILED"
        )


# API Token Management
@api_router.post("/api-tokens", response_model=APIResponse)
async def create_api_token(
    token_data: APITokenCreate,
    security_context: SecurityContext = Depends(get_current_security_context),
):
    """Create API token for current user."""
    try:
        api_token = auth_service.create_api_token(
            security_context.user.id, token_data.name, token_data.scopes, token_data.expires_days
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


@api_router.get("/api-tokens", response_model=APIEnvelope)
async def list_api_tokens(
    security_context: SecurityContext = Depends(get_current_security_context),
):
    """List user's API tokens."""
    try:
        with auth_service.db.get_session() as session:
            tokens = (
                session.query(APITokenModel)
                .filter(APITokenModel.user_id == security_context.user.id)
                .all()
            )

        token_list = []
        for token in tokens:
            token_data = {
                "id": token.id,
                "name": token.name,
                "token_prefix": token.token_prefix,
                "scopes": token.scopes,
                "created_at": token.created_at.isoformat(),
                "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                "last_used": token.last_used.isoformat() if token.last_used else None,
                "usage_count": token.usage_count,
            }
            token_list.append(token_data)

        return create_api_response(data=token_list, message="API tokens retrieved successfully")

    except Exception as e:
        logger.error(f"Failed to list API tokens: {str(e)}")
        return create_error_response(
            message="Failed to retrieve API tokens", error_type="TOKEN_LIST_FAILED"
        )


# Agent Operation Endpoints
@api_router.post("/agents", response_model=APIResponse)
async def create_agent(
    agent_data: AgentCreate,
    security_context: SecurityContext = Depends(require_permission("agent", "write")),
):
    """Create new agent (requires agent.write permission)."""
    try:
        agent = AgentModel(
            name=agent_data.name,
            description=agent_data.description,
            goals=agent_data.goals,
            memory_capacity=agent_data.memory_capacity,
            created_by=security_context.user.id,
        )

        with auth_service.db.get_session() as session:
            session.add(agent)
            session.commit()
            session.refresh(agent)

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


@api_router.get("/agents", response_model=APIEnvelope)
async def list_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    security_context: SecurityContext = Depends(require_permission("agent", "read")),
):
    """List agents (requires agent.read permission)."""
    try:
        with auth_service.db.get_session() as session:
            agents = session.query(AgentModel).offset(skip).limit(limit).all()

            agent_list = []
            for agent in agents:
                agent_data = {
                    "id": agent.id,
                    "name": agent.name,
                    "description": agent.description,
                    "status": agent.status,
                    "goals": agent.goals,
                    "memory_usage": len(agent.memory) if agent.memory else 0,
                    "created_at": agent.created_at.isoformat(),
                    "updated_at": agent.updated_at.isoformat(),
                }
                agent_list.append(agent_data)

            return create_api_response(data=agent_list, message="Agents retrieved successfully")

    except Exception as e:
        logger.error(f"Failed to list agents: {str(e)}")
        return create_error_response(
            message="Failed to retrieve agents", error_type="AGENT_LIST_FAILED"
        )


@api_router.get("/agents/{agent_id}", response_model=APIEnvelope)
async def get_agent(
    agent_id: str, security_context: SecurityContext = Depends(require_permission("agent", "read"))
):
    """Get specific agent details (requires agent.read permission)."""
    try:
        with auth_service.db.get_session() as session:
            agent = session.query(AgentModel).filter(AgentModel.id == agent_id).first()
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

            return create_api_response(
                data=agent_data, message="Agent details retrieved successfully"
            )

    except Exception as e:
        logger.error(f"Failed to get agent {agent_id}: {str(e)}")
        return create_error_response(
            message="Failed to retrieve agent details", error_type="AGENT_GET_FAILED"
        )


@api_router.post("/agents/{agent_id}/execute")
async def execute_agent(
    agent_id: str,
    security_context: SecurityContext = Depends(require_permission("agent", "execute")),
):
    """Execute agent operations (requires agent.execute permission)."""
    try:
        with auth_service.db.get_session() as session:
            agent = session.query(AgentModel).filter(AgentModel.id == agent_id).first()
            if not agent:
                return create_error_response(
                    message="Agent not found",
                    error_type="AGENT_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            # Record action
            action = ActionModel(
                action_id=str(uuid.uuid4()),
                agent_id=agent_id,
                action_type="manual_execution",
                description=f"Agent executed by {security_context.user.username}",
                user_id=security_context.user.id,
            )
            session.add(action)
            session.commit()

            # Update agent status
            agent.status = "executing"
            agent.last_execution = datetime.now(UTC)
            session.commit()

            logger.info(f"Agent {agent.name} executed by {security_context.user.username}")

            return create_api_response(
                data={
                    "agent_id": agent_id,
                    "status": "executing",
                    "action_id": action.id,
                    "executed_at": datetime.now(UTC).isoformat(),
                },
                message="Agent execution started",
            )

    except Exception as e:
        logger.error(f"Agent execution failed for {agent_id}: {str(e)}")
        return create_error_response(
            message="Failed to execute agent", error_type="AGENT_EXECUTION_FAILED"
        )


# Goal Management Endpoints
@api_router.post("/goals", response_model=APIResponse)
async def create_goal(
    goal_data: GoalCreate,
    security_context: SecurityContext = Depends(require_permission("goals", "write")),
):
    """Create new goal (requires goals.write permission)."""
    try:
        goal = GoalModel(
            title=goal_data.title,
            description=goal_data.description,
            priority=goal_data.priority,
            target_date=goal_data.target_date,
            created_by=security_context.user.id,
        )

        with auth_service.db.get_session() as session:
            session.add(goal)
            session.commit()
            session.refresh(goal)

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


@api_router.get("/goals", response_model=APIEnvelope)
async def list_goals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    security_context: SecurityContext = Depends(require_permission("goals", "read")),
):
    """List goals (requires goals.read permission)."""
    try:
        with auth_service.db.get_session() as session:
            goals = session.query(GoalModel).offset(skip).limit(limit).all()

            goal_list = []
            for goal in goals:
                goal_data = {
                    "id": goal.id,
                    "title": goal.title,
                    "description": goal.description,
                    "status": goal.status,
                    "priority": goal.priority,
                    "progress": goal.progress,
                    "created_at": goal.created_at.isoformat(),
                    "target_date": goal.target_date.isoformat() if goal.target_date else None,
                }
                goal_list.append(goal_data)

            return create_api_response(data=goal_list, message="Goals retrieved successfully")

    except Exception as e:
        logger.error(f"Failed to list goals: {str(e)}")
        return create_error_response(
            message="Failed to retrieve goals", error_type="GOAL_LIST_FAILED"
        )


# System Information Endpoints
@api_router.get("/system/health")
async def system_health():
    """System health check endpoint."""
    try:
        # Check database connection
        with auth_service.db.get_session() as session:
            session.execute(text("SELECT 1"))

        health_data = {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now(UTC).isoformat(),
            "version": "1.0.0",
        }

        return create_api_response(data=health_data, message="System is healthy")

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return create_error_response(
            message="System health check failed",
            error_type="HEALTH_CHECK_FAILED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@api_router.get("/system/info")
async def system_info(
    security_context: SecurityContext = Depends(require_permission("system", "read"))
):
    """Get system information (requires system.read permission)."""
    try:
        with auth_service.db.get_session() as session:
            user_count = session.query(UserModel).count()
            agent_count = session.query(AgentModel).count()
            goal_count = session.query(GoalModel).count()
            action_count = session.query(ActionModel).count()

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
