"""
Authentication & Authorization Service
Enterprise-grade JWT-based authentication with RBAC
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Dict, List

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from .auth_models import (
    DEFAULT_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    DEFAULT_ROLES,
    AccountLockedError,
    APITokenModel,
    AuthenticationError,
    AuthSecurityEventModel,
    InsufficientPermissionsError,
    InvalidCredentialsError,
    PermissionModel,
    RoleModel,
    SecurityContext,
    TokenExpiredError,
    UserModel,
    UserNotFoundError,
    UserSessionModel,
    db_manager,
    generate_secure_token,
    hash_token,
)

logger = logging.getLogger(__name__)

# JWT Configuration from production_config (fallbacks provided)
try:
    from .production_config import get_config

    _cfg = get_config()
    JWT_SECRET_KEY = _cfg.jwt_secret_key
    JWT_ALGORITHM = _cfg.jwt_algorithm
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = _cfg.jwt_access_token_expire_minutes
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = _cfg.jwt_refresh_token_expire_days
except Exception:
    JWT_SECRET_KEY = "your-super-secret-jwt-key-change-in-production"
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30

# Password hashing - temporarily using sha256 for compatibility
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")


"""Exceptions imported from auth_models for shared usage."""


class AuthService:
    """Authentication and authorization service."""

    def __init__(self):
        self.db = db_manager
        # Don't auto-initialize - let the app control initialization
        self._initialized = False
        # Expose configurable expirations on the instance for tests
        self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.JWT_REFRESH_TOKEN_EXPIRE_DAYS = JWT_REFRESH_TOKEN_EXPIRE_DAYS

    def initialize(self):
        """Initialize the authentication service."""
        if not self._initialized:
            self._initialize_default_data()
            self._initialized = True
            logger.info("Authentication service initialized successfully")

    def _initialize_default_data(self):
        """Initialize default roles and permissions."""
        try:
            # Ensure database is initialized first
            if not self.db.SessionLocal:
                raise RuntimeError("Auth database not initialized. Call initialize() first.")

            with self.db.get_session() as session:
                # Check if roles already exist
                existing_roles = session.query(RoleModel).count()
                if existing_roles == 0:
                    self._create_default_roles_and_permissions(session)
                    logger.info("Default roles and permissions created")

                # Ensure default admin user exists
                self._ensure_default_admin(session)
        except Exception as e:
            logger.error(f"Failed to initialize default auth data: {e}")
            raise  # Re-raise to prevent silent failures

    def _ensure_initialized(self):
        """Ensure the service is initialized before use."""
        if not self._initialized:
            self.initialize()

    def _create_default_roles_and_permissions(self, session: Session):
        """Create default roles and permissions."""
        # Create permissions first
        permissions_map = {}
        for perm_data in DEFAULT_PERMISSIONS:
            permission = PermissionModel(**perm_data)
            session.add(permission)
            session.flush()
            permissions_map[perm_data["name"]] = permission

        # Create roles
        roles_map = {}
        for role_data in DEFAULT_ROLES:
            role = RoleModel(**role_data)
            session.add(role)
            session.flush()
            roles_map[role_data["name"]] = role

        # Assign permissions to roles
        for role_name, permission_names in DEFAULT_ROLE_PERMISSIONS.items():
            role = roles_map[role_name]
            for perm_name in permission_names:
                if perm_name in permissions_map:
                    role.permissions.append(permissions_map[perm_name])

        session.commit()

    def _ensure_default_admin(self, session: Session):
        """Create a default admin user if none exists."""
        try:
            admin_user = session.query(UserModel).filter(UserModel.username == "admin").first()
            if admin_user:
                return

            hashed_password = pwd_context.hash("admin123")
            admin_user = UserModel(
                username="admin",
                email="admin@example.com",
                full_name="System Administrator",
                hashed_password=hashed_password,
                is_active=True,
                status="active",
            )
            # Attach admin role
            admin_role = session.query(RoleModel).filter(RoleModel.name == "admin").first()
            if admin_role:
                admin_user.roles.append(admin_role)

            session.add(admin_user)
            session.commit()
            logger.info("Default admin user created (username: admin)")
        except Exception as e:
            logger.error(f"Failed to ensure default admin user: {e}")

    def authenticate_user(
        self, username: str, password: str, ip_address: str = None, user_agent: str = None
    ) -> SecurityContext:
        """Authenticate user and return security context."""
        self._ensure_initialized()
        try:
            with self.db.get_session() as session:
                # Find user by username or email
                user = (
                    session.query(UserModel)
                    .filter(or_(UserModel.username == username, UserModel.email == username))
                    .first()
                )

                if not user:
                    self._log_security_event(
                        session,
                        None,
                        "failed_login",
                        "warning",
                        f"Login attempt with unknown username: {username}",
                        ip_address,
                        user_agent,
                    )
                    raise UserNotFoundError("Invalid username or email")

                # Check if account is locked
                if self._is_account_locked(user):
                    self._log_security_event(
                        session,
                        user.id,
                        "account_locked",
                        "warning",
                        f"Login attempt on locked account: {username}",
                        ip_address,
                        user_agent,
                    )
                    raise AccountLockedError(
                        "Account is temporarily locked due to multiple failed attempts"
                    )

                # Verify password
                if not user.check_password(password):
                    self._handle_failed_login(session, user, ip_address, user_agent)
                    raise InvalidCredentialsError("Invalid password")

                # Check if account is active
                if not user.is_active or user.status != "active":
                    self._log_security_event(
                        session,
                        user.id,
                        "inactive_login",
                        "warning",
                        f"Login attempt on inactive account: {username}",
                        ip_address,
                        user_agent,
                    )
                    raise AccountLockedError("Account is not active")

                # Reset failed login attempts on successful login
                user.failed_login_attempts = 0
                user.last_login = datetime.now(UTC)
                session.commit()

                # Log successful login
                self._log_security_event(
                    session,
                    user.id,
                    "login",
                    "info",
                    f"Successful login: {username}",
                    ip_address,
                    user_agent,
                )

                # Get user permissions
                permissions = self._get_user_permissions(user)
                return SecurityContext(user, permissions)

        except (UserNotFoundError, InvalidCredentialsError, AccountLockedError):
            raise
        except Exception as e:
            logger.error(f"Authentication error for user {username}: {e}")
            raise AuthenticationError("Authentication failed")

    def _is_account_locked(self, user: UserModel) -> bool:
        """Check if user account is locked due to failed attempts."""
        if user.failed_login_attempts >= 5:  # Max 5 attempts
            # Check if lockout period has expired (30 minutes)
            if user.last_login_attempt:
                lockout_duration = timedelta(minutes=30)
                last_attempt = user.last_login_attempt
                if last_attempt.tzinfo is None:
                    last_attempt = last_attempt.replace(tzinfo=UTC)
                if datetime.now(UTC) - last_attempt < lockout_duration:
                    return True
        return False

    def _handle_failed_login(
        self, session: Session, user: UserModel, ip_address: str, user_agent: str
    ):
        """Handle failed login attempt."""
        user.failed_login_attempts += 1
        user.last_login_attempt = datetime.now(UTC)
        session.commit()

        # Log failed login
        self._log_security_event(
            session,
            user.id,
            "failed_login",
            "warning",
            f"Failed login attempt (attempt {user.failed_login_attempts}): {user.username}",
            ip_address,
            user_agent,
        )

        # Log security event for lockout
        if self._is_account_locked(user):
            self._log_security_event(
                session,
                user.id,
                "account_locked",
                "warning",
                f"Account locked due to failed attempts: {user.username}",
                ip_address,
                user_agent,
            )

    def _get_user_permissions(self, user: UserModel) -> List[str]:
        """Get all permissions for a user."""
        permissions = set()
        for role in user.roles:
            for permission in role.permissions:
                permissions.add(permission.name)
        return list(permissions)

    def create_access_token(
        self, user_id: str, permissions: List[str], session_id: str = None
    ) -> str:
        """Create JWT access token."""
        expire = datetime.now(UTC) + timedelta(minutes=self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        exp_ms = int(expire.timestamp() * 1000)
        to_encode = {
            "sub": user_id,
            "permissions": permissions,
            "exp": expire,
            "iat": datetime.now(UTC),
            "type": "access",
            "exp_ms": exp_ms,
        }
        if session_id:
            to_encode["session_id"] = session_id
        return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    def create_refresh_token(self, user_id: str, session_id: str = None) -> str:
        """Create JWT refresh token."""
        expire = datetime.now(UTC) + timedelta(days=self.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode = {"sub": user_id, "exp": expire, "iat": datetime.now(UTC), "type": "refresh"}
        if session_id:
            to_encode["session_id"] = session_id
        return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    def verify_token(self, token: str, token_type: str = "access") -> SecurityContext:
        """Verify JWT token and return security context."""
        self._ensure_initialized()
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            if not user_id:
                raise TokenExpiredError("Invalid token")

            # Check token type
            if payload.get("type") != token_type:
                raise AuthenticationError("Invalid token type")

            # Check expiration
            # Prefer millisecond precision when available
            exp_ms = payload.get("exp_ms")
            if exp_ms is not None:
                now_ms = int(datetime.now(UTC).timestamp() * 1000)
                if now_ms >= int(exp_ms):
                    raise TokenExpiredError("Token has expired")
            else:
                exp = payload.get("exp")
                if exp is not None and datetime.now(UTC).timestamp() >= float(exp):
                    raise TokenExpiredError("Token has expired")

            # Get user from database
            with self.db.get_session() as session:
                user = session.query(UserModel).filter(UserModel.id == user_id).first()
                if not user or not user.is_active:
                    raise UserNotFoundError("User not found or inactive")

                # Get permissions
                permissions = self._get_user_permissions(user)
                session_id = payload.get("session_id")

                return SecurityContext(user, permissions, session_id)

        except JWTError as e:
            logger.error(f"JWT verification failed: {e}")
            raise TokenExpiredError("Invalid or expired token")
        except (AuthenticationError, UserNotFoundError, TokenExpiredError):
            # Propagate expected auth-related errors as-is
            raise
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise AuthenticationError(str(e))

    def create_user_session(
        self, user_id: str, ip_address: str = None, user_agent: str = None
    ) -> Dict[str, str]:
        """Create user session and return tokens."""
        with self.db.get_session() as session:
            user = session.query(UserModel).filter(UserModel.id == user_id).first()
            if not user:
                raise UserNotFoundError("User not found")

            # Create session record
            session_token = generate_secure_token(32)
            refresh_token = generate_secure_token(32)
            expires_at = datetime.now(UTC) + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

            session_record = UserSessionModel(
                user_id=user_id,
                session_token=hash_token(session_token),
                refresh_token=hash_token(refresh_token),
                ip_address=ip_address,
                user_agent=user_agent,
                expires_at=expires_at,
            )

            session.add(session_record)
            session.commit()

            # Get permissions
            permissions = self._get_user_permissions(user)
            access_token = self.create_access_token(user_id, permissions, session_record.id)
            refresh_token_signed = self.create_refresh_token(user_id, session_record.id)

            return {
                "access_token": access_token,
                "refresh_token": refresh_token_signed,
                "token_type": "bearer",
                "expires_in": JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            }

    def refresh_access_token(self, refresh_token: str) -> Dict[str, str]:
        """Refresh access token using refresh token."""
        try:
            payload = jwt.decode(refresh_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            session_id = payload.get("session_id")

            if not user_id or not session_id:
                raise AuthenticationError("Invalid refresh token")

            # Verify session exists and is valid
            with self.db.get_session() as session:
                session_record = (
                    session.query(UserSessionModel)
                    .filter(
                        and_(
                            UserSessionModel.id == session_id,
                            UserSessionModel.user_id == user_id,
                            UserSessionModel.is_active.is_(True),
                            UserSessionModel.expires_at > datetime.now(UTC),
                        )
                    )
                    .first()
                )

                if not session_record:
                    raise AuthenticationError("Invalid or expired session")

                # Update last accessed
                session_record.last_accessed = datetime.now(UTC)
                session.commit()

                # Create new access token
                user = session.query(UserModel).filter(UserModel.id == user_id).first()
                permissions = self._get_user_permissions(user)
                access_token = self.create_access_token(user_id, permissions, session_id)

                return {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "expires_in": JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                }

        except JWTError as e:
            logger.error(f"Refresh token verification failed: {e}")
            raise AuthenticationError("Invalid refresh token")

    def logout(self, user_id: str, session_id: str = None):
        """Logout user and invalidate session."""
        with self.db.get_session() as session:
            # Invalidate session
            if session_id:
                session_record = (
                    session.query(UserSessionModel)
                    .filter(
                        and_(UserSessionModel.id == session_id, UserSessionModel.user_id == user_id)
                    )
                    .first()
                )
                if session_record:
                    session_record.is_active = False
                    session_record.revoked_at = datetime.now(UTC)
                    session.commit()

            # Log logout event
            self._log_security_event(session, user_id, "logout", "info", "User logged out")

    def create_user(
        self, username: str, email: str, password: str, full_name: str, role_names: List[str] = None
    ) -> UserModel:
        """Create new user account."""
        with self.db.get_session() as session:
            # Check if user already exists
            existing_user = (
                session.query(UserModel)
                .filter(or_(UserModel.username == username, UserModel.email == email))
                .first()
            )
            if existing_user:
                raise ValueError("User with this username or email already exists")

            # Hash password using passlib
            hashed_password = pwd_context.hash(password)

            # Create user
            user = UserModel(
                username=username,
                email=email,
                full_name=full_name,
                hashed_password=hashed_password,
                is_active=True,
                status="active",
            )

            # Assign roles
            if role_names:
                roles = session.query(RoleModel).filter(RoleModel.name.in_(role_names)).all()
                user.roles.extend(roles)

            session.add(user)
            session.commit()

            # Log user creation
            self._log_security_event(
                session, user.id, "user_created", "info", f"User created: {username}"
            )

            return user

    def create_api_token(
        self, user_id: str, name: str, scopes: List[str], expires_days: int = 30
    ) -> str:
        """Create API token for user."""
        with self.db.get_session() as session:
            user = session.query(UserModel).filter(UserModel.id == user_id).first()
            if not user:
                raise UserNotFoundError("User not found")

            # Generate token
            token = generate_secure_token(32)
            token_hash = hash_token(token)
            token_prefix = token[:8]
            expires_at = datetime.now(UTC) + timedelta(days=expires_days) if expires_days else None

            # Create API token record
            api_token = APITokenModel(
                user_id=user_id,
                name=name,
                token_hash=token_hash,
                token_prefix=token_prefix,
                scopes=scopes,
                expires_at=expires_at,
            )

            session.add(api_token)
            session.commit()

            return token  # Return raw token (only shown once)

    def verify_api_token(self, token: str) -> SecurityContext:
        """Verify API token and return security context."""
        token_hash = hash_token(token)

        with self.db.get_session() as session:
            api_token = (
                session.query(APITokenModel)
                .filter(
                    and_(
                        APITokenModel.token_hash == token_hash,
                        APITokenModel.is_active.is_(True),
                        or_(
                            APITokenModel.expires_at.is_(None),
                            APITokenModel.expires_at > datetime.now(UTC),
                        ),
                    )
                )
                .first()
            )

            if not api_token:
                raise AuthenticationError("Invalid or expired API token")

            # Update usage statistics
            api_token.last_used = datetime.now(UTC)
            api_token.usage_count += 1
            session.commit()

            # Get user and permissions
            user = session.query(UserModel).filter(UserModel.id == api_token.user_id).first()
            if not user or not user.is_active:
                raise UserNotFoundError("User not found or inactive")

            # Build permissions from scopes
            permissions = self._build_permissions_from_scopes(api_token.scopes)

            return SecurityContext(user, permissions)

    def _build_permissions_from_scopes(self, scopes: List[str]) -> List[str]:
        """Build full permission names from API scopes."""
        # Simple scope to permission mapping
        scope_mapping = {
            "read": ["agent.read", "goals.read", "actions.read", "system.read", "users.read"],
            "write": ["agent.write", "goals.write", "actions.write", "system.write", "users.write"],
            "admin": ["agent.admin", "system.admin", "users.admin"],
        }

        permissions = set()
        for scope in scopes:
            if scope in scope_mapping:
                permissions.update(scope_mapping[scope])
            else:
                # Assume it's a specific permission
                permissions.add(scope)
        # Also include original scopes for compatibility with clients/tests
        permissions.update(scopes)
        return list(permissions)

    def _log_security_event(
        self,
        session: Session,
        user_id: str,
        event_type: str,
        severity: str,
        description: str,
        ip_address: str = None,
        user_agent: str = None,
    ):
        """Log security event."""
        event = AuthSecurityEventModel(
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.add(event)
        session.commit()

    def require_permission(self, security_context: SecurityContext, resource: str, action: str):
        """Require specific permission - raises exception if not granted."""
        if not security_context.has_permission(resource, action):
            raise InsufficientPermissionsError(f"Insufficient permissions: {resource}.{action}")

    def require_admin(self, security_context: SecurityContext):
        """Require admin privileges."""
        security_context.require_admin()


# Global auth service instance
auth_service = AuthService()
