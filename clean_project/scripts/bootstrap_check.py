#!/usr/bin/env python3
"""
Bootstrap readiness check for Agent Enterprise system.
Verifies: DB connectivity, Redis availability, and provider keys.
"""
from __future__ import annotations

import asyncio
import os
import sys


async def main() -> int:
    from agent_system.auth_models import db_manager as auth_db
    from agent_system.production_config import get_config
    from agent_system.cache_manager import cache_manager
    from agent_system.unified_config import unified_config

    cfg = get_config()
    ok = True

    # DB check
    try:
        auth_db.database_url = os.getenv("AUTH_DATABASE_URL") or cfg.get_database_url()
        auth_db.initialize()
        with auth_db.get_session() as s:
            s.execute("SELECT 1")
        print("✅ Database connectivity OK")
    except Exception as exc:
        ok = False
        print(f"❌ Database check failed: {exc}")

    # Redis check (required for distributed or rate limiting)
    try:
        await cache_manager.connect()
        healthy = await cache_manager.is_healthy()
        if healthy:
            print("✅ Redis connectivity OK")
        else:
            raise RuntimeError("Redis ping failed")
    except Exception as exc:
        if os.getenv("DISTRIBUTED_ENABLED", "false").lower() == "true":
            ok = False
        print(f"❌ Redis check failed: {exc}")

    # Provider keys check
    providers = unified_config.get_configured_providers()
    if any(p in ("serpapi", "bing", "google") for p in providers):
        print(f"✅ Web search provider configured: {', '.join(p for p in providers if p in ('serpapi','bing','google'))}")
    else:
        print("⚠️  No web search provider keys found (SERPAPI/BING/GOOGLE)")

    if any(p in ("openai", "anthropic") for p in providers):
        print(f"✅ LLM providers configured: {', '.join(p for p in providers if p in ('openai','anthropic'))}")
    else:
        print("ℹ️  No LLM provider keys found (OPENAI/ANTHROPIC). Local provider may be used.")

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130)

