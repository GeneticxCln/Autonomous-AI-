"""
API Schemas for OpenAPI Documentation
Comprehensive request/response models with examples
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# Enums
class UserStatus(str, Enum):
    """User account status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class RoleLevel(str, Enum):
    """Role hierarchy levels."""

    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    GUEST = "guest"


class SecurityEventType(str, Enum):
    """Security event types."""

    LOGIN = "login"
    LOGOUT = "logout"
    FAILED_LOGIN = "failed_login"
    ACCOUNT_LOCKED = "account_locked"
    TOKEN_CREATED = "token_created"
    TOKEN_REVOKED = "token_revoked"
    USER_CREATED = "user_created"
    USER_MODIFIED = "user_modified"
    PERMISSION_DENIED = "permission_denied"


class SecuritySeverity(str, Enum):
    """Security event severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Base Response Models
class APIResponse(BaseModel):
    """Base API response model."""

    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="Human-readable response message")
    timestamp: float = Field(..., description="Unix timestamp of response")
    data: Optional[Any] = Field(None, description="Response data payload")


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    field: Optional[str] = Field(None, description="Field that caused the error")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class APIError(BaseModel):
    """API error response model."""

    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error type/category")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[List[ErrorDetail]] = Field(None, description="Detailed error information")
    timestamp: float = Field(..., description="Unix timestamp of error")


# Authentication Schemas
class LoginRequest(BaseModel):
    """User login request."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Username or email address",
    )
    password: str = Field(
        ...,
        min_length=6,
        description="User password",
    )
    remember_me: bool = Field(False, description="Extended session duration")

    @field_validator("username")
    def validate_username(cls, v):
        if not v.strip():
            raise ValueError("Username cannot be empty")
        return v.strip()


class TokenData(BaseModel):
    """JWT token data."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class UserInfo(BaseModel):
    """User information model."""

    id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    full_name: str = Field(..., description="Full name")
    is_active: bool = Field(..., description="Whether user account is active")
    is_admin: bool = Field(..., description="Whether user has admin privileges")
    roles: List[str] = Field(default_factory=list, description="User roles")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Account creation timestamp")


class LoginResponse(BaseModel):
    """Login response model."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(1800, description="Token expiration time in seconds")
    user: UserInfo = Field(..., description="User information")


class TokenRefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(
        ...,
        description="Refresh token",
    )


# User Management Schemas
class UserCreate(BaseModel):
    """User creation request."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Unique username",
    )
    email: EmailStr = Field(..., description="Email address")
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="User's full name",
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Password (8+ characters)",
    )
    role_names: List[str] = Field(
        default=["user"],
        description="User roles",
    )

    @field_validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain letters")
        return v


class UserUpdate(BaseModel):
    """User update request."""

    email: Optional[EmailStr] = Field(None, description="Email address")
    full_name: Optional[str] = Field(
        None, min_length=2, max_length=100, description="User's full name"
    )
    is_active: Optional[bool] = Field(None, description="Account active status")
    role_names: Optional[List[str]] = Field(None, description="User roles")


class UserResponse(BaseModel):
    """User response model."""

    id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    full_name: str = Field(..., description="Full name")
    is_active: bool = Field(..., description="Whether user account is active")
    is_verified: bool = Field(..., description="Whether email is verified")
    status: UserStatus = Field(..., description="Account status")
    roles: List[str] = Field(default_factory=list, description="User roles")
    failed_login_attempts: int = Field(0, description="Failed login attempts count")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# Agent Management Schemas
class AgentCreate(BaseModel):
    """Agent creation request."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Agent name",
    )
    description: Optional[str] = Field(
        "",
        max_length=500,
        description="Agent description",
    )
    goals: List[str] = Field(
        default_factory=list,
        description="Agent goals",
    )
    memory_capacity: int = Field(1000, ge=100, le=10000, description="Memory capacity limit")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Agent configuration")


class AgentResponse(BaseModel):
    """Agent response model."""

    id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    status: str = Field(..., description="Agent status")
    goals: List[str] = Field(default_factory=list, description="Agent goals")
    memory_usage: int = Field(0, description="Current memory usage")
    memory_capacity: int = Field(1000, description="Memory capacity")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Configuration")
    performance_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Performance metrics"
    )
    created_by: Optional[str] = Field(None, description="Creator user ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_execution: Optional[datetime] = Field(None, description="Last execution timestamp")


class AgentExecute(BaseModel):
    """Agent execution request."""

    action: str = Field(
        ...,
        description="Action to execute",
    )
    parameters: Optional[Dict[str, Any]] = Field(None, description="Action parameters")


class AgentExecutionResponse(BaseModel):
    """Agent execution response."""

    agent_id: str = Field(..., description="Agent identifier")
    action_id: str = Field(..., description="Action execution ID")
    status: str = Field(..., description="Execution status")
    result: Optional[Dict[str, Any]] = Field(None, description="Execution result")
    started_at: datetime = Field(..., description="Execution start time")


# Goal Management Schemas
class GoalCreate(BaseModel):
    """Goal creation request."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Goal title",
    )
    description: Optional[str] = Field("", max_length=1000, description="Goal description")
    priority: int = Field(1, ge=1, le=10, description="Goal priority (1-10, 10 highest)")
    target_date: Optional[datetime] = Field(None, description="Target completion date")


class GoalResponse(BaseModel):
    """Goal response model."""

    id: str = Field(..., description="Unique goal identifier")
    title: str = Field(..., description="Goal title")
    description: str = Field(..., description="Goal description")
    status: str = Field(..., description="Goal status")
    priority: int = Field(..., description="Goal priority")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Completion progress")
    target_date: Optional[datetime] = Field(None, description="Target date")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")


# API Token Schemas
class APITokenCreate(BaseModel):
    """API token creation request."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Token name",
    )
    scopes: List[str] = Field(
        ...,
        description="Token scopes/permissions",
    )
    expires_days: Optional[int] = Field(30, ge=1, le=365, description="Expiration days")


class APITokenResponse(BaseModel):
    """API token response model."""

    id: str = Field(..., description="Token identifier")
    name: str = Field(..., description="Token name")
    token_prefix: str = Field(..., description="Token prefix for identification")
    scopes: List[str] = Field(default_factory=list, description="Token scopes")
    is_active: bool = Field(..., description="Token active status")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    usage_count: int = Field(0, description="Usage count")
    created_at: datetime = Field(..., description="Creation timestamp")


# Security Event Schemas
class SecurityEventResponse(BaseModel):
    """Security event response model."""

    id: str = Field(..., description="Event identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    event_type: SecurityEventType = Field(..., description="Event type")
    severity: SecuritySeverity = Field(..., description="Event severity")
    description: str = Field(..., description="Event description")
    ip_address: Optional[str] = Field(None, description="Source IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    resolved: bool = Field(False, description="Whether event is resolved")
    created_at: datetime = Field(..., description="Event timestamp")


# System Information Schemas
class SystemHealth(BaseModel):
    """System health information."""

    status: str = Field(..., description="System status")
    database: str = Field(..., description="Database status")
    timestamp: float = Field(..., description="Check timestamp")
    version: str = Field(..., description="System version")


class SystemInfo(BaseModel):
    """System information."""

    users: int = Field(..., description="Total user count")
    agents: int = Field(..., description="Total agent count")
    goals: int = Field(..., description="Total goal count")
    actions: int = Field(..., description="Total action count")
    uptime: str = Field(..., description="System uptime")
    version: str = Field(..., description="System version")
    timestamp: float = Field(..., description="Information timestamp")


# Pagination Schema
class PaginationInfo(BaseModel):
    """Pagination information."""

    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total items count")
    pages: int = Field(..., description="Total pages count")


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    items: List[Any] = Field(..., description="Response items")
    pagination: PaginationInfo = Field(..., description="Pagination information")


# Webhook Schemas
class WebhookEvent(BaseModel):
    """Webhook event model."""

    id: str = Field(..., description="Event identifier")
    type: str = Field(..., description="Event type")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: float = Field(..., description="Event timestamp")


# Rate Limiting Schemas
class RateLimitInfo(BaseModel):
    """Rate limiting information."""

    limit: int = Field(..., description="Rate limit")
    remaining: int = Field(..., description="Requests remaining")
    reset: float = Field(..., description="Reset timestamp")
    retry_after: Optional[int] = Field(None, description="Retry after seconds")


# Bulk Operations Schemas
class BulkOperationRequest(BaseModel):
    """Bulk operation request."""

    operation: str = Field(..., description="Operation type")
    items: List[str] = Field(..., description="Item identifiers")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Operation parameters")


class BulkOperationResponse(BaseModel):
    """Bulk operation response."""

    operation: str = Field(..., description="Operation type")
    total: int = Field(..., description="Total items")
    successful: int = Field(..., description="Successful operations")
    failed: int = Field(..., description="Failed operations")
    results: List[Dict[str, Any]] = Field(default_factory=list, description="Operation results")
