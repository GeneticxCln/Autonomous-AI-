"""
Integration Tests for Enterprise Authentication System
Tests complete workflows and identifies integration issues
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient

from agent_system.auth_models import db_manager
from agent_system.auth_service import auth_service
from agent_system.fastapi_app import app


def test_complete_authentication_workflow():
    """Test complete authentication workflow."""
    print("\n🧪 Testing Complete Authentication Workflow")
    print("=" * 50)

    # Initialize system
    db_manager.initialize()
    auth_service._initialize_default_data()

    # Test 1: User Authentication
    print("\n1. Testing user authentication...")
    try:
        security_context = auth_service.authenticate_user("admin", "admin123")
        print("✅ Admin authentication successful")
    except Exception as e:
        print(f"❌ Admin authentication failed: {e}")
        return False

    # Test 2: Session Creation
    print("\n2. Testing session creation...")
    try:
        tokens = auth_service.create_user_session(security_context.user.id)
        print("✅ Session tokens created")
        print(f"   Access token: {tokens['access_token'][:30]}...")
        print(f"   Refresh token: {tokens['refresh_token'][:30]}...")
    except Exception as e:
        print(f"❌ Session creation failed: {e}")
        return False

    # Test 3: Token Verification
    print("\n3. Testing token verification...")
    try:
        verified_context = auth_service.verify_token(tokens["access_token"])
        print("✅ Token verification successful")
        print(f"   Verified user: {verified_context.user.username}")
    except Exception as e:
        print(f"❌ Token verification failed: {e}")
        return False

    # Test 4: API Token Creation
    print("\n4. Testing API token creation...")
    try:
        api_token = auth_service.create_api_token(
            security_context.user.id, "Integration Test Token", ["read", "write"], expires_days=30
        )
        print("✅ API token created")
        print(f"   Token: {api_token[:20]}...")
    except Exception as e:
        print(f"❌ API token creation failed: {e}")
        return False

    # Test 5: API Token Verification
    print("\n5. Testing API token verification...")
    try:
        api_context = auth_service.verify_api_token(api_token)
        print("✅ API token verification successful")
        print(f"   API user: {api_context.user.username}")
    except Exception as e:
        print(f"❌ API token verification failed: {e}")
        return False

    # Test 6: Permission System
    print("\n6. Testing permission system...")
    try:
        assert security_context.has_permission("system", "admin")
        assert security_context.has_permission("agent", "read")
        assert not security_context.has_permission("nonexistent", "action")
        print("✅ Permission system working")
    except Exception as e:
        print(f"❌ Permission system failed: {e}")
        return False

    # Test 7: User Management
    print("\n7. Testing user management...")
    try:
        # Clean up any existing test user first
        with auth_service.db.get_session() as session:
            from agent_system.auth_models import UserModel

            existing_user = (
                session.query(UserModel).filter(UserModel.username == "integration_test").first()
            )
            if existing_user:
                session.delete(existing_user)
                session.commit()

        auth_service.create_user(
            username="integration_test",
            email="integration@example.com",
            password="test123",
            full_name="Integration Test User",
            role_names=["user"],
        )
        print("✅ New user created")

        # Test new user authentication
        auth_service.authenticate_user("integration_test", "test123")
        print("✅ New user can authenticate")
    except Exception as e:
        print(f"❌ User management failed: {e}")
        return False

    # Test 8: Security Events
    print("\n8. Testing security event logging...")
    try:
        with auth_service.db.get_session() as session:
            from agent_system.auth_models import AuthSecurityEventModel

            events = session.query(AuthSecurityEventModel).count()
            print(f"✅ Security events logged: {events} events")
    except Exception as e:
        print(f"❌ Security events failed: {e}")
        return False

    # Test 9: Logout
    print("\n9. Testing logout functionality...")
    try:
        auth_service.logout(security_context.user.id, security_context.session_id)
        print("✅ Logout successful")
    except Exception as e:
        print(f"❌ Logout failed: {e}")
        return False

    # Test 10: Token Refresh
    print("\n10. Testing token refresh...")
    try:
        new_tokens = auth_service.refresh_access_token(tokens["refresh_token"])
        print("✅ Token refresh successful")
        print(f"   New access token: {new_tokens['access_token'][:30]}...")
    except Exception as e:
        print(f"❌ Token refresh failed: {e}")
        return False

    print("\n🎉 All integration tests passed!")
    return True


def test_fastapi_integration():
    """Test FastAPI integration."""
    print("\n🌐 Testing FastAPI Integration")
    print("=" * 50)

    try:
        # Create test client
        client = TestClient(app)

        # Test health endpoint
        print("\n1. Testing health endpoint...")
        response = client.get("/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")

        if response.status_code == 200:
            print("✅ Health endpoint working")
        else:
            print("❌ Health endpoint failed")
            return False

        # Test root endpoint
        print("\n2. Testing root endpoint...")
        response = client.get("/")
        if response.status_code == 200:
            print("✅ Root endpoint working")
        else:
            print("❌ Root endpoint failed")
            return False

        # Test API info endpoint
        print("\n3. Testing API info endpoint...")
        response = client.get("/api/info")
        if response.status_code == 200:
            print("✅ API info endpoint working")
        else:
            print("❌ API info endpoint failed")
            return False

        print("\n🎉 FastAPI integration tests passed!")
        return True

    except Exception as e:
        print(f"❌ FastAPI integration failed: {e}")
        return False


def test_database_operations():
    """Test database operations."""
    print("\n💾 Testing Database Operations")
    print("=" * 50)

    try:
        # Test database connection
        with auth_service.db.get_session() as session:
            # Test basic query
            from agent_system.auth_models import PermissionModel, RoleModel, UserModel

            users = session.query(UserModel).count()
            roles = session.query(RoleModel).count()
            permissions = session.query(PermissionModel).count()

            print("✅ Database connected")
            print(f"   Users: {users}")
            print(f"   Roles: {roles}")
            print(f"   Permissions: {permissions}")

        return True

    except Exception as e:
        print(f"❌ Database operations failed: {e}")
        return False


def test_error_handling():
    """Test error handling scenarios."""
    print("\n🚨 Testing Error Handling")
    print("=" * 50)

    try:
        # Test invalid login
        print("\n1. Testing invalid login...")
        try:
            auth_service.authenticate_user("admin", "wrong_password")
            print("❌ Invalid login should have failed")
            return False
        except Exception:
            print("✅ Invalid login correctly rejected")

        # Test non-existent user
        print("\n2. Testing non-existent user...")
        try:
            auth_service.authenticate_user("nonexistent", "password")
            print("❌ Non-existent user should have failed")
            return False
        except Exception:
            print("✅ Non-existent user correctly rejected")

        # Test invalid token
        print("\n3. Testing invalid token...")
        try:
            auth_service.verify_token("invalid_token")
            print("❌ Invalid token should have failed")
            return False
        except Exception:
            print("✅ Invalid token correctly rejected")

        print("\n🎉 Error handling tests passed!")
        return True

    except Exception as e:
        print(f"❌ Error handling tests failed: {e}")
        return False


def test_performance_requirements():
    """Test performance requirements."""
    print("\n⚡ Testing Performance Requirements")
    print("=" * 50)

    try:
        # Test authentication speed
        print("\n1. Testing authentication speed...")
        auth_times = []
        for i in range(10):
            start_time = time.time()
            auth_service.authenticate_user("admin", "admin123")
            end_time = time.time()
            auth_times.append((end_time - start_time) * 1000)  # Convert to ms

        avg_time = sum(auth_times) / len(auth_times)
        max_time = max(auth_times)

        print("✅ Authentication performance:")
        print(f"   Average: {avg_time:.2f}ms")
        print(f"   Maximum: {max_time:.2f}ms")

        if avg_time > 100:  # Should be under 100ms average
            print("⚠️  Authentication might be slow for production")
        else:
            print("✅ Authentication meets performance requirements")

        # Test token generation speed
        print("\n2. Testing token generation speed...")
        security_context = auth_service.authenticate_user("admin", "admin123")

        token_times = []
        for i in range(10):
            start_time = time.time()
            auth_service.create_user_session(security_context.user.id)
            end_time = time.time()
            token_times.append((end_time - start_time) * 1000)

        avg_token_time = sum(token_times) / len(token_times)
        print(f"✅ Token generation average: {avg_token_time:.2f}ms")

        return True

    except Exception as e:
        print(f"❌ Performance tests failed: {e}")
        return False


def run_integration_tests():
    """Run all integration tests."""
    print("🚀 RUNNING COMPREHENSIVE INTEGRATION TESTS")
    print("=" * 60)

    test_results = {
        "authentication_workflow": test_complete_authentication_workflow(),
        "fastapi_integration": test_fastapi_integration(),
        "database_operations": test_database_operations(),
        "error_handling": test_error_handling(),
        "performance_requirements": test_performance_requirements(),
    }

    print("\n" + "=" * 60)
    print("📊 INTEGRATION TEST RESULTS")
    print("=" * 60)

    passed = 0
    total = len(test_results)

    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title():<30} {status}")
        if result:
            passed += 1

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
        print("✅ System is ready for production")
    else:
        print(f"\n❌ {total - passed} tests failed")
        print("🔧 System needs fixes before production")

    return passed == total


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
