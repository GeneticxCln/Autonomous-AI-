"""
Enhanced Persistence Layer
Database-backed persistence with same interface as the legacy JSON module.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List

from .enterprise_persistence import enterprise_persistence
from .models import Action, ActionStatus, Memory, Observation

logger = logging.getLogger(__name__)


def _normalize_action_selector(selector: Any) -> Dict[str, Any]:
    if hasattr(selector, "action_scores"):
        return {
            "action_scores": getattr(selector, "action_scores", {}),
            "action_counts": getattr(selector, "action_counts", {}),
            "context_weights": getattr(selector, "context_weights", {}),
            "goal_patterns": getattr(selector, "goal_patterns", {}),
            "learning_rate": getattr(selector, "learning_rate", 0.1),
            "epsilon": getattr(selector, "epsilon", 0.1),
            "type": getattr(selector, "type", "intelligent"),
        }
    if hasattr(selector, "action_history"):
        # For IntelligentActionSelector with action_history
        return {
            "action_history": getattr(selector, "action_history", {}),
            "context_weights": getattr(selector, "context_weights", {}),
            "goal_patterns": getattr(selector, "goal_patterns", {}),
            "type": getattr(selector, "type", "intelligent"),
        }
    if isinstance(selector, dict):
        return selector
    raise TypeError("Unsupported selector type for persistence")


def _apply_action_selector(selector: Any, data: Dict[str, Any]) -> None:
    if hasattr(selector, "action_scores"):
        selector.action_scores.update(data.get("action_scores", {}))
        selector.action_counts.update(data.get("action_counts", {}))
        selector.context_weights = data.get("context_weights", {})
        selector.goal_patterns = data.get("goal_patterns", {})
        if "learning_rate" in data:
            selector.learning_rate = data["learning_rate"]
        if "epsilon" in data:
            selector.epsilon = data["epsilon"]
    if hasattr(selector, "action_history"):
        selector.action_history.update(data.get("action_history", {}))
        selector.context_weights = data.get("context_weights", {})
        selector.goal_patterns = data.get("goal_patterns", {})


def save_action_selector(selector: Any, filename: str = "action_selector.json") -> None:
    selector_data = _normalize_action_selector(selector)
    enterprise_persistence.save_action_selector(selector_data, filename)
    logger.debug("Action selector saved successfully")


def load_action_selector(
    selector: Any = None, filename: str = "action_selector.json"
) -> Dict[str, Any]:
    data = enterprise_persistence.load_action_selector(filename) or {}
    if selector and data:
        _apply_action_selector(selector, data)
    
    # If this is an IntelligentActionSelector with action_history, return that format
    if selector and hasattr(selector, "action_history"):
        # Return the expected payload format for tests
        payload = {"action_history": selector.action_history}
        
        # Add other properties for completeness
        if hasattr(selector, "context_weights"):
            payload["context_weights"] = selector.context_weights
        if hasattr(selector, "goal_patterns"):
            payload["goal_patterns"] = selector.goal_patterns
        
        logger.debug("Action selector loaded from database")
        return payload
    
    # If no selector or regular selector, return the loaded data as-is
    logger.debug("Action selector loaded from database")
    return data


def _normalize_learning_system(learning_system: Any) -> Dict[str, Any]:
    if hasattr(learning_system, "strategy_performance"):
        return {
            "strategy_performance": learning_system.strategy_performance,
            "pattern_library": getattr(learning_system, "pattern_library", {}),
        }
    if isinstance(learning_system, dict):
        return learning_system
    raise TypeError("Unsupported learning system type for persistence")


def _apply_learning_system(learning_system: Any, data: Dict[str, Any]) -> None:
    if hasattr(learning_system, "strategy_performance"):
        learning_system.strategy_performance.update(data.get("strategy_performance", {}))
        
        # Convert lists back to tuples for pattern_library (JSON doesn't preserve types)
        pattern_library_data = data.get("pattern_library", {})
        for pattern_key, pattern_list in pattern_library_data.items():
            # Convert each inner list back to tuple format
            if isinstance(pattern_list, list):
                pattern_library_data[pattern_key] = [tuple(item) if isinstance(item, list) else item for item in pattern_list]
        
        learning_system.pattern_library.update(pattern_library_data)


def save_learning_system(learning_system: Any, filename: str = "learning_system.json") -> None:
    payload = _normalize_learning_system(learning_system)
    enterprise_persistence.save_learning_system(payload, filename)
    logger.debug("Learning system saved successfully")


def load_learning_system(
    learning_system: Any = None, filename: str = "learning_system.json"
) -> Dict[str, Any]:
    data = enterprise_persistence.load_learning_system(filename) or {}
    if learning_system and data:
        _apply_learning_system(learning_system, data)
    
    # If this is a LearningSystem with strategy_performance, return that format
    if learning_system and hasattr(learning_system, "strategy_performance"):
        # Convert lists back to tuples for pattern_library in the payload as well
        pattern_library_payload = {}
        for pattern_key, pattern_list in learning_system.pattern_library.items():
            if isinstance(pattern_list, list):
                # Make sure each item in the list is a tuple
                pattern_library_payload[pattern_key] = [tuple(item) if isinstance(item, list) else item for item in pattern_list]
            else:
                pattern_library_payload[pattern_key] = pattern_list
        
        # Return the expected payload format for tests
        payload = {
            "strategy_performance": learning_system.strategy_performance,
            "pattern_library": pattern_library_payload,
        }
        logger.debug("Learning system loaded from database")
        return payload
    
    # If no learning_system or no data, return as-is
    logger.debug("Learning system loaded from database")
    return data


def _serialize_memory(mem: Memory, mem_type: str) -> Dict[str, Any]:
    obs_timestamp = getattr(mem.observation, "timestamp", None)
    return {
        "id": mem.id,
        "goal_id": mem.goal_id,
        "timestamp": getattr(mem, "timestamp", datetime.now(UTC)).isoformat(),
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
            "status": getattr(mem.observation.status, "value", str(mem.observation.status)),
            "result": mem.observation.result,
            "timestamp": obs_timestamp.isoformat() if obs_timestamp else None,
            "feedback": mem.observation.feedback,
            "metrics": mem.observation.metrics,
        },
        "context": mem.context,
        "success_score": mem.success_score,
        "type": mem_type,
    }


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(UTC)


def _deserialize_memory(payload: Dict[str, Any]) -> Memory:
    action_data = payload.get("action", {})
    observation_data = payload.get("observation", {})
    obs_status = observation_data.get("status", ActionStatus.SUCCESS.value)
    try:
        status = ActionStatus(obs_status)
    except ValueError:
        status = ActionStatus.SUCCESS

    action = Action(
        id=action_data.get("id", payload.get("id")),
        name=action_data.get("name", "unknown"),
        tool_name=action_data.get("tool_name", "unknown"),
        parameters=action_data.get("parameters", {}),
        expected_outcome=action_data.get("expected_outcome", ""),
        cost=float(action_data.get("cost", 0.0)),
        prerequisites=list(action_data.get("prerequisites", [])),
    )

    observation = Observation(
        action_id=observation_data.get("action_id", action.id),
        status=status,
        result=observation_data.get("result"),
        timestamp=_parse_datetime(observation_data.get("timestamp")),
        feedback=observation_data.get("feedback", ""),
        metrics=observation_data.get("metrics", {}),
    )

    return Memory(
        id=payload.get("id", ""),
        goal_id=payload.get("goal_id", ""),
        action=action,
        observation=observation,
        context=payload.get("context", {}),
        success_score=float(payload.get("success_score", 0.0)),
        timestamp=_parse_datetime(payload.get("timestamp")),
    )


def _extract_counter(memory_id: str | None) -> int:
    if not memory_id:
        return 0
    token = str(memory_id).rsplit("_", 1)[-1]
    return int(token) if token.isdigit() else 0


def _apply_memories(memory_system: Any, memories: List[Dict[str, Any]]) -> None:
    if not hasattr(memory_system, "working_memory"):
        return

    working: List[Memory] = []
    episodic: List[Memory] = []
    counter = 0

    for entry in memories:
        mem_obj = _deserialize_memory(entry)
        counter = max(counter, _extract_counter(mem_obj.id))
        if entry.get("type") == "episodic":
            episodic.append(mem_obj)
        else:
            working.append(mem_obj)

    memory_system.working_memory = working
    memory_system.episodic_memory = episodic
    memory_system.memory_counter = max(counter, len(working) + len(episodic))


def save_memory_system(memory_system: Any, filename: str = "episodic_memory.json") -> None:
    if hasattr(memory_system, "episodic_memory"):
        memories: List[Dict[str, Any]] = []
        for memory in getattr(memory_system, "episodic_memory", []):
            memories.append(_serialize_memory(memory, "episodic"))
        for memory in getattr(memory_system, "working_memory", []):
            memories.append(_serialize_memory(memory, "working"))
    else:
        memories = list(memory_system) if isinstance(memory_system, list) else []

    enterprise_persistence.save_memories(memories, filename)
    logger.debug("Memory system saved: %s memories", len(memories))


def load_memory_system(
    memory_system: Any = None, filename: str = "episodic_memory.json"
) -> List[Dict[str, Any]]:
    memories = enterprise_persistence.load_memories(filename) or []
    if memory_system is not None:
        _apply_memories(memory_system, memories)
    logger.debug("Memory system loaded from database: %s memories", len(memories))
    return memories


def save_all(agent: Any) -> None:
    save_action_selector(agent.action_selector)
    save_learning_system(agent.learning_system)
    save_memory_system(agent.memory_system)
    logger.info("Persisted agent state to database")


def load_all(agent: Any) -> None:
    load_action_selector(agent.action_selector)
    load_learning_system(agent.learning_system)
    load_memory_system(agent.memory_system)
    logger.info("Loaded agent state from database")


def get_storage_info() -> Dict[str, Any]:
    return enterprise_persistence.get_storage_info()


def get_database_stats() -> Dict[str, int]:
    from .database_persistence import db_persistence

    return db_persistence.get_database_stats()
