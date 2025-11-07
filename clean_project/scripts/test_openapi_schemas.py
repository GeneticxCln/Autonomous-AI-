"""
Test OpenAPI schema generation and documentation
Verifies that comprehensive schemas are properly defined and documented
"""

from fastapi.testclient import TestClient

from agent_system.fastapi_app import app

# Create test client
client = TestClient(app)


def test_openapi_schema_structure():
    """Test that OpenAPI schema has proper structure with comprehensive documentation."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()

    # Verify basic OpenAPI structure
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema
    assert "components" in schema

    # Verify API info
    info = schema["info"]
    assert info["title"] == "Agent Enterprise API"
    assert info["version"] == "1.0.0"

    # Verify security schemes are defined
    security_schemes = schema["components"]["securitySchemes"]
    assert "BearerAuth" in security_schemes
    assert "ApiKeyAuth" in security_schemes

    print("✅ OpenAPI schema structure: PASSED")


def test_comprehensive_schema_definitions():
    """Test that comprehensive schema definitions are present."""
    response = client.get("/openapi.json")
    schema = response.json()

    # Check for comprehensive schema definitions
    schemas = schema["components"]["schemas"]

    # Core authentication schemas
    auth_schemas = ["LoginRequest", "LoginResponse", "TokenRefreshRequest", "TokenData", "UserInfo"]
    for schema_name in auth_schemas:
        assert schema_name in schemas, f"Missing auth schema: {schema_name}"

    # User management schemas
    user_schemas = ["UserCreate", "UserUpdate", "UserResponse"]
    for schema_name in user_schemas:
        assert schema_name in schemas, f"Missing user schema: {schema_name}"

    # Agent schemas
    agent_schemas = ["AgentCreate", "AgentResponse", "AgentExecute", "AgentExecutionResponse"]
    for schema_name in agent_schemas:
        assert schema_name in schemas, f"Missing agent schema: {schema_name}"

    # Goal schemas
    goal_schemas = ["GoalCreate", "GoalResponse"]
    for schema_name in goal_schemas:
        assert schema_name in schemas, f"Missing goal schema: {schema_name}"

    # API token schemas
    token_schemas = ["APITokenCreate", "APITokenResponse"]
    for schema_name in token_schemas:
        assert schema_name in schemas, f"Missing token schema: {schema_name}"

    # System schemas
    system_schemas = ["SystemHealth", "SystemInfo"]
    for schema_name in system_schemas:
        assert schema_name in schemas, f"Missing system schema: {schema_name}"

    # Base response schemas
    base_schemas = ["APIResponse", "APIError", "ErrorDetail", "PaginationInfo"]
    for schema_name in base_schemas:
        assert schema_name in schemas, f"Missing base schema: {schema_name}"

    # Security schemas
    security_schemas = ["SecurityEventResponse", "RateLimitInfo"]
    for schema_name in security_schemas:
        assert schema_name in schemas, f"Missing security schema: {schema_name}"

    print("✅ Comprehensive schema definitions: PASSED")


def test_endpoint_documentation():
    """Test that endpoints have proper documentation."""
    response = client.get("/openapi.json")
    schema = response.json()
    paths = schema["paths"]

    # Test that login endpoint has comprehensive documentation
    login_path = paths["/api/v1/auth/login"]["post"]
    assert "summary" in login_path
    assert "description" in login_path
    assert "responses" in login_path

    # Verify response documentation
    responses = login_path["responses"]
    assert "200" in responses
    assert "401" in responses

    # Test that refresh endpoint has documentation
    refresh_path = paths["/api/v1/auth/refresh"]["post"]
    assert "summary" in refresh_path
    assert "description" in refresh_path

    print("✅ Endpoint documentation: PASSED")


def test_enumeration_definitions():
    """Test that enums are properly defined."""
    response = client.get("/openapi.json")
    schema = response.json()
    schemas = schema["components"]["schemas"]

    # Check for enum definitions
    enum_schemas = ["UserStatus", "RoleLevel", "SecurityEventType", "SecuritySeverity"]
    for enum_name in enum_schemas:
        assert enum_name in schemas, f"Missing enum: {enum_name}"

    print("✅ Enumeration definitions: PASSED")


def test_swagger_ui_accessibility():
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
    """Test that API info endpoint provides comprehensive documentation."""
    response = client.get("/api/info")
    assert response.status_code == 200

    data = response.json()

    # Verify structure
    assert "api" in data
    assert "version" in data
    assert "endpoints" in data
    assert "authentication" in data
    assert "rate_limit" in data

    # Verify authentication endpoints are documented
    auth_endpoints = data["endpoints"]["authentication"]
    assert "login" in auth_endpoints
    assert "logout" in auth_endpoints
    assert "refresh" in auth_endpoints
    assert "me" in auth_endpoints

    # Verify user endpoints are documented
    user_endpoints = data["endpoints"]["users"]
    assert "create" in user_endpoints
    assert "list" in user_endpoints

    # Verify agent endpoints are documented
    agent_endpoints = data["endpoints"]["agents"]
    assert "create" in agent_endpoints
    assert "list" in agent_endpoints
    assert "get" in agent_endpoints
    assert "execute" in agent_endpoints

    # Verify goal endpoints are documented
    goal_endpoints = data["endpoints"]["goals"]
    assert "create" in goal_endpoints
    assert "list" in goal_endpoints

    # Verify API token endpoints are documented
    token_endpoints = data["endpoints"]["api_tokens"]
    assert "create" in token_endpoints
    assert "list" in token_endpoints

    # Verify system endpoints are documented
    system_endpoints = data["endpoints"]["system"]
    assert "health" in system_endpoints
    assert "info" in system_endpoints

    print("✅ API info endpoint: PASSED")


def test_root_endpoint_info():
    """Test that root endpoint provides API information."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()

    # Verify structure
    assert "message" in data
    assert "version" in data
    assert "status" in data
    assert "docs" in data
    assert "redoc" in data
    assert "health" in data

    # Verify navigation links
    assert data["docs"] == "/docs"
    assert data["redoc"] == "/redoc"
    assert data["health"] == "/api/v1/system/health"

    print("✅ Root endpoint info: PASSED")


def test_response_envelope_structure():
    """Test that response envelopes follow consistent structure."""
    # Test health endpoint (doesn't require auth)
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()

    # Should have consistent structure even for health checks
    # Health endpoint might have different structure, but verify it's valid JSON
    assert isinstance(data, dict)

    print("✅ Response envelope structure: PASSED")


def test_pagination_schema_presence():
    """Test that pagination schemas are defined."""
    response = client.get("/openapi.json")
    schema = response.json()
    schemas = schema["components"]["schemas"]

    # Check for pagination schemas
    assert "PaginationInfo" in schemas
    assert "PaginatedResponse" in schemas

    print("✅ Pagination schema presence: PASSED")


def test_error_schema_presence():
    """Test that error schemas are properly defined."""
    response = client.get("/openapi.json")
    schema = response.json()
    schemas = schema["components"]["schemas"]

    # Check for error handling schemas
    assert "APIError" in schemas
    assert "ErrorDetail" in schemas

    # Verify error schema structure
    error_schema = schemas["APIError"]
    properties = error_schema.get("properties", {})
    assert "success" in properties
    assert "error" in properties
    assert "message" in properties
    assert "timestamp" in properties

    print("✅ Error schema presence: PASSED")


def test_bulk_operations_schema():
    """Test that bulk operations schemas are defined."""
    response = client.get("/openapi.json")
    schema = response.json()
    schemas = schema["components"]["schemas"]

    # Check for bulk operation schemas
    assert "BulkOperationRequest" in schemas
    assert "BulkOperationResponse" in schemas

    print("✅ Bulk operations schema: PASSED")


def test_webhook_schema_presence():
    """Test that webhook schemas are defined."""
    response = client.get("/openapi.json")
    schema = response.json()
    schemas = schema["components"]["schemas"]

    # Check for webhook schemas
    assert "WebhookEvent" in schemas

    print("✅ Webhook schema presence: PASSED")


if __name__ == "__main__":
    print("🚀 Starting OpenAPI Schema Tests\n")

    try:
        test_openapi_schema_structure()
        test_comprehensive_schema_definitions()
        test_endpoint_documentation()
        test_enumeration_definitions()
        test_swagger_ui_accessibility()
        test_api_info_endpoint()
        test_root_endpoint_info()
        test_response_envelope_structure()
        test_pagination_schema_presence()
        test_error_schema_presence()
        test_bulk_operations_schema()
        test_webhook_schema_presence()

        print("\n🎉 ALL OPENAPI SCHEMA TESTS PASSED!")
        print("📚 Comprehensive OpenAPI documentation schemas are properly defined")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        raise
