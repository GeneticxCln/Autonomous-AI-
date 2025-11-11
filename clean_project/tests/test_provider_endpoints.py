from __future__ import annotations

from typing import Dict

import pytest
from fastapi.testclient import TestClient

from agent_system.auth_service import auth_service
from agent_system.fastapi_app import app
from agent_system.unified_config import unified_config


def _login_admin_token(client: TestClient) -> str:
    # Ensure default admin exists
    auth_service.initialize()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123", "remember_me": False},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    return data["access_token"]


@pytest.mark.parametrize("order,disabled", [(["serpapi", "bing", "google"], []), (["bing"], ["google"])])
def test_get_and_put_search_provider_config(order, disabled):
    client = TestClient(app)
    token = _login_admin_token(client)

    # Update configuration
    resp = client.put(
        "/api/v1/system/providers/search-config",
        json={"order": order, "disabled": disabled},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Verify with GET
    resp = client.get(
        "/api/v1/system/providers/search-config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data: Dict = resp.json()["data"]
    assert data["order"] == order if order else ["serpapi", "bing", "google"]
    assert data["disabled"] == disabled

    # Sanity: unified_config reflects updates
    assert unified_config.api.search_provider_order[: len(order)] == order
    assert unified_config.api.disabled_search_providers == disabled

