"""
Data Migration System
Migrates data from JSON files to database for enterprise deployment
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .database_models import db_manager
from .database_persistence import db_persistence

logger = logging.getLogger(__name__)

# Default state directory
STATE_DIR = Path(".agent_state")


class DataMigration:
    """Handles migration from JSON files to database."""

    def __init__(self, state_dir: Path = STATE_DIR):
        self.state_dir = state_dir
        self.migration_stats = {
            "files_processed": 0,
            "records_migrated": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }

    def migrate_all_data(self) -> Dict[str, Any]:
        """Migrate all data from JSON files to database."""
        logger.info("Starting data migration from JSON files to database")

        self.migration_stats["start_time"] = datetime.now()

        try:
            # Initialize database
            db_manager.initialize()

            # Migrate each data type
            self.migrate_action_selector()
            self.migrate_learning_system()
            self.migrate_memories()
            self.migrate_goals()
            self.migrate_actions()
            self.migrate_observations()

            self.migration_stats["end_time"] = datetime.now()
            duration = self.migration_stats["end_time"] - self.migration_stats["start_time"]

            logger.info(f"Data migration completed in {duration.total_seconds():.2f} seconds")
            return self.get_migration_report()

        except Exception as e:
            logger.error(f"Data migration failed: {e}")
            self.migration_stats["errors"] += 1
            raise

    def migrate_action_selector(self) -> None:
        """Migrate action selector data."""
        file_path = self.state_dir / "action_selector.json"

        if not file_path.exists():
            logger.warning(f"Action selector file not found: {file_path}")
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Determine selector type from data
            selector_type = data.get("type", "intelligent")

            # Save to database
            db_persistence.save_action_selector(data, selector_type)

            self.migration_stats["files_processed"] += 1
            self.migration_stats["records_migrated"] += 1

            logger.info(f"Migrated action selector: {selector_type}")

            # Create backup
            backup_path = file_path.with_suffix(".json.backup")
            file_path.rename(backup_path)
            logger.info(f"Backed up original file to: {backup_path}")

        except Exception as e:
            logger.error(f"Failed to migrate action selector: {e}")
            self.migration_stats["errors"] += 1

    def migrate_learning_system(self) -> None:
        """Migrate learning system data."""
        file_path = self.state_dir / "learning_system.json"

        if not file_path.exists():
            logger.warning(f"Learning system file not found: {file_path}")
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Save to database
            db_persistence.save_learning_system(data, "default")

            self.migration_stats["files_processed"] += 1
            self.migration_stats["records_migrated"] += 1

            logger.info("Migrated learning system data")

            # Create backup
            backup_path = file_path.with_suffix(".json.backup")
            file_path.rename(backup_path)
            logger.info(f"Backed up original file to: {backup_path}")

        except Exception as e:
            logger.error(f"Failed to migrate learning system: {e}")
            self.migration_stats["errors"] += 1

    def migrate_memories(self) -> None:
        """Migrate memory data."""
        file_path = self.state_dir / "episodic_memory.json"

        if not file_path.exists():
            logger.warning(f"Memory file not found: {file_path}")
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Handle different memory formats
            memories = []
            if isinstance(data, list):
                memories = data
            elif isinstance(data, dict):
                # Handle different possible structures
                memories = data.get("memories", data.get("episodic_memory", []))

            # Save to database
            db_persistence.save_memory(memories)

            self.migration_stats["files_processed"] += 1
            self.migration_stats["records_migrated"] += len(memories)

            logger.info(f"Migrated {len(memories)} memories")

            # Create backup
            backup_path = file_path.with_suffix(".json.backup")
            file_path.rename(backup_path)
            logger.info(f"Backed up original file to: {backup_path}")

        except Exception as e:
            logger.error(f"Failed to migrate memories: {e}")
            self.migration_stats["errors"] += 1

    def migrate_goals(self) -> None:
        """Migrate goals data."""
        file_path = self.state_dir / "goals.json"

        if not file_path.exists():
            # Try alternative locations
            alt_paths = [self.state_dir / "goal_manager.json", self.state_dir / "goals_data.json"]

            file_path = None
            for alt_path in alt_paths:
                if alt_path.exists():
                    file_path = alt_path
                    break

        if not file_path or not file_path.exists():
            logger.warning("Goals file not found")
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Handle different goal formats
            goals = []
            if isinstance(data, list):
                goals = data
            elif isinstance(data, dict):
                # Handle different possible structures
                goals = data.get("goals", data.get("goal_list", data.get("items", [])))

            # Ensure each goal has required fields
            for goal in goals:
                if "id" not in goal:
                    goal["id"] = f"goal_{hash(goal.get('description', '')) % 10000}"

            # Save to database
            db_persistence.save_goals(goals)

            self.migration_stats["files_processed"] += 1
            self.migration_stats["records_migrated"] += len(goals)

            logger.info(f"Migrated {len(goals)} goals")

            # Create backup
            backup_path = file_path.with_suffix(".json.backup")
            file_path.rename(backup_path)
            logger.info(f"Backed up original file to: {backup_path}")

        except Exception as e:
            logger.error(f"Failed to migrate goals: {e}")
            self.migration_stats["errors"] += 1

    def migrate_actions(self) -> None:
        """Migrate actions data."""
        file_path = self.state_dir / "actions.json"

        if not file_path.exists():
            logger.warning(f"Actions file not found: {file_path}")
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Handle different action formats
            actions = []
            if isinstance(data, list):
                actions = data
            elif isinstance(data, dict):
                # Handle different possible structures
                actions = data.get("actions", data.get("action_list", data.get("items", [])))

            # Ensure each action has required fields
            for action in actions:
                if "id" not in action:
                    action["id"] = f"action_{hash(action.get('description', '')) % 10000}"

            # Save to database
            db_persistence.save_actions(actions)

            self.migration_stats["files_processed"] += 1
            self.migration_stats["records_migrated"] += len(actions)

            logger.info(f"Migrated {len(actions)} actions")

            # Create backup
            backup_path = file_path.with_suffix(".json.backup")
            file_path.rename(backup_path)
            logger.info(f"Backed up original file to: {backup_path}")

        except Exception as e:
            logger.error(f"Failed to migrate actions: {e}")
            self.migration_stats["errors"] += 1

    def migrate_observations(self) -> None:
        """Migrate observations data."""
        file_path = self.state_dir / "observations.json"

        if not file_path.exists():
            logger.warning(f"Observations file not found: {file_path}")
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Handle different observation formats
            observations = []
            if isinstance(data, list):
                observations = data
            elif isinstance(data, dict):
                # Handle different possible structures
                observations = data.get(
                    "observations", data.get("observation_list", data.get("items", []))
                )

            # Ensure each observation has required fields
            for obs in observations:
                if "id" not in obs:
                    obs["id"] = f"obs_{hash(obs.get('content', '')) % 10000}"

            # Save to database
            db_persistence.save_observations(observations)

            self.migration_stats["files_processed"] += 1
            self.migration_stats["records_migrated"] += len(observations)

            logger.info(f"Migrated {len(observations)} observations")

            # Create backup
            backup_path = file_path.with_suffix(".json.backup")
            file_path.rename(backup_path)
            logger.info(f"Backed up original file to: {backup_path}")

        except Exception as e:
            logger.error(f"Failed to migrate observations: {e}")
            self.migration_stats["errors"] += 1

    def get_migration_report(self) -> Dict[str, Any]:
        """Get migration statistics report."""
        duration = None
        if self.migration_stats["start_time"] and self.migration_stats["end_time"]:
            duration = (
                self.migration_stats["end_time"] - self.migration_stats["start_time"]
            ).total_seconds()

        # Get database statistics
        db_stats = db_persistence.get_database_stats()

        return {
            "migration_summary": {
                "status": (
                    "completed" if self.migration_stats["errors"] == 0 else "completed_with_errors"
                ),
                "files_processed": self.migration_stats["files_processed"],
                "records_migrated": self.migration_stats["records_migrated"],
                "errors": self.migration_stats["errors"],
                "duration_seconds": duration,
            },
            "database_statistics": db_stats,
            "migration_details": {
                "source_format": "JSON files",
                "target_format": "SQLite database",
                "backup_location": str(self.state_dir),
                "database_file": db_manager.database_url.replace("sqlite:///", ""),
            },
        }

    def rollback_migration(self) -> None:
        """Rollback migration by restoring JSON files from backups."""
        logger.info("Rolling back migration - restoring JSON files from backups")

        try:
            backup_files = list(self.state_dir.glob("*.backup"))
            restored_count = 0

            for backup_file in backup_files:
                # Restore original file name
                original_name = backup_file.stem  # Remove .backup extension
                original_path = self.state_dir / f"{original_name}.json"

                # Move backup back to original location
                backup_file.rename(original_path)
                restored_count += 1

                logger.info(f"Restored: {original_path}")

            logger.info(f"Rolled back {restored_count} files")

        except Exception as e:
            logger.error(f"Failed to rollback migration: {e}")
            raise

    def verify_migration(self) -> Dict[str, Any]:
        """Verify that migration was successful."""
        logger.info("Verifying migration integrity")

        # Get database stats
        db_stats = db_persistence.get_database_stats()

        # Check for backup files (should exist if migration was successful)
        backup_files = list(self.state_dir.glob("*.backup"))

        verification_results = {
            "database_connected": True,
            "tables_created": len(db_stats) > 0,
            "total_records": sum(db_stats.values()),
            "backup_files_found": len(backup_files),
            "migration_verified": len(backup_files) > 0 and sum(db_stats.values()) > 0,
        }

        logger.info(f"Migration verification: {verification_results}")

        return verification_results


def run_migration() -> Dict[str, Any]:
    """Run complete data migration."""
    migration = DataMigration()
    return migration.migrate_all_data()


if __name__ == "__main__":
    # Run migration when script is executed directly
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    try:
        report = run_migration()
        print("\n" + "=" * 60)
        print("DATA MIGRATION REPORT")
        print("=" * 60)
        print(json.dumps(report, indent=2, default=str))
        print("=" * 60)

    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
