"""
Enterprise Persistence Layer
Database-first persistence system for agent state.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .database_models import db_manager
from .database_persistence import db_persistence

logger = logging.getLogger(__name__)


class EnterprisePersistence:
    """Ensures all agent state is stored in the database."""

    def __init__(self, use_database: bool = True, database_url: str | None = None):
        self.use_database = use_database
        self.database_url = database_url
        self._database_available = False
        self._initialized = False

    def configure(self, *, database_url: str | None = None):
        """Update persistence configuration and force re-initialization."""
        if database_url:
            self.database_url = database_url
        self._database_available = False
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self._initialize_database()

    def _initialize_database(self) -> None:
        if not self.use_database:
            raise RuntimeError("Database persistence is required but disabled")

        try:
            if self.database_url:
                db_manager.database_url = self.database_url

            db_manager.initialize()
            self._database_available = True
            self._initialized = True
            logger.info("Database persistence enabled")

            # Run legacy migration once if JSON state files are present
            state_dir = Path(".agent_state")
            if state_dir.exists() and any(state_dir.glob("*.json")):
                from .data_migration import run_migration

                migration_report = run_migration()
                logger.info(
                    "Migration completed: %s records migrated",
                    migration_report["migration_summary"]["records_migrated"],
                )

        except Exception as exc:  # pragma: no cover - startup failures are fatal
            self._initialized = True
            self._database_available = False
            logger.error("Database initialization failed: %s", exc)
            raise

    def _require_database(self) -> None:
        self._ensure_initialized()
        if not self._database_available:
            raise RuntimeError("Database persistence is not available")

    def save_action_selector(self, selector_data: Dict[str, Any], *_args, **_kwargs) -> None:
        self._require_database()
        selector_type = selector_data.get("type", "intelligent")
        db_persistence.save_action_selector(selector_data, selector_type)
        logger.debug("Action selector saved to database: %s", selector_type)

    def load_action_selector(self, *_args, **_kwargs) -> Optional[Dict[str, Any]]:
        self._require_database()
        result = db_persistence.load_action_selector("intelligent")
        logger.debug("Action selector loaded from database")
        return result

    def save_learning_system(self, learning_data: Dict[str, Any], *_args, **_kwargs) -> None:
        self._require_database()
        db_persistence.save_learning_system(learning_data, "default")
        logger.debug("Learning system saved to database")

    def load_learning_system(self, *_args, **_kwargs) -> Optional[Dict[str, Any]]:
        self._require_database()
        result = db_persistence.load_learning_system("default")
        logger.debug("Learning system loaded from database")
        return result

    def save_memories(self, memories: List[Dict[str, Any]], *_args, **_kwargs) -> None:
        self._require_database()
        db_persistence.save_memory(memories)
        logger.debug("Memories saved to database: %s items", len(memories))

    def load_memories(self, *_args, **_kwargs) -> List[Dict[str, Any]]:
        self._require_database()
        result = db_persistence.load_memories() or []
        logger.debug("Memories loaded from database: %s items", len(result))
        return result

    def get_storage_info(self) -> Dict[str, Any]:
        self._ensure_initialized()
        info: Dict[str, Any] = {
            "storage_type": "database",
            "database_available": self._database_available,
            "database_url": db_manager.database_url,
        }

        if self._database_available:
            try:
                info["database_stats"] = db_persistence.get_database_stats()
            except Exception as exc:  # pragma: no cover - diagnostics only
                info["database_error"] = str(exc)
        return info


# Global enterprise persistence instance (lazy initialization)
enterprise_persistence = EnterprisePersistence()
