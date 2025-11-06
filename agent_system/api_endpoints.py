"""
FastAPI Authentication & Agent Operation Endpoints
Production-ready API with enterprise security
"""
from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any
import uuid
from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import text

from .api_security import (
    get_current_user, get_current_security_context, require_permission, require_admin,
    create_api_response, create_error_response, log_api_access
)
from .auth_models import UserModel, SecurityContext
from .auth_models import APITokenModel
from .auth_service import auth_service
from .database_models import AgentModel, GoalModel, ActionModel

# Import auth models to register them with SQLAlchemy
from . import auth_models  # noqa: F401

logger = logging.getLogger(__name__)

# Create main API router
api_router = APIRouter(prefix="/api/v1", tags=["Authentication", "Agent Operations"])

# Pydantic models for API requests/responses
class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or email")
    password: str = Field(..., min_length=6, description="User password")
    remember_me: bool = Field(default=False, description="Extended session duration")

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6, description="User password")
    role_names: Optional[List[str]] = Field(default=["user"], description="User roles")

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    is_active: bool
    roles: List[str]
    created_at: datetime
    last_login: Optional[datetime] = None

class APITokenCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = Field(..., description="API scopes/permissions")
    expires_days: Optional[int] = Field(default=30, ge=1, le=365)

class APITokenResponse(BaseModel):
    id: str
    name: str
    token_prefix: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    usage_count: int = 0

class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default="", max_length=500)
    goals: List[str] = Field(default_factory=list)
    memory_capacity: int = Field(default=1000, ge=100, le=10000)

class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    goals: List[str]
    memory_usage: int
    created_at: datetime
    updated_at: datetime

class GoalCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default="", max_length=1000)
    priority: int = Field(default=1, ge=1, le=10)
    target_date: Optional[datetime] = None

class GoalResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    priority: int
    progress: float
    created_at: datetime
    target_date: Optional[datetime] = None


class APIEnvelope(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    timestamp: float

# Authentication Endpoints
@api_router.post("/auth/login", response_model=APIEnvelope)
async def login(request: Request, login_data: LoginRequest):
    """Authenticate user and return JWT tokens."""
    try:
        # Authenticate user
        security_context = auth_service.authenticate_user(
            login_data.username,
            login_data.password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )

        # Create user session
        tokens = auth_service.create_user_session(
            security_context.user.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )

        # Build user info
        user_info = {
            "id": security_context.user.id,
            "username": security_context.user.username,
            "email": security_context.user.email,
            "full_name": security_context.user.full_name,
            "roles": [role.name for role in security_context.user.roles],
            "permissions": security_context.permissions,
            "is_admin": security_context.is_admin
        }

        logger.info(f"User {security_context.user.username} logged in successfully")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    "token_type": tokens["token_type"],
                    "expires_in": tokens["expires_in"],
                    "user": user_info
                }
            }
        )

    except Exception as e:
        logger.warning(f"Login failed for {login_data.username}: {str(e)}")
        return create_error_response(
            message="Invalid username or password",
            error_type="AUTHENTICATION_FAILED",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

@api_router.post("/auth/refresh", response_model=APIEnvelope)
async def refresh_token(request: Request, refresh_data: TokenRefreshRequest):
    """Refresh access token using refresh token."""
    try:
        tokens = auth_service.refresh_access_token(refresh_data.refresh_token)

        return create_api_response(
            data=tokens,
            message="Token refreshed successfully"
        )

    except Exception as e:
        logger.warning(f"Token refresh failed: {str(e)}")
        return create_error_response(
            message="Invalid or expired refresh token",
            error_type="TOKEN_REFRESH_FAILED",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

@api_router.post("/auth/logout", response_model=APIEnvelope)
async def logout(request: Request, security_context: SecurityContext = Depends(get_current_security_context)):
    """Logout user and invalidate session."""
    try:
        auth_service.logout(
            security_context.user.id,
            security_context.session_id
        )

        logger.info(f"User {security_context.user.username} logged out successfully")

        return create_api_response(
            message="Logged out successfully"
        )

    except Exception as e:
        logger.error(f"Logout failed for user {security_context.user.username}: {str(e)}")
        return create_error_response(
            message="Logout failed",
            error_type="LOGOUT_FAILED"
        )

@api_router.get("/auth/me", response_model=APIEnvelope)
async def get_current_user_info(security_context: SecurityContext = Depends(get_current_security_context)):
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
            "last_login": security_context.user.last_login.isoformat() if security_context.user.last_login else None,
            "created_at": security_context.user.created_at.isoformat()
        }

        return create_api_response(
            data=user_data,
            message="User information retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Failed to get user info: {str(e)}")
        return create_error_response(
            message="Failed to retrieve user information",
            error_type="USER_INFO_FAILED"
        )

# User Management Endpoints
@api_router.post("/users", response_model=APIEnvelope)
async def create_user(
    user_data: UserCreateRequest,
    security_context: SecurityContext = Depends(require_permission("users", "write"))
):
    """Create new user account (requires users.write permission)."""
    try:
        user = auth_service.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role_names=user_data.role_names
        )

        response_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "roles": [role.name for role in user.roles],
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None
        }

        return create_api_response(
            data=response_data,
            message="User created successfully",
            status_code=status.HTTP_201_CREATED
        )

    except ValueError as e:
        return create_error_response(
            message=str(e),
            error_type="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"User creation failed: {str(e)}")
        return create_error_response(
            message="Failed to create user",
            error_type="USER_CREATION_FAILED"
        )

@api_router.get("/users", response_model=APIEnvelope)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    security_context: SecurityContext = Depends(require_permission("users", "read"))
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
                    "last_login": user.last_login.isoformat() if user.last_login else None
                }
                user_list.append(user_data)

            return create_api_response(
                data=user_list,
                message="Users retrieved successfully"
            )

    except Exception as e:
        logger.error(f"Failed to list users: {str(e)}")
        return create_error_response(
            message="Failed to retrieve users",
            error_type="USER_LIST_FAILED"
        )

# API Token Management
@api_router.post("/api-tokens", response_model=APIEnvelope)
async def create_api_token(
    token_data: APITokenCreateRequest,
    security_context: SecurityContext = Depends(get_current_security_context)
):
    """Create API token for current user."""
    try:
        api_token = auth_service.create_api_token(
            security_context.user.id,
            token_data.name,
            token_data.scopes,
            token_data.expires_days
        )

        return create_api_response(
            data={
                "token": api_token,
                "prefix": api_token[:8],
                "name": token_data.name,
                "scopes": token_data.scopes
            },
            message="API token created successfully",
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        logger.error(f"API token creation failed: {str(e)}")
        return create_error_response(
            message="Failed to create API token",
            error_type="TOKEN_CREATION_FAILED"
        )

@api_router.get("/api-tokens", response_model=APIEnvelope)
async def list_api_tokens(
    security_context: SecurityContext = Depends(get_current_security_context)
):
    """List user's API tokens."""
    try:
        with auth_service.db.get_session() as session:
            tokens = session.query(APITokenModel).filter(
                APITokenModel.user_id == security_context.user.id
            ).all()

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
                "usage_count": token.usage_count
            }
            token_list.append(token_data)

        return create_api_response(
            data=token_list,
            message="API tokens retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Failed to list API tokens: {str(e)}")
        return create_error_response(
            message="Failed to retrieve API tokens",
            error_type="TOKEN_LIST_FAILED"
        )

# Agent Operation Endpoints
@api_router.post("/agents", response_model=APIEnvelope)
async def create_agent(
    agent_data: AgentCreateRequest,
    security_context: SecurityContext = Depends(require_permission("agent", "write"))
):
    """Create new agent (requires agent.write permission)."""
    try:
        agent = AgentModel(
            name=agent_data.name,
            description=agent_data.description,
            goals=agent_data.goals,
            memory_capacity=agent_data.memory_capacity,
            created_by=security_context.user.id
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
            "updated_at": agent.updated_at.isoformat()
        }

        logger.info(f"Agent {agent.name} created by {security_context.user.username}")

        return create_api_response(
            data=agent_response,
            message="Agent created successfully",
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        logger.error(f"Agent creation failed: {str(e)}")
        return create_error_response(
            message="Failed to create agent",
            error_type="AGENT_CREATION_FAILED"
        )

@api_router.get("/agents", response_model=APIEnvelope)
async def list_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    security_context: SecurityContext = Depends(require_permission("agent", "read"))
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
                    "updated_at": agent.updated_at.isoformat()
                }
                agent_list.append(agent_data)

            return create_api_response(
                data=agent_list,
                message="Agents retrieved successfully"
            )

    except Exception as e:
        logger.error(f"Failed to list agents: {str(e)}")
        return create_error_response(
            message="Failed to retrieve agents",
            error_type="AGENT_LIST_FAILED"
        )

@api_router.get("/agents/{agent_id}", response_model=APIEnvelope)
async def get_agent(
    agent_id: str,
    security_context: SecurityContext = Depends(require_permission("agent", "read"))
):
    """Get specific agent details (requires agent.read permission)."""
    try:
        with auth_service.db.get_session() as session:
            agent = session.query(AgentModel).filter(AgentModel.id == agent_id).first()
            if not agent:
                return create_error_response(
                    message="Agent not found",
                    error_type="AGENT_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND
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
                "updated_at": agent.updated_at.isoformat()
            }

            return create_api_response(
                data=agent_data,
                message="Agent details retrieved successfully"
            )

    except Exception as e:
        logger.error(f"Failed to get agent {agent_id}: {str(e)}")
        return create_error_response(
            message="Failed to retrieve agent details",
            error_type="AGENT_GET_FAILED"
        )

@api_router.post("/agents/{agent_id}/execute")
async def execute_agent(
    agent_id: str,
    security_context: SecurityContext = Depends(require_permission("agent", "execute"))
):
    """Execute agent operations (requires agent.execute permission)."""
    try:
        with auth_service.db.get_session() as session:
            agent = session.query(AgentModel).filter(AgentModel.id == agent_id).first()
            if not agent:
                return create_error_response(
                    message="Agent not found",
                    error_type="AGENT_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            # Record action
            action = ActionModel(
                action_id=str(uuid.uuid4()),
                agent_id=agent_id,
                action_type="manual_execution",
                description=f"Agent executed by {security_context.user.username}",
                user_id=security_context.user.id
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
                    "executed_at": datetime.now(UTC).isoformat()
                },
                message="Agent execution started"
            )

    except Exception as e:
        logger.error(f"Agent execution failed for {agent_id}: {str(e)}")
        return create_error_response(
            message="Failed to execute agent",
            error_type="AGENT_EXECUTION_FAILED"
        )

# Goal Management Endpoints
@api_router.post("/goals", response_model=APIEnvelope)
async def create_goal(
    goal_data: GoalCreateRequest,
    security_context: SecurityContext = Depends(require_permission("goals", "write"))
):
    """Create new goal (requires goals.write permission)."""
    try:
        goal = GoalModel(
            title=goal_data.title,
            description=goal_data.description,
            priority=goal_data.priority,
            target_date=goal_data.target_date,
            created_by=security_context.user.id
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
            "target_date": goal.target_date.isoformat() if goal.target_date else None
        }

        logger.info(f"Goal '{goal.title}' created by {security_context.user.username}")

        return create_api_response(
            data=goal_response,
            message="Goal created successfully",
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        logger.error(f"Goal creation failed: {str(e)}")
        return create_error_response(
            message="Failed to create goal",
            error_type="GOAL_CREATION_FAILED"
        )

@api_router.get("/goals", response_model=APIEnvelope)
async def list_goals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    security_context: SecurityContext = Depends(require_permission("goals", "read"))
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
                    "target_date": goal.target_date.isoformat() if goal.target_date else None
                }
                goal_list.append(goal_data)

            return create_api_response(
                data=goal_list,
                message="Goals retrieved successfully"
            )

    except Exception as e:
        logger.error(f"Failed to list goals: {str(e)}")
        return create_error_response(
            message="Failed to retrieve goals",
            error_type="GOAL_LIST_FAILED"
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
            "version": "1.0.0"
        }

        return create_api_response(
            data=health_data,
            message="System is healthy"
        )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return create_error_response(
            message="System health check failed",
            error_type="HEALTH_CHECK_FAILED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

@api_router.get("/system/info")
async def system_info(security_context: SecurityContext = Depends(require_permission("system", "read"))):
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
            "timestamp": datetime.now(UTC).isoformat()
        }

        return create_api_response(
            data=system_data,
            message="System information retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Failed to get system info: {str(e)}")
        return create_error_response(
            message="Failed to retrieve system information",
            error_type="SYSTEM_INFO_FAILED"
        )