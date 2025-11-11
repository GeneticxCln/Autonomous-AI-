from __future__ import annotations

from typing import Dict

import pytest

from agent_system import api_security
from agent_system.cache_manager import cache_manager
from agent_system.config_simple import get_api_key
from agent_system.models import ActionStatus
from agent_system.real_tools import RealWebSearchTool
from agent_system.unified_config import unified_config


@pytest.mark.asyncio
async def test_provider_order_and_disable(monkeypatch):
    # Configure providers: prefer bing then serpapi; disable none
    unified_config.api.search_provider_order = ["bing", "serpapi", "google"]
    unified_config.api.disabled_search_providers = []

    # Mark keys as configured (runtime)
    unified_config.api.bing_search_key = "test-bing"
    unified_config.api.serpapi_key = "test-serp"
    # Ensure function reflects new values
    assert get_api_key("bing") == "test-bing"
    assert get_api_key("serpapi") == "test-serp"

    tool = RealWebSearchTool()

    called: Dict[str, int] = {"bing": 0, "serpapi": 0, "google": 0}

    def fake_bing(q: str, n: int):
        called["bing"] += 1
        return {
            "results": [{"title": "B", "link": "https://bing.example", "snippet": "b"}],
            "count": 1,
            "search_engine": "bing",
            "query": q,
        }

    def fake_serpapi(q: str, n: int):
        called["serpapi"] += 1
        return None

    monkeypatch.setattr(tool, "_try_bing_search", fake_bing)
    monkeypatch.setattr(tool, "_try_serpapi_search", fake_serpapi)

    status, result = tool.execute(query="q", max_results=3)
    assert status == ActionStatus.SUCCESS
    assert result.get("search_engine") == "bing"
    assert called["bing"] == 1
    assert called["serpapi"] == 1  # tried after bing only if needed; our fake returns directly

    # Now disable bing; serpapi should be used
    unified_config.api.disabled_search_providers = ["bing"]

    def fake_serpapi_success(q: str, n: int):
        called["serpapi"] += 1
        return {
            "results": [{"title": "S", "link": "https://google.example", "snippet": "s"}],
            "count": 1,
            "search_engine": "google_serpapi" if False else "google_serpapi".replace("google_", "serpapi_"),
            "query": q,
        }

    monkeypatch.setattr(tool, "_try_serpapi_search", fake_serpapi_success)

    status, result = tool.execute(query="q2", max_results=2)
    assert status == ActionStatus.SUCCESS
    assert result.get("search_engine").startswith("serpapi")


@pytest.mark.asyncio
async def test_rate_limit_strict_mode_fail_closed(monkeypatch):
    # Enable strict mode
    unified_config.strict_mode = True

    async def fake_increment(*args, **kwargs):
        return None  # simulate Redis unavailable

    monkeypatch.setattr(cache_manager, "increment_counter", fake_increment)

    throttled = await api_security.check_custom_rate_limit("api", "unit:test", limit=10, window_seconds=60)
    assert throttled is True

