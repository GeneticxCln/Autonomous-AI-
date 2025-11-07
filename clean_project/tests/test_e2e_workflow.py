"""
End-to-End API workflow tests using FastAPI TestClient.
Validates login, protected routes, user/goal/agent flows.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from agent_system.auth_models import db_manager
from agent_system.auth_service import auth_service
from agent_system.database_models import db_manager as app_db_manager
from agent_system.fastapi_app import app


def get_auth_headers(client: TestClient) -> dict:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123", "remember_me": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    access = data["data"]["access_token"]
    return {"Authorization": f"Bearer {access}"}


def test_e2e_api_flow():
    # Use isolated databases for E2E to avoid schema drift with local file
    db_manager.database_url = "sqlite:///./agent_e2e_auth.db"
    app_db_manager.database_url = "sqlite:///./agent_e2e.db"

    db_manager.initialize()
    app_db_manager.initialize()
    auth_service._initialize_default_data()

    client = TestClient(app)
    headers = get_auth_headers(client)

    # Cleanup if previous run left the user
    from agent_system.auth_models import UserModel

    with auth_service.db.get_session() as session:
        existing = session.query(UserModel).filter(UserModel.username == "e2e_user").first()
        if existing:
            session.delete(existing)
            session.commit()

    # Create a user
    resp = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "e2e_user",
            "email": "e2e@example.com",
            "full_name": "E2E User",
            "password": "testpass123",
            "role_names": ["user"],
        },
    )
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body.get("success") is True

    # List users
    resp = client.get("/api/v1/users", headers=headers)
    assert resp.status_code == 200
    assert resp.json().get("success") is True

    # Create a goal
    resp = client.post(
        "/api/v1/goals",
        headers=headers,
        json={
            "title": "E2E Goal",
            "description": "Ensure end-to-end works",
            "priority": 5,
        },
    )
    assert resp.status_code in (200, 201)
    goal_id = resp.json()["data"]["id"]

    # List goals
    resp = client.get("/api/v1/goals", headers=headers)
    assert resp.status_code == 200
    assert any(g["id"] == goal_id for g in resp.json()["data"])

    # Create an agent
    resp = client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "name": "E2E Agent",
            "description": "Integration agent",
            "goals": [goal_id],
            "memory_capacity": 500,
        },
    )
    assert resp.status_code in (200, 201)
    agent_id = resp.json()["data"]["id"]

    # Execute agent
    resp = client.post(f"/api/v1/agents/{agent_id}/execute", headers=headers)
    assert resp.status_code == 200
    assert resp.json().get("success") is True

    # Create API token and list
    resp = client.post(
        "/api/v1/api-tokens",
        headers=headers,
        json={"name": "E2E Token", "scopes": ["read", "write"], "expires_days": 30},
    )
    assert resp.status_code in (200, 201)
    resp = client.get("/api/v1/api-tokens", headers=headers)
    assert resp.status_code == 200
    assert resp.json().get("success") is True
