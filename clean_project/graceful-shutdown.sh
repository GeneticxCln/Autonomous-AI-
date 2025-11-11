#!/bin/sh
set -eu

echo "[graceful-shutdown] Initiating preStop hook"

# Try to gently signal common server processes if present
if command -v pkill >/dev/null 2>&1; then
  pkill -TERM -f "uvicorn" 2>/dev/null || true
  pkill -TERM -f "agent_system.fastapi_app:app" 2>/dev/null || true
fi

# Give the app a moment to complete in-flight requests
sleep 5

echo "[graceful-shutdown] Completed"
exit 0
