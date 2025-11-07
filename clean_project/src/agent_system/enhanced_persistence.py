"""
Enhanced Persistence Layer
Database-backed persistence with same interface as original JSON persistence
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .enterprise_persistence import enterprise_persistence

logger = logging.getLogger(__name__)


def save_action_selector(selector: Any, filename: str = "action_selector.json") -> None:
    """Save action selector to database with fallback to JSON."""
    try:
        # Convert selector to dict format
        if hasattr(selector, "action_scores"):
            # Handle ActionSelector objects
            selector_data = {
                "action_scores": selector.action_scores,
                "action_counts": selector.action_counts,
                "context_weights": getattr(selector, "context_weights", {}),
                "goal_patterns": getattr(selector, "goal_patterns", {}),
                "learning_rate": getattr(selector, "learning_rate", 0.1),
                "epsilon": getattr(selector, "epsilon", 0.1),
                "type": getattr(selector, "type", "intelligent"),
            }
        else:
            # Already a dict
            selector_data = selector

        enterprise_persistence.save_action_selector(selector_data, filename)
        logger.debug("Action selector saved successfully")

    except Exception as e:
        logger.error(f"Failed to save action selector: {e}")
        # Fallback to original JSON persistence
        from .persistence import save_action_selector as json_save

        json_save(selector, filename)


def load_action_selector(
    selector: Any = None, filename: str = "action_selector.json"
) -> Dict[str, Any]:
    """Load action selector from database with fallback to JSON."""
    try:
        data = enterprise_persistence.load_action_selector(filename)
        if data:
            logger.debug("Action selector loaded from database")
            return data
    except Exception as e:
        logger.warning(f"Database load failed, trying JSON: {e}")

    # Fallback to JSON
    from .persistence import load_action_selector as json_load

    data = json_load(filename)
    if data:
        logger.debug("Action selector loaded from JSON file")
    return data or {}


def save_learning_system(learning_system: Any, filename: str = "learning_system.json") -> None:
    """Save learning system to database with fallback to JSON."""
    try:
        # Convert learning system to dict format
        if hasattr(learning_system, "strategy_performance"):
            # Handle LearningSystem objects
            learning_data = {
                "strategy_performance": learning_system.strategy_performance,
                "pattern_library": getattr(learning_system, "pattern_library", {}),
            }
        else:
            # Already a dict
            learning_data = learning_system

        enterprise_persistence.save_learning_system(learning_data, filename)
        logger.debug("Learning system saved successfully")

    except Exception as e:
        logger.error(f"Failed to save learning system: {e}")
        # Fallback to original JSON persistence
        from .persistence import save_learning_system as json_save

        json_save(learning_system, filename)


def load_learning_system(
    learning_system: Any = None, filename: str = "learning_system.json"
) -> Dict[str, Any]:
    """Load learning system from database with fallback to JSON."""
    try:
        data = enterprise_persistence.load_learning_system(filename)
        if data:
            logger.debug("Learning system loaded from database")
            return data
    except Exception as e:
        logger.warning(f"Database load failed, trying JSON: {e}")

    # Fallback to JSON
    from .persistence import load_learning_system as json_load

    data = json_load(filename)
    if data:
        logger.debug("Learning system loaded from JSON file")
    return data or {}


def save_memory_system(memory_system: Any, filename: str = "episodic_memory.json") -> None:
    """Save memory system to database with fallback to JSON."""
    try:
        # Convert memory system to list of memories
        if hasattr(memory_system, "episodic_memory"):
            # Handle MemorySystem objects, serialize to plain dicts
            def _serialize(mem):
                return {
                    "id": mem.id,
                    "goal_id": mem.goal_id,
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
                        "status": getattr(
                            mem.observation.status, "value", str(mem.observation.status)
                        ),
                        "result": mem.observation.result,
                        "timestamp": (
                            mem.observation.timestamp.isoformat()
                            if hasattr(mem.observation, "timestamp")
                            else None
                        ),
                        "feedback": mem.observation.feedback,
                        "metrics": mem.observation.metrics,
                    },
                    "context": mem.context,
                    "success_score": mem.success_score,
                }

            memories = []
            for memory in memory_system.episodic_memory:
                data = _serialize(memory)
                data["type"] = "episodic"
                memories.append(data)
            for memory in memory_system.working_memory:
                data = _serialize(memory)
                data["type"] = "working"
                memories.append(data)
        else:
            # Already a list of memories
            memories = memory_system if isinstance(memory_system, list) else []

        enterprise_persistence.save_memories(memories, filename)
        logger.debug(f"Memory system saved: {len(memories)} memories")

    except Exception as e:
        logger.error(f"Failed to save memory system: {e}")
        # Fallback to original JSON persistence
        from .persistence import save_memory_system as json_save

        json_save(memory_system, filename)


def load_memory_system(
    memory_system: Any = None, filename: str = "episodic_memory.json"
) -> List[Dict[str, Any]]:
    """Load memory system from database with fallback to JSON."""
    try:
        memories = enterprise_persistence.load_memories(filename)
        if memories is not None:
            logger.debug(f"Memory system loaded from database: {len(memories)} memories")
            return memories
    except Exception as e:
        logger.warning(f"Database load failed, trying JSON: {e}")

    # Fallback to JSON
    from .persistence import load_memory_system as json_load

    memories = json_load(filename)
    if memories:
        logger.debug(f"Memory system loaded from JSON file: {len(memories)} memories")
    return memories or []


def save_all(agent: Any) -> None:
    """Persist all supported subsystems of the agent to database."""
    try:
        save_action_selector(agent.action_selector)
        save_learning_system(agent.learning_system)
        save_memory_system(agent.memory_system)
        logger.info("Persisted agent state to database")
    except Exception as e:
        logger.error(f"Failed to persist agent state: {e}")
        # Fallback to JSON persistence
        from .persistence import save_all as json_save_all

        json_save_all(agent)


def load_all(agent: Any) -> None:
    """Load persisted state into the agent from database."""
    try:
        load_action_selector(agent.action_selector)
        load_learning_system(agent.learning_system)
        load_memory_system(agent.memory_system)
        logger.info("Loaded agent state from database")
    except Exception as e:
        logger.warning(f"Database load failed, trying JSON: {e}")
        # Fallback to JSON persistence
        from .persistence import load_all as json_load_all

        json_load_all(agent)


def get_storage_info() -> Dict[str, Any]:
    """Get information about current storage system."""
    return enterprise_persistence.get_storage_info()


def get_database_stats() -> Dict[str, int]:
    """Get database statistics if available."""
    try:
        from .database_persistence import db_persistence

        return db_persistence.get_database_stats()
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return {}
