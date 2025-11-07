"""
Enterprise Persistence Layer
Hybrid persistence system with database primary and JSON fallback
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .database_persistence import db_persistence
from .persistence import load_action_selector as json_load_action_selector
from .persistence import load_learning_system as json_load_learning_system
from .persistence import save_action_selector as json_save_action_selector
from .persistence import save_learning_system as json_save_learning_system

logger = logging.getLogger(__name__)


class EnterprisePersistence:
    """
    Enterprise persistence layer that uses database as primary storage
    with JSON file fallback for backward compatibility.
    """

    def __init__(self, use_database: bool = True, database_url: str = None):
        self.use_database = use_database
        self.database_url = database_url
        self._database_available = False
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database if enabled."""
        if not self.use_database:
            logger.info("Database disabled, using JSON file persistence")
            return

        try:
            from .data_migration import run_migration
            from .database_models import db_manager

            # Use custom database URL if provided
            if self.database_url:
                db_manager.database_url = self.database_url

            # Initialize database
            db_manager.initialize()
            self._database_available = True

            logger.info("Database persistence enabled")

            # Check if we need to migrate data
            state_dir = Path(".agent_state")
            if state_dir.exists() and any(state_dir.glob("*.json")):
                logger.info("Found existing JSON files, running migration...")
                try:
                    migration_report = run_migration()
                    logger.info(
                        f"Migration completed: {migration_report['migration_summary']['records_migrated']} records migrated"
                    )
                except Exception as e:
                    logger.warning(f"Migration failed, falling back to JSON: {e}")
                    self._database_available = False

        except Exception as e:
            logger.warning(f"Database initialization failed, falling back to JSON: {e}")
            self._database_available = False

    def is_database_available(self) -> bool:
        """Check if database is available."""
        return self._database_available

    def save_action_selector(
        self, selector_data: Dict[str, Any], filename: str = "action_selector.json"
    ) -> None:
        """Save action selector using primary storage (database or JSON)."""
        if self._database_available:
            try:
                selector_type = selector_data.get("type", "intelligent")
                db_persistence.save_action_selector(selector_data, selector_type)
                logger.debug(f"Action selector saved to database: {selector_type}")
            except Exception as e:
                logger.warning(f"Database save failed, falling back to JSON: {e}")
                json_save_action_selector(selector_data, filename)
        else:
            json_save_action_selector(selector_data, filename)

    def load_action_selector(
        self, filename: str = "action_selector.json"
    ) -> Optional[Dict[str, Any]]:
        """Load action selector using primary storage (database or JSON)."""
        if self._database_available:
            try:
                result = db_persistence.load_action_selector("intelligent")
                if result:
                    logger.debug("Action selector loaded from database")
                    return result
            except Exception as e:
                logger.warning(f"Database load failed, falling back to JSON: {e}")

        # Fallback to JSON
        result = json_load_action_selector(filename)
        if result:
            logger.debug("Action selector loaded from JSON file")
        return result

    def save_learning_system(
        self, learning_data: Dict[str, Any], filename: str = "learning_system.json"
    ) -> None:
        """Save learning system using primary storage (database or JSON)."""
        if self._database_available:
            try:
                db_persistence.save_learning_system(learning_data, "default")
                logger.debug("Learning system saved to database")
            except Exception as e:
                logger.warning(f"Database save failed, falling back to JSON: {e}")
                json_save_learning_system(learning_data, filename)
        else:
            json_save_learning_system(learning_data, filename)

    def load_learning_system(
        self, filename: str = "learning_system.json"
    ) -> Optional[Dict[str, Any]]:
        """Load learning system using primary storage (database or JSON)."""
        if self._database_available:
            try:
                result = db_persistence.load_learning_system("default")
                if result:
                    logger.debug("Learning system loaded from database")
                    return result
            except Exception as e:
                logger.warning(f"Database load failed, falling back to JSON: {e}")

        # Fallback to JSON
        result = json_load_learning_system(filename)
        if result:
            logger.debug("Learning system loaded from JSON file")
        return result

    def save_memories(
        self, memories: List[Dict[str, Any]], filename: str = "episodic_memory.json"
    ) -> None:
        """Save memories using primary storage (database or JSON)."""
        if self._database_available:
            try:
                db_persistence.save_memory(memories)
                logger.debug(f"Memories saved to database: {len(memories)} items")
            except Exception as e:
                logger.warning(f"Database save failed, falling back to JSON: {e}")
                self._save_memories_json(memories, filename)
        else:
            self._save_memories_json(memories, filename)

    def _save_memories_json(self, memories: List[Dict[str, Any]], filename: str):
        """Save memories to JSON file."""
        try:
            from pathlib import Path

            from .persistence import _write_json

            state_dir = Path(".agent_state")
            path = state_dir / filename

            # Convert memories to JSON-serializable format
            json_data = []
            for memory in memories:
                json_data.append(
                    {
                        "id": memory.get("id"),
                        "goal_id": memory.get("goal_id"),
                        "action": memory.get("action", {}),
                        "observation": memory.get("observation", {}),
                        "context": memory.get("context", {}),
                        "success_score": memory.get("success_score", 0.0),
                        "type": memory.get("type", "episodic"),
                    }
                )

            _write_json(path, json_data)
            logger.debug(f"Memories saved to JSON file: {len(memories)} items")

        except Exception as e:
            logger.error(f"Failed to save memories to JSON: {e}")
            raise

    def load_memories(self, filename: str = "episodic_memory.json") -> List[Dict[str, Any]]:
        """Load memories using primary storage (database or JSON)."""
        if self._database_available:
            try:
                result = db_persistence.load_memories()
                if result is not None:
                    logger.debug(f"Memories loaded from database: {len(result)} items")
                    return result
            except Exception as e:
                logger.warning(f"Database load failed, falling back to JSON: {e}")

        # Fallback to JSON
        return self._load_memories_json(filename)

    def _load_memories_json(self, filename: str) -> List[Dict[str, Any]]:
        """Load memories from JSON file."""
        try:
            from pathlib import Path

            from .persistence import _read_json

            state_dir = Path(".agent_state")
            path = state_dir / filename

            data = _read_json(path)
            if data is None:
                return []

            if isinstance(data, list):
                memories = data
            else:
                memories = data.get("memories", data.get("episodic_memory", []))

            logger.debug(f"Memories loaded from JSON file: {len(memories)} items")
            return memories

        except Exception as e:
            logger.error(f"Failed to load memories from JSON: {e}")
            return []

    def get_storage_info(self) -> Dict[str, Any]:
        """Get information about current storage system."""
        info = {
            "storage_type": "database" if self._database_available else "json_files",
            "database_available": self._database_available,
            "database_url": self.database_url if self._database_available else None,
        }

        if self._database_available:
            try:
                info["database_stats"] = db_persistence.get_database_stats()
            except Exception as e:
                info["database_error"] = str(e)

        return info


# Global enterprise persistence instance
enterprise_persistence = EnterprisePersistence()
