"""
API Endpoints Test Suite
Comprehensive testing of FastAPI authentication and agent operation endpoints
"""

import sys
import time
from pathlib import Path
from typing import Dict

import requests

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent_system.auth_models import db_manager


class APITestClient:
    """Test client for API endpoints."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
        self.user_id = None

    def login(self, username: str, password: str) -> bool:
        """Login and store tokens."""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"username": username, "password": password},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.access_token = data["data"]["access_token"]
                    self.refresh_token = data["data"]["refresh_token"]
                    self.user_id = data["data"]["user"]["id"]
                    return True
            return False
        except Exception as e:
            print(f"Login failed: {e}")
            return False

    def auth_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    def test_authentication_endpoints(self) -> bool:
        """Test authentication endpoints."""
        print("\n🔐 Testing Authentication Endpoints")
        print("=" * 50)

        # Test login
        print("Testing login...")
        if not self.login("admin", "admin123"):
            print("❌ Login failed")
            return False
        print("✅ Login successful")

        # Test get current user
        print("Testing get current user...")
        try:
            response = requests.get(f"{self.base_url}/api/v1/auth/me", headers=self.auth_headers())
            if response.status_code == 200 and response.json().get("success"):
                user_data = response.json()["data"]
                print(f"✅ Current user: {user_data['username']} ({user_data['roles']})")
            else:
                print("❌ Get current user failed")
                return False
        except Exception as e:
            print(f"❌ Get current user error: {e}")
            return False

        # Test token refresh
        print("Testing token refresh...")
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/refresh", json={"refresh_token": self.refresh_token}
            )
            if response.status_code == 200 and response.json().get("success"):
                new_token = response.json()["data"]["access_token"]
                self.access_token = new_token
                print("✅ Token refresh successful")
            else:
                print("❌ Token refresh failed")
                return False
        except Exception as e:
            print(f"❌ Token refresh error: {e}")
            return False

        return True

    def test_agent_endpoints(self) -> bool:
        """Test agent operation endpoints."""
        print("\n🤖 Testing Agent Operation Endpoints")
        print("=" * 50)

        # Test create agent
        print("Testing agent creation...")
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/agents",
                headers=self.auth_headers(),
                json={
                    "name": "Test Agent",
                    "description": "Test agent for API validation",
                    "goals": ["Test goal 1", "Test goal 2"],
                    "memory_capacity": 1000,
                },
            )

            if response.status_code == 201 and response.json().get("success"):
                agent_data = response.json()["data"]
                agent_id = agent_data["id"]
                print(f"✅ Agent created: {agent_data['name']} (ID: {agent_id})")
            else:
                print(f"❌ Agent creation failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Agent creation error: {e}")
            return False

        # Test list agents
        print("Testing agent listing...")
        try:
            response = requests.get(f"{self.base_url}/api/v1/agents", headers=self.auth_headers())
            if response.status_code == 200 and response.json().get("success"):
                agents = response.json()["data"]
                print(f"✅ Listed {len(agents)} agents")
            else:
                print("❌ Agent listing failed")
                return False
        except Exception as e:
            print(f"❌ Agent listing error: {e}")
            return False

        # Test get specific agent
        print("Testing agent details...")
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/agents/{agent_id}", headers=self.auth_headers()
            )
            if response.status_code == 200 and response.json().get("success"):
                agent_details = response.json()["data"]
                print(f"✅ Agent details retrieved: {agent_details['name']}")
            else:
                print("❌ Agent details failed")
                return False
        except Exception as e:
            print(f"❌ Agent details error: {e}")
            return False

        # Test agent execution
        print("Testing agent execution...")
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/agents/{agent_id}/execute", headers=self.auth_headers()
            )
            if response.status_code == 200 and response.json().get("success"):
                execution_data = response.json()["data"]
                print(f"✅ Agent execution started: {execution_data['status']}")
            else:
                print("❌ Agent execution failed")
                return False
        except Exception as e:
            print(f"❌ Agent execution error: {e}")
            return False

        return True

    def test_goal_endpoints(self) -> bool:
        """Test goal management endpoints."""
        print("\n🎯 Testing Goal Management Endpoints")
        print("=" * 50)

        # Test create goal
        print("Testing goal creation...")
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/goals",
                headers=self.auth_headers(),
                json={
                    "title": "Test Goal",
                    "description": "Test goal for API validation",
                    "priority": 5,
                },
            )

            if response.status_code == 201 and response.json().get("success"):
                goal_data = response.json()["data"]
                goal_id = goal_data["id"]
                print(f"✅ Goal created: {goal_data['title']} (ID: {goal_id})")
            else:
                print(f"❌ Goal creation failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Goal creation error: {e}")
            return False

        # Test list goals
        print("Testing goal listing...")
        try:
            response = requests.get(f"{self.base_url}/api/v1/goals", headers=self.auth_headers())
            if response.status_code == 200 and response.json().get("success"):
                goals = response.json()["data"]
                print(f"✅ Listed {len(goals)} goals")
            else:
                print("❌ Goal listing failed")
                return False
        except Exception as e:
            print(f"❌ Goal listing error: {e}")
            return False

        return True

    def test_user_management(self) -> bool:
        """Test user management endpoints."""
        print("\n👥 Testing User Management Endpoints")
        print("=" * 50)

        # Test create user
        print("Testing user creation...")
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/users",
                headers=self.auth_headers(),
                json={
                    "username": "testuser",
                    "email": "test@example.com",
                    "full_name": "Test User",
                    "password": "testpass123",
                    "role_names": ["user"],
                },
            )

            if response.status_code == 201 and response.json().get("success"):
                user_data = response.json()["data"]
                user_id = user_data["id"]
                print(f"✅ User created: {user_data['username']} (ID: {user_id})")
            else:
                print(f"❌ User creation failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ User creation error: {e}")
            return False

        # Test list users
        print("Testing user listing...")
        try:
            response = requests.get(f"{self.base_url}/api/v1/users", headers=self.auth_headers())
            if response.status_code == 200 and response.json().get("success"):
                users = response.json()["data"]
                print(f"✅ Listed {len(users)} users")
            else:
                print("❌ User listing failed")
                return False
        except Exception as e:
            print(f"❌ User listing error: {e}")
            return False

        return True

    def test_api_token_management(self) -> bool:
        """Test API token management."""
        print("\n🔑 Testing API Token Management")
        print("=" * 50)

        # Test create API token
        print("Testing API token creation...")
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/api-tokens",
                headers=self.auth_headers(),
                json={"name": "Test API Token", "scopes": ["read", "write"], "expires_days": 30},
            )

            if response.status_code == 201 and response.json().get("success"):
                token_data = response.json()["data"]
                api_token = token_data["token"]
                print(f"✅ API token created: {token_data['prefix']}...")
                print(f"   Full token: {api_token}")
            else:
                print(f"❌ API token creation failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ API token creation error: {e}")
            return False

        # Test list API tokens
        print("Testing API token listing...")
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/api-tokens", headers=self.auth_headers()
            )
            if response.status_code == 200 and response.json().get("success"):
                tokens = response.json()["data"]
                print(f"✅ Listed {len(tokens)} API tokens")
            else:
                print("❌ API token listing failed")
                return False
        except Exception as e:
            print(f"❌ API token listing error: {e}")
            return False

        return True

    def test_system_endpoints(self) -> bool:
        """Test system information endpoints."""
        print("\n🔧 Testing System Endpoints")
        print("=" * 50)

        # Test health check
        print("Testing health check...")
        try:
            response = requests.get(f"{self.base_url}/health")
            if response.status_code == 200:
                health = response.json()
                print(f"✅ System health: {health['status']}")
            else:
                print("❌ Health check failed")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False

        # Test system info
        print("Testing system info...")
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/system/info", headers=self.auth_headers()
            )
            if response.status_code == 200 and response.json().get("success"):
                system_info = response.json()["data"]
                print(
                    f"✅ System info retrieved: {system_info['users']} users, {system_info['agents']} agents"
                )
            else:
                print("❌ System info failed")
                return False
        except Exception as e:
            print(f"❌ System info error: {e}")
            return False

        return True

    def test_logout(self) -> bool:
        """Test logout functionality."""
        print("\n🚪 Testing Logout")
        print("=" * 50)

        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/logout", headers=self.auth_headers()
            )
            if response.status_code == 200 and response.json().get("success"):
                print("✅ Logout successful")
                self.access_token = None
                self.refresh_token = None
                return True
            else:
                print("❌ Logout failed")
                return False
        except Exception as e:
            print(f"❌ Logout error: {e}")
            return False


def wait_for_api(base_url: str = "http://127.0.0.1:8000", timeout: int = 30) -> bool:
    """Wait for API to be ready."""
    print(f"⏳ Waiting for API to be ready at {base_url}...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{base_url}/health", timeout=1)
            if response.status_code == 200:
                print("✅ API is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)

    print("❌ API not ready within timeout")
    return False


def run_api_tests():
    """Run comprehensive API tests."""
    print("🧪 API Endpoints Test Suite")
    print("=" * 50)

    # Initialize database
    try:
        db_manager.initialize()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return

    # Wait for API server
    if not wait_for_api():
        print("❌ Cannot proceed with tests - API server not available")
        return

    # Create test client
    client = APITestClient()

    # Run test suites
    test_suites = [
        ("Authentication", client.test_authentication_endpoints),
        ("Agent Operations", client.test_agent_endpoints),
        ("Goal Management", client.test_goal_endpoints),
        ("User Management", client.test_user_management),
        ("API Token Management", client.test_api_token_management),
        ("System Endpoints", client.test_system_endpoints),
        ("Logout", client.test_logout),
    ]

    results = {}
    for suite_name, test_func in test_suites:
        try:
            results[suite_name] = test_func()
        except Exception as e:
            print(f"❌ {suite_name} suite failed with error: {e}")
            results[suite_name] = False

    # Print summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for suite_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{suite_name:<25} {status}")

    print(f"\nTotal: {passed}/{total} test suites passed")

    if passed == total:
        print("🎉 All API tests passed successfully!")
        print("✅ Authentication system working")
        print("✅ Agent operations working")
        print("✅ Goal management working")
        print("✅ User management working")
        print("✅ API token system working")
        print("✅ System endpoints working")
    else:
        print("❌ Some tests failed - check logs above")

    return passed == total


if __name__ == "__main__":
    run_api_tests()
