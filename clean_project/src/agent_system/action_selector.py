from __future__ import annotations

import logging
import random
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .models import Action, Goal

logger = logging.getLogger(__name__)


class ActionSelector:
    """Selects actions based on learned performance and contextual scoring."""

    def __init__(self, learning_rate: float = 0.1, epsilon: float = 0.1):
        self.action_scores: Dict[str, float] = defaultdict(float)
        self.action_counts: Dict[str, int] = defaultdict(int)
        self.learning_rate = learning_rate
        # Exploration rate for epsilon-greedy selection (0 <= epsilon <= 1)
        self.epsilon = max(0.0, min(epsilon, 1.0))

    def select_action(
        self,
        available_actions: List[Action],
        goal: Goal,
        context: Dict[str, Any],
        completed_actions: Optional[List[str]] = None,
    ) -> Optional[Action]:
        """Select the best action using multi-criteria scoring."""
        if not available_actions:
            return None

        completed_actions = completed_actions or []
        scored_actions: List[Tuple[float, Action]] = []

        for action in available_actions:
            if not self._prerequisites_met(action, completed_actions):
                continue

            score = self._score_action(action, goal, context)
            scored_actions.append((score, action))

        if not scored_actions:
            return None

        # Epsilon-greedy selection: with probability epsilon, explore a random feasible action.
        if random.random() < self.epsilon and len(scored_actions) > 1:
            selected_score, selected_action = random.choice(scored_actions)
            logger.info(
                "Selected action (explore): %s (score: %.3f)", selected_action.name, selected_score
            )
            return selected_action

        scored_actions.sort(reverse=True, key=lambda pair: pair[0])
        selected_action = scored_actions[0][1]

        logger.info("Selected action: %s (score: %.3f)", selected_action.name, scored_actions[0][0])
        return selected_action

    def update_action_score(self, action: Action, success_score: float):
        """Update action score based on outcome."""
        action_key = f"{action.tool_name}:{action.name}"
        # Use same default baseline as _score_action to ensure monotonic improvement when learning
        old_score = self.action_scores.get(action_key, 0.5)
        self.action_scores[action_key] = old_score * (1 - self.learning_rate) + success_score * self.learning_rate
        self.action_counts[action_key] += 1

        logger.debug(
            "Updated score for %s: %.3f -> %.3f",
            action_key,
            old_score,
            self.action_scores[action_key],
        )

    def _score_action(self, action: Action, goal: Goal, context: Dict[str, Any]) -> float:
        """Score an action based on utility, history, alignment, and context."""
        action_key = f"{action.tool_name}:{action.name}"
        historical_score = self.action_scores.get(action_key, 0.5)
        utility_score = 1.0 / (1.0 + action.cost)
        alignment_score = self._calculate_alignment(action, goal)
        context_score = self._calculate_context_relevance(action, context)

        return (
            historical_score * 0.3
            + utility_score * 0.2
            + alignment_score * 0.3
            + context_score * 0.2
        )

    def _prerequisites_met(self, action: Action, completed_actions: List[str]) -> bool:
        """Check if action prerequisites are satisfied."""
        return all(prereq in completed_actions for prereq in action.prerequisites)

    def _calculate_alignment(self, action: Action, goal: Goal) -> float:
        """Calculate how well action aligns with goal."""
        goal_words = set(goal.description.lower().split())
        action_words = set(action.name.lower().split())
        outcome_words = set(action.expected_outcome.lower().split())

        overlap = len(goal_words & (action_words | outcome_words))
        total = len(goal_words)

        return overlap / total if total > 0 else 0.5

    def _calculate_context_relevance(self, action: Action, context: Dict[str, Any]) -> float:
        """Calculate how relevant action is given current context.

        Heuristics:
        - Boost if action parameters align with available context keys.
        - Adjust by recent success_rate in working memory context if present.
        """
        relevance = 0.5

        if context:
            for key in action.parameters:
                if key in context:
                    relevance += 0.1

            # Incorporate recent success rate if provided by MemorySystem context [0..1].
            success_rate = context.get("success_rate")
            if isinstance(success_rate, (int, float)):
                # Map success_rate in [0,1] to [-0.1, +0.1] adjustment centered at 0.5
                relevance += (success_rate - 0.5) * 0.2

        return min(max(relevance, 0.0), 1.0)
