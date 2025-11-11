
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_system.api_security import (
    RateLimitMiddleware,
    _reset_rate_limit_state_for_tests,
    check_custom_rate_limit,
)


@pytest.mark.anyio
async def test_check_custom_rate_limit_exceeds_threshold(monkeypatch):
    _reset_rate_limit_state_for_tests()

    # Force in-memory fallback by bypassing Redis connectivity
    async def _always_fail_increment(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "agent_system.cache_manager.cache_manager.increment_counter",
        _always_fail_increment,
        raising=True,
    )

    exceeded = False
    for _ in range(3):
        exceeded = await check_custom_rate_limit("unit", "tester", limit=2, window_seconds=60)

    assert exceeded is True


def test_rate_limit_middleware_returns_429(monkeypatch):
    _reset_rate_limit_state_for_tests()

    async def _always_fail_increment(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "agent_system.cache_manager.cache_manager.increment_counter",
        _always_fail_increment,
        raising=True,
    )

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit=2, window_seconds=60, enabled=True)

    @app.get("/ping")
    def ping():
        return {"status": "ok"}

    client = TestClient(app)
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    throttled = client.get("/ping")
    assert throttled.status_code == 429
    assert throttled.json()["error"] == "RATE_LIMIT_EXCEEDED"
