from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .models import Action, ActionStatus, Memory, Observation

logger = logging.getLogger(__name__)

# Default state directory inside project root
STATE_DIR = Path(".agent_state")
STATE_DIR.mkdir(exist_ok=True)


def _read_json(path: Path) -> Dict[str, Any] | List[Any] | None:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to read JSON %s: %s", path, exc)
        return None


def _write_json(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to write JSON %s: %s", path, exc)


# ---------- ActionSelector persistence ----------


def save_action_selector(selector: Any, filename: str = "action_selector.json") -> None:
    path = STATE_DIR / filename

    # Handle both old and new action selectors
    if hasattr(selector, "action_scores"):  # Old ActionSelector
        payload = {
            "action_scores": selector.action_scores,
            "action_counts": selector.action_counts,
            "learning_rate": getattr(selector, "learning_rate", 0.1),
            "epsilon": getattr(selector, "epsilon", 0.1),
            "type": "old",
        }
    elif hasattr(selector, "action_history"):  # IntelligentActionSelector
        payload = {
            "action_history": selector.action_history,
            "context_weights": getattr(selector, "context_weights", {}),
            "goal_patterns": getattr(selector, "goal_patterns", {}),
            "type": "intelligent",
        }
    else:
        logger.warning(f"Unknown action selector type: {type(selector)}")
        payload = {"type": "unknown"}

    _write_json(path, payload)


def load_action_selector(selector: Any, filename: str = "action_selector.json") -> None:
    path = STATE_DIR / filename
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return

    selector_type = payload.get("type", "unknown")

    if selector_type == "old" and hasattr(selector, "action_scores"):
        # Load old action selector data
        selector.action_scores.update(payload.get("action_scores", {}))
        selector.action_counts.update(payload.get("action_counts", {}))
        if "learning_rate" in payload:
            selector.learning_rate = float(payload["learning_rate"])
        if "epsilon" in payload:
            selector.epsilon = float(payload["epsilon"])

    elif selector_type == "intelligent" and hasattr(selector, "action_history"):
        # Load intelligent action selector data
        selector.action_history.update(payload.get("action_history", {}))
        selector.context_weights.update(payload.get("context_weights", {}))
        selector.goal_patterns.update(payload.get("goal_patterns", {}))

    else:
        logger.warning(
            f"Cannot load action selector data - type mismatch or unsupported type: {selector_type}"
        )


# ---------- LearningSystem persistence ----------


def save_learning_system(learning: Any, filename: str = "learning_system.json") -> None:
    path = STATE_DIR / filename
    payload = {
        "strategy_performance": learning.strategy_performance,
        "pattern_library": learning.pattern_library,
    }
    _write_json(path, payload)


def load_learning_system(learning: Any, filename: str = "learning_system.json") -> None:
    path = STATE_DIR / filename
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return
    learning.strategy_performance.update(payload.get("strategy_performance", {}))
    learning.pattern_library.update(payload.get("pattern_library", {}))


# ---------- MemorySystem persistence (episodic only) ----------

# Minimal serialization for Memory avoiding deep recursion and non-JSON types


def _serialize_memory(mem: Memory) -> Dict[str, Any]:
    return {
        "id": mem.id,
        "goal_id": mem.goal_id,
        "timestamp": mem.timestamp.isoformat(),
        "success_score": mem.success_score,
        "context": mem.context,
        "action": {
            "id": mem.action.id,
            "name": mem.action.name,
            "tool_name": mem.action.tool_name,
            "parameters": mem.action.parameters,
            "expected_outcome": mem.action.expected_outcome,
            "cost": mem.action.cost,
            "prerequisites": mem.action.prerequisites,
        },
        "observation": {
            "action_id": mem.observation.action_id,
            "status": mem.observation.status.value,
            "result": mem.observation.result,
            "timestamp": mem.observation.timestamp.isoformat(),
            "feedback": mem.observation.feedback,
            "metrics": mem.observation.metrics,
        },
    }


def _deserialize_memory(payload: Dict[str, Any]) -> Memory:
    action = Action(
        id=payload["action"]["id"],
        name=payload["action"]["name"],
        tool_name=payload["action"]["tool_name"],
        parameters=payload["action"].get("parameters", {}),
        expected_outcome=payload["action"]["expected_outcome"],
        cost=float(payload["action"]["cost"]),
        prerequisites=list(payload["action"].get("prerequisites", [])),
    )
    observation = Observation(
        action_id=payload["observation"]["action_id"],
        status=ActionStatus(payload["observation"]["status"]),
        result=payload["observation"].get("result"),
        timestamp=datetime.fromisoformat(payload["observation"]["timestamp"]),
        feedback=payload["observation"].get("feedback", ""),
        metrics=payload["observation"].get("metrics", {}),
    )
    return Memory(
        id=payload["id"],
        goal_id=payload["goal_id"],
        action=action,
        observation=observation,
        context=payload.get("context", {}),
        success_score=float(payload.get("success_score", 0.0)),
        timestamp=datetime.fromisoformat(payload["timestamp"]),
    )


def save_memory_system(memory_sys: Any, filename: str = "episodic_memory.json") -> None:
    path = STATE_DIR / filename
    payload = {
        "episodic": [_serialize_memory(m) for m in getattr(memory_sys, "episodic_memory", [])],
        "counter": getattr(memory_sys, "memory_counter", 0),
    }
    _write_json(path, payload)


def load_memory_system(memory_sys: Any, filename: str = "episodic_memory.json") -> None:
    path = STATE_DIR / filename
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return
    episodic = payload.get("episodic", [])
    try:
        memory_sys.episodic_memory = [_deserialize_memory(item) for item in episodic]  # type: ignore[attr-defined]
        memory_sys.memory_counter = int(payload.get("counter", len(memory_sys.episodic_memory)))  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to load episodic memory: %s", exc)


# ---------- High-level helpers ----------


def save_all(agent: Any) -> None:
    """Persist all supported subsystems of the agent."""
    try:
        save_action_selector(agent.action_selector)
        save_learning_system(agent.learning_system)
        save_memory_system(agent.memory_system)
        logger.info("Persisted agent state to %s", STATE_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to persist agent state: %s", exc)


def load_all(agent: Any) -> None:
    """Load persisted state into the agent if present."""
    try:
        load_action_selector(agent.action_selector)
        load_learning_system(agent.learning_system)
        load_memory_system(agent.memory_system)
        logger.info("Loaded agent state from %s", STATE_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to load agent state: %s", exc)
