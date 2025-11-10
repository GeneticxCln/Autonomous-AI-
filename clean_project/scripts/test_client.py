from __future__ import annotations

import atexit
import os
from contextlib import ExitStack

from fastapi.testclient import TestClient

os.environ.setdefault("SKIP_INFRA_STARTUP", "true")

from agent_system.fastapi_app import app

_stack = ExitStack()
client: TestClient = _stack.enter_context(TestClient(app))


@atexit.register
def _close_client() -> None:
    _stack.close()
