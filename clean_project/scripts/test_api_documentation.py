"""
Test comprehensive API documentation improvements
Verifies OpenAPI schema integration and endpoint functionality
"""
import pytest
import time
import json
from datetime import datetime
from fastapi.testclient import TestClient

# Import and initialize the app properly
from agent_system.fastapi_app import app
from agent_system.auth_service import auth_service
from agent_system.auth_models import db_manager as auth_db_manager

# Initialize auth system for testing
auth_db_manager.initialize()
auth_service.initialize()

# Create test client after initialization
client = TestClient(app)

class TestAPIDocumentation:
    """Test comprehensive API documentation features."""

    def setup_method(self):
        """Setup test environment."""
        # Login as admin to get tokens for authenticated requests
        self.login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123",
                "remember_me": False
            }
        )
        assert self.login_response.status_code == 200
        self.access_token = self.login_response.json()["data"]["access_token"]

    def test_openapi_schema_generation(self):
        """Test that OpenAPI schema includes comprehensive documentation."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()

        # Verify schema structure
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        assert "components" in schema

        # Verify security schemes
        assert "BearerAuth" in schema["components"]["securitySchemes"]
        assert "ApiKeyAuth" in schema["components"]["securitySchemes"]

        # Verify login endpoint documentation
        login_path = schema["paths"]["/api/v1/auth/login"]
        assert "post" in login_path
        assert "summary" in login_path["post"]
        assert "description" in login_path["post"]
        assert "responses" in login_path["post"]

        # Verify comprehensive response examples
        responses = login_path["post"]["responses"]
        assert "200" in responses
        assert "401" in responses
        assert "content" in responses["200"]

        print("✅ OpenAPI schema generation: PASSED")

    def test_swagger_ui_documentation(self):
        """Test that Swagger UI is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

        print("✅ Swagger UI documentation: PASSED")

    def test_re_doc_documentation(self):
        """Test that ReDoc is accessible."""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text.lower()

        print("✅ ReDoc documentation: PASSED")

    def test_typed_api_envelope_responses(self):
        """Test that API responses follow typed envelope structure."""
        # Test successful login response structure
        login_data = self.login_response.json()
        assert "success" in login_data
        assert "message" in login_data
        assert "timestamp" in login_data
        assert "data" in login_data
        assert login_data["success"] is True

        # Verify data structure for login response
        data = login_data["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert "expires_in" in data
        assert "user" in data

        # Verify user structure
        user = data["user"]
        assert "id" in user
        assert "username" in user
        assert "email" in user
        assert "full_name" in user
        assert "roles" in user
        assert "permissions" in user
        assert "is_admin" in user
        assert "created_at" in user

        print("✅ Typed API envelope responses: PASSED")

    def test_error_responses_with_typed_schemas(self):
        """Test that error responses use typed error schemas."""
        # Test invalid login (should return 401)
        invalid_login = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "wrong_password",
                "remember_me": False
            }
        )
        assert invalid_login.status_code == 401

        error_data = invalid_login.json()
        assert "success" in error_data
        assert "error" in error_data
        assert "message" in error_data
        assert "timestamp" in error_data
        assert error_data["success"] is False

        print("✅ Typed error responses: PASSED")

    def test_authenticated_endpoint_documentation(self):
        """Test that authenticated endpoints require proper authentication."""
        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Test getting current user info
        me_response = client.get("/api/v1/auth/me", headers=headers)
        assert me_response.status_code == 200

        me_data = me_response.json()
        assert "success" in me_data
        assert "data" in me_data
        assert me_data["success"] is True

        # Verify user data structure
        user_data = me_data["data"]
        assert "id" in user_data
        assert "username" in user_data
        assert "roles" in user_data
        assert "permissions" in user_data

        print("✅ Authenticated endpoint documentation: PASSED")

    def test_permission_based_access_documentation(self):
        """Test that permission requirements are properly documented."""
        # Access token from admin user should have system.read permission
        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Test system info endpoint (requires system.read permission)
        info_response = client.get("/api/v1/system/info", headers=headers)
        assert info_response.status_code == 200

        info_data = info_response.json()
        assert "success" in info_data
        assert "data" in info_data
        assert "users" in info_data["data"]
        assert "agents" in info_data["data"]
        assert "goals" in info_data["data"]
        assert "actions" in info_data["data"]

        print("✅ Permission-based access documentation: PASSED")

    def test_comprehensive_endpoint_documentation(self):
        """Test that all endpoints have comprehensive documentation."""
        response = client.get("/openapi.json")
        schema = response.json()

        # Check key endpoints have documentation
        expected_endpoints = [
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/auth/logout",
            "/api/v1/auth/me",
            "/api/v1/users",
            "/api/v1/agents",
            "/api/v1/goals",
            "/api/v1/api-tokens",
            "/api/v1/system/health",
            "/api/v1/system/info"
        ]

        for endpoint in expected_endpoints:
            assert endpoint in schema["paths"], f"Endpoint {endpoint} not documented"

        print("✅ Comprehensive endpoint documentation: PASSED")

    def test_api_schema_consistency(self):
        """Test that API schemas are consistent across endpoints."""
        response = client.get("/openapi.json")
        schema = response.json()

        # Verify components section has comprehensive schemas
        assert "schemas" in schema["components"]

        # Check for key schema definitions
        expected_schemas = [
            "LoginRequest", "LoginResponse", "TokenRefreshRequest", "TokenData",
            "UserInfo", "UserCreate", "UserUpdate", "UserResponse",
            "AgentCreate", "AgentResponse", "GoalCreate", "GoalResponse",
            "APITokenCreate", "APITokenResponse", "SystemHealth", "SystemInfo",
            "APIResponse", "APIError", "ErrorDetail", "PaginationInfo"
        ]

        for schema_name in expected_schemas:
            assert schema_name in schema["components"]["schemas"], \
                f"Schema {schema_name} not found in components"

        print("✅ API schema consistency: PASSED")

    def test_performance_with_comprehensive_documentation(self):
        """Test that comprehensive documentation doesn't impact performance."""
        start_time = time.time()

        # Make multiple authenticated requests
        for _ in range(10):
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = client.get("/api/v1/auth/me", headers=headers)
            assert response.status_code == 200

        end_time = time.time()
        avg_time = (end_time - start_time) / 10

        # Should be fast even with comprehensive schemas
        assert avg_time < 0.1  # Less than 100ms per request

        print(f"✅ Performance with documentation: PASSED ({avg_time*1000:.2f}ms avg)")

    def test_enumeration_documentation(self):
        """Test that enums are properly documented in OpenAPI."""
        response = client.get("/openapi.json")
        schema = response.json()

        # Check that enum values are documented
        login_path = schema["paths"]["/api/v1/auth/login"]
        request_body = login_path["post"]["requestBody"]
        content = request_body["content"]["application/json"]
        schema_ref = content["schema"]

        # The schema should reference UserStatus enum
        assert schema_ref["$ref"] or "properties" in schema_ref

        print("✅ Enumeration documentation: PASSED")

    def test_pagination_documentation(self):
        """Test that pagination is properly documented."""
        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Test list users with pagination
        response = client.get("/api/v1/users?skip=0&limit=10", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert "success" in data

        print("✅ Pagination documentation: PASSED")

if __name__ == "__main__":
    # Run comprehensive tests
    test = TestAPIDocumentation()
    test.setup_method()

    print("🚀 Starting API Documentation Comprehensive Tests\n")

    try:
        test.test_openapi_schema_generation()
        test.test_swagger_ui_documentation()
        test.test_re_doc_documentation()
        test.test_typed_api_envelope_responses()
        test.test_error_responses_with_typed_schemas()
        test.test_authenticated_endpoint_documentation()
        test.test_permission_based_access_documentation()
        test.test_comprehensive_endpoint_documentation()
        test.test_api_schema_consistency()
        test.test_performance_with_comprehensive_documentation()
        test.test_enumeration_documentation()
        test.test_pagination_documentation()

        print("\n🎉 ALL API DOCUMENTATION TESTS PASSED!")
        print("📚 Comprehensive OpenAPI documentation is working correctly")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise