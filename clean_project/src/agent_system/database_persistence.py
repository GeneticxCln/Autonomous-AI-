"""
Database Persistence Layer
Replaces JSON file-based persistence with enterprise database storage
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc

from .database_models import (
    ActionModel,
    ActionSelectorModel,
    ConfigurationModel,
    CrossSessionPatternModel,
    DatabaseManager,
    DecisionModel,
    GoalModel,
    LearningSystemModel,
    MemoryModel,
    ObservationModel,
    PerformanceMetricModel,
    SecurityAuditModel,
    db_manager,
)

logger = logging.getLogger(__name__)


class DatabasePersistence:
    """Database-backed persistence layer replacing JSON files."""

    def __init__(self) -> None:
        self.db: DatabaseManager = db_manager

    def save_action_selector(
        self, selector_data: Dict[str, Any], selector_type: str = "intelligent"
    ) -> None:
        """Save action selector data to database."""
        try:
            with self.db.get_session() as session:
                # Check if selector exists
                existing = (
                    session.query(ActionSelectorModel)
                    .filter(ActionSelectorModel.selector_type == selector_type)
                    .first()
                )

                if existing:
                    # Update existing
                    existing.action_scores = selector_data.get("action_scores", {})
                    existing.action_counts = selector_data.get("action_counts", {})
                    existing.action_history = selector_data.get("action_history", {})
                    existing.context_weights = selector_data.get("context_weights", {})
                    existing.goal_patterns = selector_data.get("goal_patterns", {})
                    existing.learning_rate = selector_data.get("learning_rate", 0.1)
                    existing.epsilon = selector_data.get("epsilon", 0.1)
                else:
                    # Create new
                    model = ActionSelectorModel(
                        selector_type=selector_type,
                        action_scores=selector_data.get("action_scores", {}),
                        action_counts=selector_data.get("action_counts", {}),
                        action_history=selector_data.get("action_history", {}),
                        context_weights=selector_data.get("context_weights", {}),
                        goal_patterns=selector_data.get("goal_patterns", {}),
                        learning_rate=selector_data.get("learning_rate", 0.1),
                        epsilon=selector_data.get("epsilon", 0.1),
                    )
                    session.add(model)

                session.commit()
                logger.debug(f"Action selector saved to database: {selector_type}")

        except Exception as e:
            logger.error(f"Failed to save action selector: {e}")
            raise

    def load_action_selector(self, selector_type: str = "intelligent") -> Optional[Dict[str, Any]]:
        """Load action selector data from database."""
        try:
            with self.db.get_session() as session:
                selector = (
                    session.query(ActionSelectorModel)
                    .filter(ActionSelectorModel.selector_type == selector_type)
                    .first()
                )

                if not selector:
                    return None

                return {
                    "action_scores": selector.action_scores or {},
                    "action_counts": selector.action_counts or {},
                    "action_history": selector.action_history or {},
                    "context_weights": selector.context_weights or {},
                    "goal_patterns": selector.goal_patterns or {},
                    "learning_rate": selector.learning_rate,
                    "epsilon": selector.epsilon,
                    "type": selector.selector_type,
                }

        except Exception as e:
            logger.error(f"Failed to load action selector: {e}")
            return None

    def save_memory(self, memories: List[Dict[str, Any]]) -> None:
        """Save memories to database.

        This method deduplicates memory_ids within the provided batch to avoid
        UNIQUE constraint violations when multiple entries reference the same
        logical memory in a single call.
        """
        try:
            with self.db.get_session() as session:
                # Track newly created models in-session to avoid duplicate inserts
                created: Dict[str, MemoryModel] = {}

                for memory_data in memories:
                    mem_id = memory_data.get("id", "")
                    if not mem_id:
                        # Skip invalid entries without an ID
                        continue

                    # If we already added this memory in the current batch, update it
                    if mem_id in created:
                        model = created[mem_id]
                        model.goal_id = memory_data.get("goal_id")
                        model.action_data = memory_data.get("action", {})
                        model.observation_data = memory_data.get("observation", {})
                        model.context_data = memory_data.get("context", {})
                        model.success_score = memory_data.get("success_score", 0.0)
                        model.memory_type = memory_data.get("type", "working")
                        model.accessed_at = datetime.now(UTC)
                        continue

                    # Otherwise, see if it exists in the database already
                    existing = (
                        session.query(MemoryModel).filter(MemoryModel.memory_id == mem_id).first()
                    )

                    if existing:
                        # Update existing
                        existing.goal_id = memory_data.get("goal_id")
                        existing.action_data = memory_data.get("action", {})
                        existing.observation_data = memory_data.get("observation", {})
                        existing.context_data = memory_data.get("context", {})
                        existing.success_score = memory_data.get("success_score", 0.0)
                        existing.memory_type = memory_data.get("type", "working")
                        existing.accessed_at = datetime.now(UTC)
                    else:
                        # Create new and record in local map
                        model = MemoryModel(
                            memory_id=mem_id,
                            goal_id=memory_data.get("goal_id"),
                            action_data=memory_data.get("action", {}),
                            observation_data=memory_data.get("observation", {}),
                            context_data=memory_data.get("context", {}),
                            success_score=memory_data.get("success_score", 0.0),
                            memory_type=memory_data.get("type", "working"),
                        )
                        session.add(model)
                        created[mem_id] = model

                session.commit()
                logger.debug(f"Memories saved to database: {len(memories)} items")

        except Exception as e:
            logger.error(f"Failed to save memories: {e}")
            raise

    def load_memories(self) -> List[Dict[str, Any]]:
        """Load memories from database."""
        try:
            with self.db.get_session() as session:
                memories = session.query(MemoryModel).all()

                result = []
                for memory in memories:
                    result.append(
                        {
                            "id": memory.memory_id,
                            "goal_id": memory.goal_id,
                            "action": memory.action_data or {},
                            "observation": memory.observation_data or {},
                            "context": memory.context_data or {},
                            "success_score": memory.success_score,
                            "type": memory.memory_type,
                        }
                    )

                return result

        except Exception as e:
            logger.error(f"Failed to load memories: {e}")
            return []

    def save_learning_system(
        self, learning_data: Dict[str, Any], system_type: str = "default"
    ) -> None:
        """Save learning system data to database."""
        try:
            with self.db.get_session() as session:
                existing = (
                    session.query(LearningSystemModel)
                    .filter(LearningSystemModel.system_type == system_type)
                    .first()
                )

                if existing:
                    # Update existing
                    existing.learned_strategies = learning_data.get("learned_strategies", {})
                    existing.strategy_performance = learning_data.get("strategy_performance", {})
                    existing.strategy_scores = learning_data.get("strategy_scores", {})
                    existing.pattern_library = learning_data.get("pattern_library", {})
                    existing.total_episodes = learning_data.get("total_episodes", 0)
                    existing.learning_history = learning_data.get("learning_history", [])
                    existing.best_strategies = learning_data.get("best_strategies", {})
                else:
                    # Create new
                    model = LearningSystemModel(
                        system_type=system_type,
                        learned_strategies=learning_data.get("learned_strategies", {}),
                        strategy_performance=learning_data.get("strategy_performance", {}),
                        strategy_scores=learning_data.get("strategy_scores", {}),
                        pattern_library=learning_data.get("pattern_library", {}),
                        total_episodes=learning_data.get("total_episodes", 0),
                        learning_history=learning_data.get("learning_history", []),
                        best_strategies=learning_data.get("best_strategies", {}),
                    )
                    session.add(model)

                session.commit()
                logger.debug(f"Learning system saved to database: {system_type}")

        except Exception as e:
            logger.error(f"Failed to save learning system: {e}")
            raise

    def load_learning_system(self, system_type: str = "default") -> Optional[Dict[str, Any]]:
        """Load learning system data from database."""
        try:
            with self.db.get_session() as session:
                learning = (
                    session.query(LearningSystemModel)
                    .filter(LearningSystemModel.system_type == system_type)
                    .first()
                )

                if not learning:
                    return None

                return {
                    "learned_strategies": learning.learned_strategies or {},
                    "strategy_performance": learning.strategy_performance or {},
                    "strategy_scores": learning.strategy_scores or {},
                    "pattern_library": learning.pattern_library or {},
                    "total_episodes": learning.total_episodes,
                    "learning_history": learning.learning_history or [],
                    "best_strategies": learning.best_strategies or {},
                    "type": learning.system_type,
                }

        except Exception as e:
            logger.error(f"Failed to load learning system: {e}")
            return None

    def save_goals(self, goals_data: List[Dict[str, Any]]) -> None:
        """Save goals to database."""
        try:
            with self.db.get_session() as session:
                for goal_data in goals_data:
                    existing = (
                        session.query(GoalModel)
                        .filter(GoalModel.id == goal_data.get("id", ""))
                        .first()
                    )

                    title = goal_data.get("title") or goal_data.get("description", "")[:200]
                    description = goal_data.get("description", "")
                    status_val = goal_data.get("status", "pending")
                    # Map 0-1 float to 1-10 int if needed
                    priority_val = goal_data.get("priority", 1)
                    if isinstance(priority_val, float):
                        priority_val = max(1, min(10, int(round(priority_val * 10))))
                    progress_val = float(goal_data.get("progress", 0.0))

                    if existing:
                        existing.title = title
                        existing.description = description
                        existing.status = status_val
                        existing.priority = priority_val
                        existing.progress = progress_val
                    else:
                        model = GoalModel(
                            id=goal_data.get("id", None) or None,
                            title=title,
                            description=description,
                            status=status_val,
                            priority=priority_val,
                            progress=progress_val,
                        )
                        session.add(model)

                session.commit()
                logger.debug(f"Goals saved to database: {len(goals_data)} items")

        except Exception as e:
            logger.error(f"Failed to save goals: {e}")
            raise

    def load_goals(self) -> List[Dict[str, Any]]:
        """Load goals from database."""
        try:
            with self.db.get_session() as session:
                goals = session.query(GoalModel).order_by(desc(GoalModel.created_at)).all()

                result = []
                for goal in goals:
                    result.append(
                        {
                            "id": goal.id,
                            "title": goal.title,
                            "description": goal.description,
                            "status": goal.status,
                            "priority": goal.priority,
                            "progress": goal.progress,
                        }
                    )

                return result

        except Exception as e:
            logger.error(f"Failed to load goals: {e}")
            return []

    def save_actions(self, actions_data: List[Dict[str, Any]]) -> None:
        """Save actions to database."""
        try:
            with self.db.get_session() as session:
                for action_data in actions_data:
                    # Check if action exists
                    existing = (
                        session.query(ActionModel)
                        .filter(ActionModel.action_id == action_data.get("id", ""))
                        .first()
                    )

                    if existing:
                        # Update existing
                        existing.goal_id = action_data.get("goal_id")
                        existing.action_type = action_data.get("type", "")
                        existing.description = action_data.get("description", "")
                        existing.parameters = action_data.get("parameters", {})
                        existing.status = action_data.get("status", "pending")
                        existing.result = action_data.get("result", {})
                        existing.success_score = action_data.get("success_score", 0.0)
                    else:
                        # Create new
                        model = ActionModel(
                            action_id=action_data.get("id", ""),
                            goal_id=action_data.get("goal_id"),
                            action_type=action_data.get("type", ""),
                            description=action_data.get("description", ""),
                            parameters=action_data.get("parameters", {}),
                            status=action_data.get("status", "pending"),
                            result=action_data.get("result", {}),
                            success_score=action_data.get("success_score", 0.0),
                        )
                        session.add(model)

                session.commit()
                logger.debug(f"Actions saved to database: {len(actions_data)} items")

        except Exception as e:
            logger.error(f"Failed to save actions: {e}")
            raise

    def load_actions(self) -> List[Dict[str, Any]]:
        """Load actions from database."""
        try:
            with self.db.get_session() as session:
                actions = session.query(ActionModel).order_by(desc(ActionModel.created_at)).all()

                result = []
                for action in actions:
                    result.append(
                        {
                            "id": action.action_id,
                            "goal_id": action.goal_id,
                            "type": action.action_type,
                            "description": action.description,
                            "parameters": action.parameters or {},
                            "status": action.status,
                            "result": action.result or {},
                            "success_score": action.success_score,
                        }
                    )

                return result

        except Exception as e:
            logger.error(f"Failed to load actions: {e}")
            return []

    def save_observations(self, observations_data: List[Dict[str, Any]]) -> None:
        """Save observations to database."""
        try:
            with self.db.get_session() as session:
                for obs_data in observations_data:
                    # Check if observation exists
                    existing = (
                        session.query(ObservationModel)
                        .filter(ObservationModel.observation_id == obs_data.get("id", ""))
                        .first()
                    )

                    if existing:
                        # Update existing
                        existing.action_id = obs_data.get("action_id")
                        existing.goal_id = obs_data.get("goal_id")
                        existing.content = obs_data.get("content", "")
                        existing.observation_type = obs_data.get("type", "result")
                        existing.obs_metadata = obs_data.get("metadata", {})
                        existing.success = obs_data.get("success", False)
                    else:
                        # Create new
                        model = ObservationModel(
                            observation_id=obs_data.get("id", ""),
                            action_id=obs_data.get("action_id"),
                            goal_id=obs_data.get("goal_id"),
                            content=obs_data.get("content", ""),
                            observation_type=obs_data.get("type", "result"),
                            obs_metadata=obs_data.get("metadata", {}),
                            success=obs_data.get("success", False),
                        )
                        session.add(model)

                session.commit()
                logger.debug(f"Observations saved to database: {len(observations_data)} items")

        except Exception as e:
            logger.error(f"Failed to save observations: {e}")
            raise

    def load_observations(self) -> List[Dict[str, Any]]:
        """Load observations from database."""
        try:
            with self.db.get_session() as session:
                observations = (
                    session.query(ObservationModel)
                    .order_by(desc(ObservationModel.created_at))
                    .all()
                )

                result = []
                for obs in observations:
                    result.append(
                        {
                            "id": obs.observation_id,
                            "action_id": obs.action_id,
                            "goal_id": obs.goal_id,
                            "content": obs.content,
                            "type": obs.observation_type,
                            "metadata": obs.obs_metadata or {},
                            "success": obs.success,
                        }
                    )

                return result

        except Exception as e:
            logger.error(f"Failed to load observations: {e}")
            return []

    def save_cross_session_patterns(self, patterns_data: List[Dict[str, Any]]) -> None:
        """Save cross-session learning patterns to database."""
        try:
            with self.db.get_session() as session:
                for pattern_data in patterns_data:
                    # Check if pattern exists
                    existing = (
                        session.query(CrossSessionPatternModel)
                        .filter(CrossSessionPatternModel.pattern_id == pattern_data.get("id", ""))
                        .first()
                    )

                    if existing:
                        # Update existing
                        existing.pattern_type = pattern_data.get("type", "")
                        existing.pattern_data = pattern_data.get("data", {})
                        existing.confidence_score = pattern_data.get("confidence", 0.0)
                        existing.usage_count = pattern_data.get("usage_count", 0)
                        existing.success_rate = pattern_data.get("success_rate", 0.0)
                    else:
                        # Create new
                        model = CrossSessionPatternModel(
                            pattern_id=pattern_data.get("id", ""),
                            pattern_type=pattern_data.get("type", ""),
                            pattern_data=pattern_data.get("data", {}),
                            confidence_score=pattern_data.get("confidence", 0.0),
                            usage_count=pattern_data.get("usage_count", 0),
                            success_rate=pattern_data.get("success_rate", 0.0),
                        )
                        session.add(model)

                session.commit()
                logger.debug(
                    f"Cross-session patterns saved to database: {len(patterns_data)} items"
                )

        except Exception as e:
            logger.error(f"Failed to save cross-session patterns: {e}")
            raise

    def load_cross_session_patterns(self) -> List[Dict[str, Any]]:
        """Load cross-session learning patterns from database."""
        try:
            with self.db.get_session() as session:
                patterns = (
                    session.query(CrossSessionPatternModel)
                    .order_by(desc(CrossSessionPatternModel.confidence_score))
                    .all()
                )

                result = []
                for pattern in patterns:
                    result.append(
                        {
                            "id": pattern.pattern_id,
                            "type": pattern.pattern_type,
                            "data": pattern.pattern_data or {},
                            "confidence": pattern.confidence_score,
                            "usage_count": pattern.usage_count,
                            "success_rate": pattern.success_rate,
                        }
                    )

                return result

        except Exception as e:
            logger.error(f"Failed to load cross-session patterns: {e}")
            return []

    def save_configuration(
        self, config_key: str, config_value: Any, config_type: str = "system"
    ) -> None:
        """Save configuration to database."""
        try:
            with self.db.get_session() as session:
                # Check if config exists
                existing = (
                    session.query(ConfigurationModel)
                    .filter(ConfigurationModel.config_key == config_key)
                    .first()
                )

                if existing:
                    # Update existing
                    existing.config_value = config_value
                    existing.config_type = config_type
                else:
                    # Create new
                    model = ConfigurationModel(
                        config_key=config_key, config_value=config_value, config_type=config_type
                    )
                    session.add(model)

                session.commit()
                logger.debug(f"Configuration saved to database: {config_key}")

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise

    def load_configuration(self, config_key: str) -> Optional[Any]:
        """Load configuration from database."""
        try:
            with self.db.get_session() as session:
                config = (
                    session.query(ConfigurationModel)
                    .filter(
                        and_(
                            ConfigurationModel.config_key == config_key,
                            ConfigurationModel.is_active.is_(True),
                        )
                    )
                    .first()
                )

                return config.config_value if config else None

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return None

    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        try:
            with self.db.get_session() as session:
                stats = {
                    "action_selectors": session.query(ActionSelectorModel).count(),
                    "memories": session.query(MemoryModel).count(),
                    "learning_systems": session.query(LearningSystemModel).count(),
                    "goals": session.query(GoalModel).count(),
                    "actions": session.query(ActionModel).count(),
                    "observations": session.query(ObservationModel).count(),
                    "patterns": session.query(CrossSessionPatternModel).count(),
                    "decisions": session.query(DecisionModel).count(),
                    "performance_metrics": session.query(PerformanceMetricModel).count(),
                    "security_audits": session.query(SecurityAuditModel).count(),
                    "configurations": session.query(ConfigurationModel).count(),
                }
                return stats

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}


# Global database persistence instance
db_persistence: DatabasePersistence = DatabasePersistence()
