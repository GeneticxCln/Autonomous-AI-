from __future__ import annotations

import os

import pytest

# Ensure predictable secrets for tests (>=32 chars)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ")


@pytest.fixture(scope="session", autouse=True)
def initialize_databases():
    """Initialize application and auth databases once per test session.

    Avoids 'Database not initialized' and missing table errors in API tests.
    """
    from agent_system.auth_models import db_manager as auth_db_manager
    from agent_system.auth_service import auth_service
    from agent_system.database_models import db_manager as app_db_manager

    # Default SQLite databases for test session
    auth_db_manager.database_url = os.getenv("TEST_AUTH_DB", "sqlite:///./agent_test_auth.db")
    app_db_manager.database_url = os.getenv("TEST_APP_DB", "sqlite:///./agent_test.db")

    # Initialize both DBs and auth system
    app_db_manager.initialize()
    auth_db_manager.initialize()

    # Ensure default data/admin exists
    try:
        auth_service.initialize()
        # Some tests rely on admin:admin123 existing explicitly
        auth_service._initialize_default_data()
    except Exception:
        # If already initialized or partial, ignore
        pass
