from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
from typing import Any, Dict, Optional

import httpx


async def check_http(url: str, timeout: float = 3.0) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            return {"url": url, "ok": r.status_code == 200, "status": r.status_code}
    except Exception as e:
        return {"url": url, "ok": False, "error": str(e)}


async def check_redis(
    host: str = "localhost", port: int = 6379, timeout: float = 1.0
) -> Dict[str, Any]:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        writer.write(b"PING\r\n")
        await writer.drain()
        data = await asyncio.wait_for(reader.read(64), 1.0)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return {"redis": f"{host}:{port}", "ok": b"+PONG" in data}
    except Exception as e:
        return {"redis": f"{host}:{port}", "ok": False, "error": str(e)}


async def check_prometheus(url: str = "http://localhost:9090/-/healthy") -> Dict[str, Any]:
    return await check_http(url)


async def main() -> int:
    api_base = os.getenv("API_BASE", "http://localhost:8000")
    checks = []

    # API health
    checks.append(await check_http(f"{api_base}/health"))
    checks.append(await check_http(f"{api_base}/api/v1/system/health"))

    # Prometheus
    checks.append(await check_prometheus())

    # Redis
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    checks.append(await check_redis(redis_host, redis_port))

    # Summarize
    ok = all(item.get("ok") for item in checks)
    print(json.dumps({"ok": ok, "checks": checks}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
