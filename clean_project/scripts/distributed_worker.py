"""
Backward-compatible entrypoint for launching the agent worker.

Use `python -m agent_system.worker` directly for new deployments.
"""

from __future__ import annotations

from agent_system.worker import main


if __name__ == "__main__":
    main()
