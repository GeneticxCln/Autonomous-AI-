"""
Authentication & Authorization Database Models
Enterprise-grade user management and security system
"""

from __future__ import annotations

import os
import secrets
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from passlib.context import CryptContext
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


# Database manager for auth system
class DatabaseManager:
    """Database connection and session management for auth system."""

    def __init__(
        self,
        database_url: str = "sqlite:///./agent_enterprise.db",
        *,
        pool_size: int | None = None,
        max_overflow: int | None = None,
        pool_timeout: int | None = None,
        pool_recycle: int | None = None,
    ):
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None
        # Allow environment overrides for pooling to support horizontal scaling
        self.pool_size = (
            pool_size if pool_size is not None else int(os.getenv("DB_POOL_SIZE", "10"))
        )
        self.max_overflow = (
            max_overflow if max_overflow is not None else int(os.getenv("DB_MAX_OVERFLOW", "20"))
        )
        self.pool_timeout = (
            pool_timeout if pool_timeout is not None else int(os.getenv("DB_POOL_TIMEOUT", "30"))
        )
        self.pool_recycle = (
            pool_recycle if pool_recycle is not None else int(os.getenv("DB_POOL_RECYCLE", "300"))
        )

    def configure_pool(
        self,
        *,
        pool_size: Optional[int] = None,
        max_overflow: Optional[int] = None,
        pool_timeout: Optional[int] = None,
        pool_recycle: Optional[int] = None,
    ) -> None:
        """Allow the hosting app to override pooling defaults prior to init."""
        if pool_size is not None:
            self.pool_size = pool_size
        if max_overflow is not None:
            self.max_overflow = max_overflow
        if pool_timeout is not None:
            self.pool_timeout = pool_timeout
        if pool_recycle is not None:
            self.pool_recycle = pool_recycle

    def _engine_kwargs(self) -> Dict[str, Any]:
        """Build SQLAlchemy engine configuration with pooling enabled."""
        kwargs: Dict[str, Any] = {
            "pool_pre_ping": True,
            "pool_recycle": self.pool_recycle,
            "echo": False,
        }
        if self.pool_size:
            kwargs["pool_size"] = self.pool_size
        if self.max_overflow is not None:
            kwargs["max_overflow"] = self.max_overflow
        if self.pool_timeout is not None:
            kwargs["pool_timeout"] = self.pool_timeout
        if self.database_url.startswith("sqlite"):
            # Ensure proper typing for connect_args
            existing = kwargs.get("connect_args")
            connect_args: Dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
            connect_args.update({"check_same_thread": False})
            kwargs["connect_args"] = connect_args
        return kwargs

    def initialize(self) -> None:
        """Initialize database connection and create tables."""
        try:
            engine_kwargs = self._engine_kwargs()
            self.engine = create_engine(self.database_url, **engine_kwargs)

            # Create session factory (prevent attribute expiration on commit)
            self.SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=self.engine, expire_on_commit=False
            )

            # Create all tables
            Base.metadata.create_all(bind=self.engine)

            print(
                f"✅ Auth database initialized successfully: {self._mask_db_url(self.database_url)}"
            )

        except Exception as e:
            print(f"❌ Auth database initialization failed: {e}")
            raise

    def get_session(self) -> Session:
        """Get a database session."""
        if not self.SessionLocal:
            raise RuntimeError("Auth database not initialized. Call initialize() first.")
        return self.SessionLocal()

    def close(self) -> None:
        """Close database connections."""
        if self.engine:
            self.engine.dispose()
            print("✅ Auth database connections closed")

    @staticmethod
    def _mask_db_url(url: str) -> str:
        """Mask credentials in database URL for safe logging."""
        try:
            if url.startswith("sqlite"):
                return url
            if "://" not in url:
                return "***"
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                _, host = rest.split("@", 1)
                return f"{scheme}://***@{host}"
            return f"{scheme}://***"
        except Exception:
            return "***"


# Global auth database manager instance
db_manager = DatabaseManager()


class Base(DeclarativeBase):  # type: ignore[misc]
    pass


# Password hashing context (prefer passlib; fallback to sha256 comparison for legacy hashes)
pwd_context = CryptContext(schemes=["argon2", "sha256_crypt"], deprecated="auto")


# Shared exception hierarchy (used by auth_service and tests)
class AuthenticationError(Exception):
    pass


class AuthorizationError(Exception):
    pass


class UserNotFoundError(AuthenticationError):
    pass


class InvalidCredentialsError(AuthenticationError):
    pass


class AccountLockedError(AuthenticationError):
    pass


class TokenExpiredError(AuthenticationError):
    pass


class InsufficientPermissionsError(AuthorizationError):
    pass


# Association tables for many-to-many relationships
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE")),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE")),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE")),
    Column("permission_id", String(36), ForeignKey("permissions.id", ondelete="CASCADE")),
)


class UserStatus(Enum):
    """User account status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class RoleLevel(Enum):
    """Role hierarchy levels."""

    ADMIN = 100
    MANAGER = 75
    USER = 50
    GUEST = 25
    READONLY = 10


class UserModel(Base):
    """Database model for user accounts."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_login_attempt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Security settings
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(32))
    backup_codes: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Profile data
    preferences: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    user_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    # Relationships
    roles: Mapped[List["RoleModel"]] = relationship(
        secondary=user_roles, back_populates="users"
    )
    sessions: Mapped[List["UserSessionModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuthSecurityEventModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_user_username", "username"),
        Index("idx_user_email", "email"),
        Index("idx_user_status", "status"),
        Index("idx_user_active", "is_active"),
        Index("idx_user_created", "created_at"),
        UniqueConstraint("username", name="uq_user_username"),
        UniqueConstraint("email", name="uq_user_email"),
    )

    def check_password(self, password: str) -> bool:
        """Check password; supports argon2/sha256_crypt and migrates legacy sha256 to argon2 on success."""
        try:
            # Passlib-managed hashes
            if self.hashed_password and self.hashed_password.startswith("$argon2"):
                return bool(pwd_context.verify(password, self.hashed_password))

            # sha256_crypt ($5$) -> migrate to argon2 on success
            if self.hashed_password and self.hashed_password.startswith("$5$"):
                ok: bool = bool(pwd_context.verify(password, self.hashed_password))
                if ok:
                    try:
                        self.hashed_password = pwd_context.hash(password)
                        self.password_changed_at = datetime.now(UTC)
                    except Exception:
                        pass
                return ok

            # Legacy sha256 hex hash
            import hashlib

            expected_hash = hashlib.sha256(password.encode()).hexdigest()
            if self.hashed_password == expected_hash:
                # Upgrade hash to argon2
                self.hashed_password = pwd_context.hash(password)
                self.password_changed_at = datetime.now(UTC)
                return True
            return False
        except Exception:
            return False


class RoleModel(Base):
    """Database model for user roles."""

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    level: Mapped[int] = mapped_column(Integer, default=50, index=True)  # Role hierarchy level
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)  # System roles cannot be deleted
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    users: Mapped[List["UserModel"]] = relationship(
        secondary=user_roles, back_populates="roles"
    )
    permissions: Mapped[List["PermissionModel"]] = relationship(
        secondary=role_permissions, back_populates="roles"
    )

    # Indexes
    __table_args__ = (
        Index("idx_role_name", "name"),
        Index("idx_role_level", "level"),
        Index("idx_role_active", "is_active"),
        UniqueConstraint("name", name="uq_role_name"),
    )


class PermissionModel(Base):
    """Database model for permissions."""

    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    resource: Mapped[str] = mapped_column(String(50), index=True)  # e.g., 'agent', 'goals', 'actions'
    action: Mapped[str] = mapped_column(String(50), index=True)  # e.g., 'read', 'write', 'delete', 'admin'
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)  # System permissions
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    roles: Mapped[List["RoleModel"]] = relationship(
        secondary=role_permissions, back_populates="permissions"
    )

    # Indexes
    __table_args__ = (
        Index("idx_permission_name", "name"),
        Index("idx_permission_resource", "resource"),
        Index("idx_permission_action", "action"),
        Index("idx_permission_active", "is_active"),
        UniqueConstraint("name", name="uq_permission_name"),
    )


class UserSessionModel(Base):
    """Database model for user sessions."""

    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    refresh_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    device_info: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))  # IPv6 compatible
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    last_accessed: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="sessions")

    # Indexes
    __table_args__ = (
        Index("idx_session_user", "user_id"),
        Index("idx_session_token", "session_token"),
        Index("idx_session_expires", "expires_at"),
        Index("idx_session_active", "is_active"),
        UniqueConstraint("session_token", name="uq_session_token"),
    )


class APITokenModel(Base):
    """Database model for API tokens."""

    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False)  # First 8 chars for identification
    scopes: Mapped[List[str]] = mapped_column(JSON, default=list)  # API scopes/permissions
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Indexes
    __table_args__ = (
        Index("idx_token_user", "user_id"),
        Index("idx_token_hash", "token_hash"),
        Index("idx_token_prefix", "token_prefix"),
        Index("idx_token_active", "is_active"),
        Index("idx_token_expires", "expires_at"),
        UniqueConstraint("token_hash", name="uq_token_hash"),
    )


class AuthSecurityEventModel(Base):
    """Database model for security events."""

    __tablename__ = "security_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # login, logout, failed_login, etc.
    severity: Mapped[str] = mapped_column(String(20), default="info", index=True)  # info, warning, error, critical
    description: Mapped[str] = mapped_column(Text, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    event_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)

    # Relationship
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="audit_logs")

    # Indexes
    __table_args__ = (
        Index("idx_event_user", "user_id"),
        Index("idx_event_type", "event_type"),
        Index("idx_event_severity", "severity"),
        Index("idx_event_resolved", "resolved"),
        Index("idx_event_created", "created_at"),
    )


class PasswordResetModel(Base):
    """Database model for password reset tokens."""

    __tablename__ = "password_resets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_reset_user", "user_id"),
        Index("idx_reset_token", "token_hash"),
        Index("idx_reset_email", "email"),
        Index("idx_reset_expires", "expires_at"),
        Index("idx_reset_used", "used"),
        UniqueConstraint("token_hash", name="uq_reset_token"),
    )


# Default roles and permissions
DEFAULT_ROLES = [
    {
        "name": "admin",
        "description": "System administrator with full access",
        "level": RoleLevel.ADMIN.value,
        "is_system": True,
    },
    {
        "name": "manager",
        "description": "Manager with elevated privileges",
        "level": RoleLevel.MANAGER.value,
        "is_system": True,
    },
    {
        "name": "user",
        "description": "Regular user with standard access",
        "level": RoleLevel.USER.value,
        "is_system": True,
    },
    {
        "name": "guest",
        "description": "Guest user with limited access",
        "level": RoleLevel.GUEST.value,
        "is_system": True,
    },
]

DEFAULT_PERMISSIONS = [
    # Agent permissions
    {
        "name": "agent.read",
        "description": "Read agent status and information",
        "resource": "agent",
        "action": "read",
    },
    {
        "name": "agent.write",
        "description": "Modify agent configuration",
        "resource": "agent",
        "action": "write",
    },
    {
        "name": "agent.execute",
        "description": "Execute agent operations",
        "resource": "agent",
        "action": "execute",
    },
    {
        "name": "agent.admin",
        "description": "Full agent administration",
        "resource": "agent",
        "action": "admin",
    },
    # Goal permissions
    {
        "name": "goals.read",
        "description": "Read agent goals",
        "resource": "goals",
        "action": "read",
    },
    {
        "name": "goals.write",
        "description": "Create and modify goals",
        "resource": "goals",
        "action": "write",
    },
    {
        "name": "goals.delete",
        "description": "Delete goals",
        "resource": "goals",
        "action": "delete",
    },
    # Action permissions
    {
        "name": "actions.read",
        "description": "Read action history",
        "resource": "actions",
        "action": "read",
    },
    {
        "name": "actions.write",
        "description": "Execute actions",
        "resource": "actions",
        "action": "write",
    },
    # System permissions
    {
        "name": "system.read",
        "description": "Read system information",
        "resource": "system",
        "action": "read",
    },
    {
        "name": "system.write",
        "description": "Modify system settings",
        "resource": "system",
        "action": "write",
    },
    {
        "name": "system.admin",
        "description": "Full system administration",
        "resource": "system",
        "action": "admin",
    },
    # User management permissions
    {
        "name": "users.read",
        "description": "Read user information",
        "resource": "users",
        "action": "read",
    },
    {
        "name": "users.write",
        "description": "Create and modify users",
        "resource": "users",
        "action": "write",
    },
    {
        "name": "users.delete",
        "description": "Delete users",
        "resource": "users",
        "action": "delete",
    },
    {
        "name": "users.admin",
        "description": "Full user administration",
        "resource": "users",
        "action": "admin",
    },
]

# Default role-permission mappings
DEFAULT_ROLE_PERMISSIONS = {
    "admin": [
        "agent.read",
        "agent.write",
        "agent.execute",
        "agent.admin",
        "goals.read",
        "goals.write",
        "goals.delete",
        "actions.read",
        "actions.write",
        "system.read",
        "system.write",
        "system.admin",
        "users.read",
        "users.write",
        "users.delete",
        "users.admin",
    ],
    "manager": [
        "agent.read",
        "agent.write",
        "agent.execute",
        "goals.read",
        "goals.write",
        "goals.delete",
        "actions.read",
        "actions.write",
        "system.read",
        "system.write",
    ],
    "user": [
        "agent.read",
        "agent.execute",
        "goals.read",
        "goals.write",
        "actions.read",
        "actions.write",
        "system.read",
    ],
    "guest": ["agent.read", "goals.read", "actions.read"],
}


class SecurityContext:
    """Security context for authenticated requests."""

    def __init__(self, user: UserModel, permissions: List[str], session_id: Optional[str] = None):
        self.user = user
        self.permissions = permissions
        self.session_id = session_id
        self.is_admin = "admin" in [
            p.split(".")[1] for p in permissions if "." in p and p.endswith(".admin")
        ]
        self.is_manager = "manager" in [r.name for r in user.roles] if user.roles else False

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if user has specific permission."""
        permission_name = f"{resource}.{action}"
        return permission_name in self.permissions

    def has_any_permission(self, permissions: List[str]) -> bool:
        """Check if user has any of the specified permissions."""
        return any(p in self.permissions for p in permissions)

    def has_all_permissions(self, permissions: List[str]) -> bool:
        """Check if user has all specified permissions."""
        return all(p in self.permissions for p in permissions)

    def require_permission(self, resource: str, action: str) -> None:
        """Require specific permission - raises exception if not granted."""
        if not self.has_permission(resource, action):
            raise PermissionError(f"Permission denied: {resource}.{action}")

    def require_admin(self) -> None:
        """Require admin privileges."""
        if not self.is_admin:
            raise PermissionError("Admin privileges required")


def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure random token."""
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """Hash token for secure storage."""
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()
