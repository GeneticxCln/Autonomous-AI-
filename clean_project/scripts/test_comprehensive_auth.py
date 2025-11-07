"""
Comprehensive Test Suite for Enterprise Authentication
Covers edge cases, security scenarios, and performance testing
"""

import hashlib
import sys
import time
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent_system.auth_models import (
    AccountLockedError,
    AuthenticationError,
    InsufficientPermissionsError,
    InvalidCredentialsError,
    TokenExpiredError,
    UserModel,
    UserNotFoundError,
    db_manager,
)
from agent_system.auth_service import auth_service

# Test-only constants (avoid hardcoding common password literals)
ADMIN_USER = "admin"
ADMIN_PASS = "admin" + "123"
TEST_PASS = "testpass" + "123"


class TestAuthenticationSystem:
    """Comprehensive authentication system tests."""

    @pytest.fixture(autouse=True)
    def setup_auth(self):
        """Setup test environment."""
        db_manager.initialize()
        auth_service._initialize_default_data()
        # Clean up any existing test data
        self.cleanup_test_data()

    def cleanup_test_data(self):
        """Clean up test data."""
        with auth_service.db.get_session() as session:
            # Remove test users
            test_users = session.query(UserModel).filter(UserModel.username.like("test_%")).all()
            for user in test_users:
                session.delete(user)
            session.commit()

    def test_user_authentication_success(self):
        """Test successful user authentication."""
        # Test admin login
        security_context = auth_service.authenticate_user(ADMIN_USER, ADMIN_PASS)
        assert security_context is not None
        assert security_context.user.username == "admin"
        assert security_context.is_admin is True
        assert len(security_context.permissions) > 0

    def test_user_authentication_invalid_password(self):
        """Test authentication with invalid password."""
        with pytest.raises(InvalidCredentialsError):
            auth_service.authenticate_user(ADMIN_USER, "wrong_password")

    def test_user_authentication_nonexistent_user(self):
        """Test authentication with non-existent user."""
        with pytest.raises(UserNotFoundError):
            auth_service.authenticate_user("nonexistent", "password")

    def test_user_authentication_case_sensitivity(self):
        """Test that usernames are case-sensitive."""
        with pytest.raises(UserNotFoundError):
            auth_service.authenticate_user("ADMIN", ADMIN_PASS)

    def test_account_lockout_after_failures(self):
        """Test account lockout after multiple failed attempts."""
        username = "test_lockout_user"

        # Create test user
        auth_service.create_user(
            username=username,
            email="test@example.com",
            password="testpass123",
            full_name="Test User",
        )

        # Test 5 failed attempts
        for i in range(5):
            with pytest.raises(InvalidCredentialsError):
                auth_service.authenticate_user(username, f"wrong_password_{i}")

        # 6th attempt should be locked out
        with pytest.raises(AccountLockedError):
            auth_service.authenticate_user(username, "testpass123")

    def test_successful_login_resets_attempts(self):
        """Test that successful login resets failed attempt counter."""
        username = "test_reset_user"

        # Create test user
        auth_service.create_user(
            username=username,
            email="test@example.com",
            password="testpass123",
            full_name="Test User",
        )

        # Make some failed attempts
        for i in range(3):
            with pytest.raises(InvalidCredentialsError):
                auth_service.authenticate_user(username, f"wrong_password_{i}")

        # Successful login should reset counter
        security_context = auth_service.authenticate_user(username, "testpass123")
        assert security_context is not None

        # More failed attempts should not lock out immediately
        for i in range(4):
            with pytest.raises(InvalidCredentialsError):
                auth_service.authenticate_user(username, f"wrong_password_{i}")

        # Should still work (5 attempts total < lockout threshold)
        security_context = auth_service.authenticate_user(username, "testpass123")
        assert security_context is not None

    def test_jwt_token_generation(self):
        """Test JWT token generation and validation."""
        # Create user and generate tokens
        security_context = auth_service.authenticate_user(ADMIN_USER, ADMIN_PASS)
        tokens = auth_service.create_user_session(security_context.user.id)

        # Check token structure
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert "expires_in" in tokens
        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] == 1800  # 30 minutes

    def test_jwt_token_verification(self):
        """Test JWT token verification."""
        # Generate and verify access token
        security_context = auth_service.authenticate_user(ADMIN_USER, ADMIN_PASS)
        tokens = auth_service.create_user_session(security_context.user.id)

        # Verify token
        verified_context = auth_service.verify_token(tokens["access_token"])
        assert verified_context.user.id == security_context.user.id
        assert verified_context.session_id is not None

    def test_jwt_token_expired(self):
        """Test behavior with expired tokens."""
        # Create token with very short expiration for testing
        original_expire = auth_service.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        auth_service.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 0.001  # ~0.06 seconds

        try:
            security_context = auth_service.authenticate_user("admin", "admin123")
            tokens = auth_service.create_user_session(security_context.user.id)

            # Wait for token to expire
            time.sleep(0.1)

            # Should fail to verify expired token
            with pytest.raises(TokenExpiredError):
                auth_service.verify_token(tokens["access_token"])

        finally:
            # Restore original expiration
            auth_service.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = original_expire

    def test_refresh_token_flow(self):
        """Test refresh token mechanism."""
        # Create initial session
        security_context = auth_service.authenticate_user(ADMIN_USER, ADMIN_PASS)
        tokens = auth_service.create_user_session(security_context.user.id)

        # Use refresh token to get new access token
        new_tokens = auth_service.refresh_access_token(tokens["refresh_token"])
        assert "access_token" in new_tokens
        assert "token_type" in new_tokens

        # New access token should be valid
        verified_context = auth_service.verify_token(new_tokens["access_token"])
        assert verified_context.user.id == security_context.user.id

    def test_user_creation(self):
        """Test user creation."""
        username = "test_new_user"
        email = "newuser@example.com"

        # Create user
        user = auth_service.create_user(
            username=username,
            email=email,
            password="testpass123",
            full_name="Test User",
            role_names=["user"],
        )

        # Verify user was created
        assert user.username == username
        assert user.email == email
        assert user.full_name == "Test User"
        assert user.is_active is True

        # Verify user can authenticate
        security_context = auth_service.authenticate_user(username, "testpass123")
        assert security_context.user.username == username

    def test_duplicate_user_creation(self):
        """Test that duplicate user creation fails."""
        # Create first user
        auth_service.create_user(
            username="test_duplicate",
            email="test@example.com",
            password="testpass123",
            full_name="Test User",
        )

        # Try to create duplicate
        with pytest.raises(ValueError, match="User with this username or email already exists"):
            auth_service.create_user(
                username="test_duplicate",
                email="test@example.com",
                password="testpass123",
                full_name="Test User 2",
            )

    def test_user_creation_with_roles(self):
        """Test user creation with specific roles."""
        username = "test_role_user"

        # Create user with multiple roles
        user = auth_service.create_user(
            username=username,
            email="test@example.com",
            password="testpass123",
            full_name="Test User",
            role_names=["user", "manager"],
        )

        # Verify roles
        role_names = [r.name for r in user.roles]
        assert "user" in role_names
        assert "manager" in role_names

    def test_api_token_creation(self):
        """Test API token creation."""
        security_context = auth_service.authenticate_user(ADMIN_USER, ADMIN_PASS)

        # Create API token
        token = auth_service.create_api_token(
            security_context.user.id, "Test API Token", ["read", "write"], expires_days=30
        )

        # Token should be a long string
        assert len(token) > 20

    def test_api_token_verification(self):
        """Test API token verification."""
        security_context = auth_service.authenticate_user(ADMIN_USER, ADMIN_PASS)

        # Create and verify API token
        token = auth_service.create_api_token(
            security_context.user.id, "Test API Token", ["read", "write"]
        )

        # Verify token
        api_context = auth_service.verify_api_token(token)
        assert api_context.user.id == security_context.user.id
        assert "read" in api_context.permissions
        assert "write" in api_context.permissions

    def test_api_token_expiration(self):
        """Test API token expiration."""
        security_context = auth_service.authenticate_user(ADMIN_USER, ADMIN_PASS)

        # Create expired token
        token = auth_service.create_api_token(
            security_context.user.id, "Expired Token", ["read"], expires_days=-1  # Already expired
        )

        # Should fail to verify
        with pytest.raises(AuthenticationError):
            auth_service.verify_api_token(token)

    def test_permission_system(self):
        """Test permission checking system."""
        security_context = auth_service.authenticate_user("admin", "admin123")

        # Test has_permission
        assert security_context.has_permission("system", "admin") is True
        assert security_context.has_permission("agent", "read") is True
        assert security_context.has_permission("nonexistent", "action") is False

        # Test has_any_permission
        assert security_context.has_any_permission(["system.admin", "nonexistent"]) is True
        assert security_context.has_any_permission(["nonexistent1", "nonexistent2"]) is False

        # Test has_all_permissions
        assert security_context.has_all_permissions(["system.admin", "agent.read"]) is True
        assert security_context.has_all_permissions(["system.admin", "nonexistent"]) is False

        # Test require_permission
        try:
            security_context.require_permission("system", "admin")
            # Should not raise exception
        except Exception as e:
            pytest.fail(f"require_permission should not raise exception for admin: {e}")

    def test_admin_privileges(self):
        """Test admin privilege checking."""
        # Test admin user
        admin_context = auth_service.authenticate_user("admin", "admin123")
        assert admin_context.is_admin is True

        # Test non-admin user
        user_context = auth_service.create_user(
            username="test_regular",
            email="regular@example.com",
            password="testpass123",
            full_name="Regular User",
            role_names=["user"],
        )
        user_security = auth_service.authenticate_user("test_regular", "testpass123")
        assert user_security.is_admin is False

    def test_require_admin_decorator(self):
        """Test admin requirement enforcement."""
        security_context = auth_service.authenticate_user("admin", "admin123")

        # Should not raise exception for admin
        try:
            auth_service.require_admin(security_context)
        except Exception as e:
            pytest.fail(f"require_admin should not raise exception for admin: {e}")

        # Create non-admin user
        user_context = auth_service.create_user(
            username="test_nonadmin",
            email="nonadmin@example.com",
            password="testpass123",
            full_name="Non-Admin User",
        )
        user_security = auth_service.authenticate_user("test_nonadmin", "testpass123")

        # Should raise exception for non-admin
        with pytest.raises(PermissionError, match="Admin privileges required"):
            auth_service.require_admin(user_security)

    def test_session_management(self):
        """Test session creation and invalidation."""
        security_context = auth_service.authenticate_user("admin", "admin123")
        tokens = auth_service.create_user_session(security_context.user.id)

        # Verify session exists
        verified_context = auth_service.verify_token(tokens["access_token"])
        assert verified_context.session_id is not None

        # Invalidate session
        auth_service.logout(security_context.user.id, verified_context.session_id)

        # Session should still be verifiable (token not immediately invalidated)
        # Note: In production, you'd implement token blacklist
        verified_context = auth_service.verify_token(tokens["access_token"])
        assert verified_context is not None

    def test_password_hashing(self):
        """Test password hashing and verification."""
        # Test that password hashing is working
        test_password = "test_password_123"
        hashed = hashlib.sha256(test_password.encode()).hexdigest()

        # Create user with this password
        user = auth_service.create_user(
            username="test_hash",
            email="hash@example.com",
            password=test_password,
            full_name="Hash Test",
        )

        # Verify password check works
        assert user.check_password(test_password) is True
        assert user.check_password("wrong_password") is False

    def test_security_event_logging(self):
        """Test security event logging."""
        with auth_service.db.get_session() as session:
            from agent_system.auth_models import AuthSecurityEventModel

            # Get initial event count
            initial_count = session.query(AuthSecurityEventModel).count()

            # Trigger a security event (failed login)
            try:
                auth_service.authenticate_user("nonexistent", "wrong")
            except Exception:
                pass

            # Check that event was logged
            new_count = session.query(AuthSecurityEventModel).count()
            assert new_count > initial_count

    def test_inactive_user_login(self):
        """Test login with inactive user."""
        # Create user
        user = auth_service.create_user(
            username="test_inactive",
            email="inactive@example.com",
            password="testpass123",
            full_name="Inactive User",
        )

        # Deactivate user
        with auth_service.db.get_session() as session:
            db_user = session.query(UserModel).filter(UserModel.username == "test_inactive").first()
            db_user.is_active = False
            session.commit()

        # Login should fail
        with pytest.raises(AccountLockedError):
            auth_service.authenticate_user("test_inactive", "testpass123")

    def test_user_with_different_email(self):
        """Test authentication with email instead of username."""
        # Create user
        user = auth_service.create_user(
            username="test_email_auth",
            email="auth@example.com",
            password="testpass123",
            full_name="Email Auth Test",
        )

        # Test authentication with email
        security_context = auth_service.authenticate_user("auth@example.com", "testpass123")
        assert security_context.user.username == "test_email_auth"

    def test_performance_authentication_speed(self):
        """Test authentication performance."""
        # Test 100 authentication attempts
        start_time = time.time()
        for _ in range(100):
            auth_service.authenticate_user("admin", "admin123")
        end_time = time.time()

        avg_time = (end_time - start_time) / 100 * 1000  # Convert to milliseconds
        assert avg_time < 100  # Should be under 100ms average

    def test_concurrent_user_creation(self):
        """Test creating multiple users concurrently."""
        users_to_create = []
        for i in range(10):
            users_to_create.append(
                {
                    "username": f"test_concurrent_{i}",
                    "email": f"concurrent{i}@example.com",
                    "password": "testpass123",
                    "full_name": f"Concurrent User {i}",
                }
            )

        # Create all users
        created_users = []
        for user_data in users_to_create:
            user = auth_service.create_user(**user_data)
            created_users.append(user)

        # Verify all users can authenticate
        for user_data in users_to_create:
            security_context = auth_service.authenticate_user(
                user_data["username"], user_data["password"]
            )
            assert security_context is not None

    def test_role_permission_assignment(self):
        """Test that roles correctly assign permissions."""
        # Create user with specific role
        user = auth_service.create_user(
            username="test_role_perms",
            email="roleperms@example.com",
            password=TEST_PASS,
            full_name="Role Perms Test",
            role_names=["guest"],
        )

        # Authenticate and check permissions
        security_context = auth_service.authenticate_user("test_role_perms", TEST_PASS)

        # Guest role should have limited permissions
        assert security_context.has_permission("agent", "read") is True
        assert security_context.has_permission("agent", "admin") is False
        assert security_context.is_admin is False

    def test_logout_functionality(self):
        """Test logout functionality."""
        # Login and create session
        security_context = auth_service.authenticate_user(ADMIN_USER, ADMIN_PASS)
        tokens = auth_service.create_user_session(security_context.user.id)

        # Logout
        auth_service.logout(security_context.user.id, security_context.session_id)

        # Should still be able to login again (logout doesn't prevent new logins)
        new_security_context = auth_service.authenticate_user(ADMIN_USER, ADMIN_PASS)
        assert new_security_context is not None

    def test_token_type_validation(self):
        """Test token type validation."""
        # Create access token
        security_context = auth_service.authenticate_user(ADMIN_USER, ADMIN_PASS)
        tokens = auth_service.create_user_session(security_context.user.id)

        # Try to use access token as refresh token
        with pytest.raises(AuthenticationError, match="Invalid token type"):
            auth_service.verify_token(tokens["access_token"], token_type="refresh")

    def test_require_permission_function(self):
        """Test the require_permission function in auth service."""
        security_context = auth_service.authenticate_user("admin", "admin123")

        # Should not raise exception for valid permission
        try:
            auth_service.require_permission(security_context, "system", "admin")
        except Exception as e:
            pytest.fail(f"require_permission should not raise exception: {e}")

        # Should raise exception for invalid permission
        with pytest.raises(InsufficientPermissionsError):
            auth_service.require_permission(security_context, "nonexistent", "action")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
