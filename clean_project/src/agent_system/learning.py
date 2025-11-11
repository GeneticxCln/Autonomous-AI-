from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .models import Action, ActionStatus, Goal, Observation, Plan

logger = logging.getLogger(__name__)


class LearningSystem:
    """Learns from experience and adapts strategies."""

    def __init__(self) -> None:
        self.strategy_performance: Dict[str, List[float]] = defaultdict(list)
        self.pattern_library: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

    def learn_from_episode(
        self,
        goal: Goal,
        actions: List[Action],
        observations: List[Observation],
        final_success: bool,
    ) -> None:
        """Learn from a completed episode (goal attempt)."""
        strategy_key = self._identify_strategy(actions)
        success_score = 1.0 if final_success else 0.0

        self.strategy_performance[strategy_key].append(success_score)

        for action, observation in zip(actions, observations):
            pattern_key = f"{goal.description[:30]}:{action.tool_name}"
            action_success = 1.0 if observation.status == ActionStatus.SUCCESS else 0.0
            self.pattern_library[pattern_key].append((action.name, action_success))

        logger.info("Learned from episode: %s (success: %s)", strategy_key, final_success)

    def _identify_strategy(self, actions: List[Action]) -> str:
        """Identify strategy from action sequence."""
        return "->".join([action.name for action in actions])

    def get_best_strategy(self, goal_type: str) -> Optional[str]:
        """Get the best performing strategy for a goal type."""
        best_strategy: Optional[str] = None
        best_score = 0.0

        for strategy, scores in self.strategy_performance.items():
            if len(scores) >= 2:
                avg_score = sum(scores) / len(scores)
                if avg_score > best_score:
                    best_score = avg_score
                    best_strategy = strategy

        return best_strategy

    def suggest_improvements(self, goal: Goal, current_plan: Plan) -> List[str]:
        """Suggest improvements based on learned patterns."""
        suggestions: List[str] = []

        for action in current_plan.actions:
            pattern_key = f"{goal.description[:30]}:{action.tool_name}"
            patterns = self.pattern_library.get(pattern_key, [])

            if patterns:
                best_action = max(patterns, key=lambda pair: pair[1])
                if best_action[0] != action.name and best_action[1] > 0.7:
                    suggestions.append(
                        f"Consider using '{best_action[0]}' instead of '{action.name}' "
                        f"(historical success: {best_action[1]:.1%})"
                    )

        strategy_key = self._identify_strategy(current_plan.actions)
        if strategy_key in self.strategy_performance:
            scores = self.strategy_performance[strategy_key]
            avg_score = sum(scores) / len(scores)
            if avg_score < 0.5:
                suggestions.append(
                    f"This strategy has low success rate ({avg_score:.1%}), consider alternative approach"
                )

        return suggestions

    def get_learning_stats(self) -> Dict[str, Any]:
        """Get learning system statistics."""
        return {
            "strategies_learned": len(self.strategy_performance),
            "patterns_learned": len(self.pattern_library),
            "total_episodes": sum(len(scores) for scores in self.strategy_performance.values()),
            "best_strategies": {
                strategy: sum(scores) / len(scores)
                for strategy, scores in self.strategy_performance.items()
                if len(scores) >= 2
            },
        }
