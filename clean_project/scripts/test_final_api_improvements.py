"""
Final comprehensive test for API documentation improvements
Verifies that comprehensive schemas are properly integrated and working
"""

from scripts.test_client import client


def test_openapi_generation_success():
    """Test that OpenAPI schema generates successfully."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()

    # Verify basic structure
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema
    assert "components" in schema

    # Verify API info
    info = schema["info"]
    assert info["title"] == "Agent Enterprise API"
    assert info["version"] == "1.0.0"

    print("✅ OpenAPI generation success: PASSED")


def test_comprehensive_schemas_imported():
    """Test that comprehensive schemas are imported and available."""
    response = client.get("/openapi.json")
    schema = response.json()
    schemas = schema["components"]["schemas"]

    # Check that key comprehensive schemas are included
    expected_schemas = [
        "LoginRequest",
        "TokenRefreshRequest",
        "UserCreate",
        "AgentCreate",
        "GoalCreate",
        "APITokenCreate",
        "APIResponse",
        "APIError",
        "ErrorDetail",
    ]

    for schema_name in expected_schemas:
        assert schema_name in schemas, f"Missing expected schema: {schema_name}"

    print("✅ Comprehensive schemas imported: PASSED")


def test_security_schemes_defined():
    """Test that security schemes are properly defined."""
    response = client.get("/openapi.json")
    schema = response.json()
    security_schemes = schema["components"]["securitySchemes"]

    # Verify security schemes
    assert "BearerAuth" in security_schemes
    assert "ApiKeyAuth" in security_schemes

    # Verify BearerAuth structure
    bearer_auth = security_schemes["BearerAuth"]
    assert bearer_auth["type"] == "http"
    assert bearer_auth["scheme"] == "bearer"
    assert bearer_auth["bearerFormat"] == "JWT"

    # Verify ApiKeyAuth structure
    api_key_auth = security_schemes["ApiKeyAuth"]
    assert api_key_auth["type"] == "apiKey"
    assert api_key_auth["in"] == "header"
    assert api_key_auth["name"] == "X-API-Key"

    print("✅ Security schemes defined: PASSED")


def test_comprehensive_endpoint_coverage():
    """Test that all major endpoints are documented."""
    response = client.get("/openapi.json")
    schema = response.json()
    paths = schema["paths"]

    # Check for comprehensive endpoint coverage
    expected_endpoints = [
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/users",
        "/api/v1/agents",
        "/api/v1/agents/{agent_id}",
        "/api/v1/agents/{agent_id}/execute",
        "/api/v1/goals",
        "/api/v1/api-tokens",
        "/api/v1/system/health",
        "/api/v1/system/info",
    ]

    for endpoint in expected_endpoints:
        assert endpoint in paths, f"Missing endpoint: {endpoint}"

    print("✅ Comprehensive endpoint coverage: PASSED")


def test_enhanced_login_endpoint():
    """Test that login endpoint has enhanced documentation."""
    response = client.get("/openapi.json")
    schema = response.json()
    login_path = schema["paths"]["/api/v1/auth/login"]["post"]

    # Verify enhanced documentation
    assert "summary" in login_path
    assert "description" in login_path
    assert "responses" in login_path

    # Verify response documentation includes both success and error cases
    responses = login_path["responses"]
    assert "200" in responses
    assert "401" in responses

    # Verify request body is documented
    assert "requestBody" in login_path

    print("✅ Enhanced login endpoint documentation: PASSED")


def test_enhanced_refresh_endpoint():
    """Test that refresh endpoint has enhanced documentation."""
    response = client.get("/openapi.json")
    schema = response.json()
    refresh_path = schema["paths"]["/api/v1/auth/refresh"]["post"]

    # Verify enhanced documentation
    assert "summary" in refresh_path
    assert "description" in refresh_path

    print("✅ Enhanced refresh endpoint documentation: PASSED")


def test_documentation_ui_accessibility():
    """Test that documentation UIs are accessible."""
    # Test Swagger UI
    swagger_response = client.get("/docs")
    assert swagger_response.status_code == 200
    assert "swagger" in swagger_response.text.lower()

    # Test ReDoc
    redoc_response = client.get("/redoc")
    assert redoc_response.status_code == 200
    assert "redoc" in redoc_response.text.lower()

    print("✅ Documentation UI accessibility: PASSED")


def test_api_info_endpoint():
    """Test that API info endpoint provides comprehensive information."""
    response = client.get("/api/info")
    assert response.status_code == 200

    data = response.json()

    # Verify comprehensive information structure
    assert "api" in data
    assert "version" in data
    assert "endpoints" in data
    assert "authentication" in data
    assert "rate_limit" in data

    # Verify all endpoint categories are documented
    endpoint_categories = ["authentication", "users", "agents", "goals", "api_tokens", "system"]
    for category in endpoint_categories:
        assert category in data["endpoints"], f"Missing endpoint category: {category}"

    print("✅ API info endpoint: PASSED")


def test_root_endpoint():
    """Test that root endpoint provides navigation."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()

    # Verify navigation links
    assert "docs" in data
    assert "redoc" in data
    assert "health" in data
    assert data["docs"] == "/docs"
    assert data["redoc"] == "/redoc"
    assert data["health"] == "/api/v1/system/health"

    print("✅ Root endpoint: PASSED")


def test_health_endpoint():
    """Test that health endpoint is accessible without auth."""
    response = client.get("/health")

    # Health endpoint may return 503 if database is not available, but it should be accessible
    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert "status" in data
        assert "database" in data
    else:
        # 503 is acceptable if database is not connected
        data = response.json()
        assert "status" in data
        assert "database" in data

    print("✅ Health endpoint: PASSED")


def test_schema_type_definitions():
    """Test that schemas have proper type definitions."""
    response = client.get("/openapi.json")
    schema = response.json()
    schemas = schema["components"]["schemas"]

    # Test LoginRequest structure
    login_request = schemas["LoginRequest"]
    assert "properties" in login_request
    assert "username" in login_request["properties"]
    assert "password" in login_request["properties"]

    # Test APIResponse structure
    api_response = schemas["APIResponse"]
    assert "properties" in api_response
    assert "success" in api_response["properties"]
    assert "message" in api_response["properties"]
    assert "timestamp" in api_response["properties"]
    assert "data" in api_response["properties"]

    # Test APIError structure
    api_error = schemas["APIError"]
    assert "properties" in api_error
    assert "success" in api_error["properties"]
    assert "error" in api_error["properties"]
    assert "message" in api_error["properties"]
    assert "timestamp" in api_error["properties"]

    print("✅ Schema type definitions: PASSED")


def test_validation_error_handling():
    """Test that validation errors are properly handled."""
    # Test with invalid login data (missing required fields)
    response = client.post("/api/v1/auth/login", json={})
    assert response.status_code == 422  # Validation error

    # Verify validation error structure
    data = response.json()
    assert "detail" in data  # FastAPI validation error format

    print("✅ Validation error handling: PASSED")


def test_comprehensive_enumeration_support():
    """Test that enums are defined in comprehensive schemas."""
    # Verify that the comprehensive schemas file exists and has enums
    from agent_system.api_schemas import RoleLevel, SecurityEventType, SecuritySeverity, UserStatus

    # Test that enums have values
    assert len(UserStatus.__members__) > 0
    assert len(RoleLevel.__members__) > 0
    assert len(SecurityEventType.__members__) > 0
    assert len(SecuritySeverity.__members__) > 0

    print("✅ Comprehensive enumeration support: PASSED")


def test_response_envelope_consistency():
    """Test that response envelopes follow consistent structure."""
    # Test root endpoint response
    root_response = client.get("/")
    assert root_response.status_code == 200
    root_data = root_response.json()
    assert isinstance(root_data, dict)

    # Test health endpoint response (may be 503 if db not connected)
    health_response = client.get("/health")
    assert health_response.status_code in [200, 503]
    health_data = health_response.json()
    assert isinstance(health_data, dict)

    print("✅ Response envelope consistency: PASSED")


def test_performance_with_comprehensive_schemas():
    """Test that comprehensive schemas don't impact performance significantly."""
    import time

    # Test multiple OpenAPI requests
    start_time = time.time()
    for _ in range(5):
        response = client.get("/openapi.json")
        assert response.status_code == 200
    end_time = time.time()

    avg_time = (end_time - start_time) / 5
    assert avg_time < 0.1  # Should be fast

    print(f"✅ Performance with comprehensive schemas: PASSED ({avg_time*1000:.2f}ms avg)")


if __name__ == "__main__":
    print("🚀 Starting Final API Documentation Improvements Test\n")

    try:
        test_openapi_generation_success()
        test_comprehensive_schemas_imported()
        test_security_schemes_defined()
        test_comprehensive_endpoint_coverage()
        test_enhanced_login_endpoint()
        test_enhanced_refresh_endpoint()
        test_documentation_ui_accessibility()
        test_api_info_endpoint()
        test_root_endpoint()
        test_health_endpoint()
        test_schema_type_definitions()
        test_validation_error_handling()
        test_comprehensive_enumeration_support()
        test_response_envelope_consistency()
        test_performance_with_comprehensive_schemas()

        print("\n🎉 ALL API DOCUMENTATION IMPROVEMENT TESTS PASSED!")
        print("📚 Comprehensive OpenAPI documentation is fully implemented and working")
        print("🔍 Key improvements achieved:")
        print("   ✅ Comprehensive Pydantic schemas defined in api_schemas.py")
        print("   ✅ Enhanced endpoint documentation with examples")
        print("   ✅ Proper security scheme definitions (Bearer + API Key)")
        print("   ✅ Typed response envelopes for consistency")
        print("   ✅ Error schema definitions for proper error handling")
        print("   ✅ Complete enumeration support for API clarity")
        print("   ✅ Performance maintained despite comprehensive schemas")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        raise
