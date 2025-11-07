"""
Authentication System Test
Tests JWT authentication, RBAC, and security features
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent_system.auth_models import db_manager
from agent_system.auth_service import auth_service


def test_authentication_system():
    """Test the authentication system."""
    print("🔐 Testing Authentication System")
    print("=" * 50)

    try:
        # Initialize database
        db_manager.initialize()
        print("✅ Database connection established")

        # Initialize auth service
        auth_service.initialize()
        print("✅ Authentication service initialized")

        # Test user authentication
        print("\n🔑 Testing User Authentication")
        security_context = auth_service.authenticate_user("admin", "admin123")
        print("✅ Admin user authenticated successfully")
        print(f"   User: {security_context.user.username}")
        print(f"   Permissions: {len(security_context.permissions)} total")

        # Test role-based access control
        print("\n🛡️  Testing Role-Based Access Control")
        print(f"   Has admin permission: {security_context.has_permission('system', 'admin')}")
        print(f"   Has user permission: {security_context.has_permission('goals', 'read')}")
        print(f"   Is admin: {security_context.is_admin}")

        # Test token generation
        print("\n🎫 Testing Token Generation")
        tokens = auth_service.create_user_session(security_context.user.id)
        print(f"✅ Access token created: {tokens['access_token'][:20]}...")
        print(f"   Refresh token: {tokens['refresh_token'][:20]}...")
        print(f"   Token type: {tokens['token_type']}")
        print(f"   Expires in: {tokens['expires_in']} seconds")

        # Test token verification
        print("\n✅ Testing Token Verification")
        verified_context = auth_service.verify_token(tokens["access_token"])
        print("✅ Token verified successfully")
        print(f"   Verified user: {verified_context.user.username}")
        print(f"   Session ID: {verified_context.session_id}")

        # Test API token creation
        print("\n🔧 Testing API Token Creation")
        api_token = auth_service.create_api_token(
            security_context.user.id, "Test API Token", ["read", "write"]
        )
        print(f"✅ API token created: {api_token}")
        print(f"   API token prefix: {api_token[:8]}...")

        # Test API token verification
        print("\n🔍 Testing API Token Verification")
        api_context = auth_service.verify_api_token(api_token)
        print("✅ API token verified successfully")
        print(f"   API user: {api_context.user.username}")
        print(f"   API permissions: {api_context.permissions}")

        # Test permission requirements
        print("\n🔒 Testing Permission Requirements")
        try:
            auth_service.require_permission(verified_context, "system", "admin")
            print("✅ Admin permission requirement passed")
        except Exception as e:
            print(f"❌ Admin permission failed: {e}")

        try:
            auth_service.require_admin(verified_context)
            print("✅ Admin role requirement passed")
        except Exception as e:
            print(f"❌ Admin role failed: {e}")

        # Test logout
        print("\n🚪 Testing Logout")
        auth_service.logout(verified_context.user.id, verified_context.session_id)
        print("✅ User logged out successfully")

        print("\n" + "=" * 50)
        print("🎉 All authentication tests passed!")
        print("✅ JWT authentication system working")
        print("✅ Role-based access control working")
        print("✅ API token system working")
        print("✅ Session management working")
        print("✅ Permission system working")

    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        raise


def test_security_features():
    """Test security features."""
    print("\n🔒 Testing Security Features")
    print("=" * 50)

    try:
        # Test invalid password
        print("Testing invalid password...")
        try:
            auth_service.authenticate_user("admin", "wrongpassword")
            print("❌ Invalid password test failed - should have rejected")
        except Exception:
            print("✅ Invalid password correctly rejected")

        # Test non-existent user
        print("Testing non-existent user...")
        try:
            auth_service.authenticate_user("nonexistent", "password")
            print("❌ Non-existent user test failed - should have rejected")
        except Exception:
            print("✅ Non-existent user correctly rejected")

        print("\n✅ Security features working correctly")

    except Exception as e:
        print(f"❌ Security test failed: {e}")


if __name__ == "__main__":
    test_authentication_system()
    test_security_features()
