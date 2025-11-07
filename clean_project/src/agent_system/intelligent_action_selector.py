"""
Intelligent action selector with real decision-making capabilities.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .models import Action, Goal

logger = logging.getLogger(__name__)


class IntelligentActionSelector:
    """AI-powered action selector that makes intelligent decisions."""

    def __init__(self):
        self.action_history = {}  # Track action performance
        self.context_weights = {}  # Context-specific weights
        self.goal_patterns = {}  # Learned goal patterns

    def select_action(
        self,
        available_actions: List[Action],
        goal: Goal,
        context: Dict[str, Any],
        completed_actions: List[str],
    ) -> Optional[Action]:
        """Intelligently select the best action based on context and learning."""

        if not available_actions:
            return None

        logger.info(
            f"Selecting action from {len(available_actions)} options for goal: {goal.description}"
        )

        # Score each action
        scored_actions = []
        for action in available_actions:
            score = self._calculate_action_score(action, goal, context, completed_actions)
            scored_actions.append((action, score))

        # Sort by score (highest first)
        scored_actions.sort(key=lambda x: x[1], reverse=True)

        best_action, best_score = scored_actions[0]

        logger.info(f"Selected action: {best_action.name} (score: {best_score:.3f})")

        # Store selection rationale for learning
        self._store_selection_rationale(best_action, goal, context, best_score)

        return best_action

    def _calculate_action_score(
        self, action: Action, goal: Goal, context: Dict[str, Any], completed_actions: List[str]
    ) -> float:
        """Calculate intelligent score for an action."""

        score = 0.0

        # 1. Base score from action type (30%)
        score += self._get_action_type_score(action) * 0.3

        # 2. Goal alignment score (25%)
        score += self._calculate_goal_alignment(action, goal) * 0.25

        # 3. Context relevance score (20%)
        score += self._calculate_context_relevance(action, context) * 0.2

        # 4. Historical performance score (15%)
        score += self._get_historical_performance_score(action) * 0.15

        # 5. Prerequisite completion score (10%)
        score += self._calculate_prerequisite_score(action, completed_actions) * 0.1

        return max(0.0, min(1.0, score))  # Ensure score is between 0 and 1

    def _get_action_type_score(self, action: Action) -> float:
        """Score based on action type and current context."""

        action_scores = {
            "search_information": 0.9,
            "load_data": 0.8,
            "execute_code": 0.7,
            "analyze_sources": 0.8,
            "synthesize_findings": 0.6,
            "save_results": 0.4,
            "generic_task": 0.3,
        }

        return action_scores.get(action.name, 0.5)

    def _calculate_goal_alignment(self, action: Action, goal: Goal) -> float:
        """Calculate how well an action aligns with the goal."""

        goal_lower = goal.description.lower()
        action_lower = action.name.lower()

        # Check keyword matches
        goal_keywords = self._extract_keywords(goal_lower)
        action_keywords = self._extract_keywords(action_lower)

        if not goal_keywords:
            return 0.5

        matches = len(set(goal_keywords) & set(action_keywords))
        alignment = matches / len(goal_keywords)

        # Boost for specific matches
        if "research" in goal_lower and "search" in action_lower:
            alignment += 0.3
        elif "file" in goal_lower and "data" in action_lower:
            alignment += 0.3
        elif "code" in goal_lower and ("execute" in action_lower or "code" in action_lower):
            alignment += 0.3

        return min(1.0, alignment)

    def _calculate_context_relevance(self, action: Action, context: Dict[str, Any]) -> float:
        """Calculate relevance of action to current context."""

        relevance = 0.5  # Base relevance

        # Check if action has been recently used
        recent_actions = context.get("recent_actions", [])
        if action.name in recent_actions:
            relevance -= 0.2  # Penalize repetition

        # Check context-specific preferences
        context_type = context.get("context_type", "general")

        if context_type == "research" and action.name == "search_information":
            relevance += 0.4
        elif context_type == "analysis" and action.name in ["load_data", "analyze_sources"]:
            relevance += 0.4
        elif context_type == "development" and action.name == "execute_code":
            relevance += 0.4

        # Check parameter relevance
        if action.parameters:
            param_relevance = self._evaluate_parameter_relevance(action.parameters, context)
            relevance += param_relevance * 0.3

        return max(0.0, min(1.0, relevance))

    def _evaluate_parameter_relevance(
        self, parameters: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """Evaluate how relevant action parameters are to the context."""

        relevance = 0.0

        # Check if parameters match context needs
        if "query" in parameters and "search_terms" in context:
            common_terms = set(str(parameters["query"]).lower().split()) & set(
                context["search_terms"]
            )
            if common_terms:
                relevance += len(common_terms) / max(len(str(parameters["query"]).split()), 1)

        if "filepath" in parameters and "target_files" in context:
            if parameters["filepath"] in context["target_files"]:
                relevance += 1.0

        if "code" in parameters and "code_context" in context:
            if context["code_context"]:
                relevance += 0.5

        return min(1.0, relevance)

    def _get_historical_performance_score(self, action: Action) -> float:
        """Get score based on historical performance of similar actions."""

        action_key = f"{action.tool_name}_{action.name}"

        if action_key in self.action_history:
            history = self.action_history[action_key]

            # Calculate success rate
            total_attempts = history.get("total_attempts", 0)
            successes = history.get("successes", 0)

            if total_attempts > 0:
                success_rate = successes / total_attempts

                # Calculate average success score
                scores = history.get("success_scores", [])
                avg_score = sum(scores) / len(scores) if scores else 0.5

                # Combine success rate and score
                return (success_rate * 0.6) + (avg_score * 0.4)

        return 0.5  # Default score for unseen actions

    def _calculate_prerequisite_score(self, action: Action, completed_actions: List[str]) -> float:
        """Calculate score based on prerequisite completion."""

        prerequisites = action.prerequisites or []

        if not prerequisites:
            return 1.0  # No prerequisites, full score

        completed_prerequisites = [
            prereq for prereq in prerequisites if prereq in completed_actions
        ]

        if len(prerequisites) == 0:
            return 1.0

        completion_rate = len(completed_prerequisites) / len(prerequisites)

        # Additional boost for recent completions
        if len(completed_prerequisites) == len(prerequisites):
            return 1.0
        elif len(completed_prerequisites) > 0:
            return 0.7 + (completion_rate * 0.3)
        else:
            return 0.2  # Low score if prerequisites not met

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""

        # Common stop words to filter out
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "up",
            "about",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "among",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "can",
        }

        # Extract words and filter
        words = text.lower().split()
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]

        return keywords

    def _store_selection_rationale(
        self, action: Action, goal: Goal, context: Dict[str, Any], score: float
    ):
        """Store rationale for action selection for learning."""

        _rationale = {
            "action": action.name,
            "goal": goal.description,
            "context_type": context.get("context_type", "general"),
            "score": score,
            "timestamp": context.get("timestamp"),
            "parameters": action.parameters,
            "reasoning": {
                "goal_alignment": self._calculate_goal_alignment(action, goal),
                "context_relevance": self._calculate_context_relevance(action, context),
                "historical_performance": self._get_historical_performance_score(action),
            },
        }

        # Store in action history
        action_key = f"{action.tool_name}_{action.name}"
        if action_key not in self.action_history:
            self.action_history[action_key] = {
                "total_attempts": 0,
                "successes": 0,
                "success_scores": [],
            }

        self.action_history[action_key]["total_attempts"] += 1

    def update_action_performance(self, action: Action, success: bool, success_score: float):
        """Update performance tracking for an action."""

        action_key = f"{action.tool_name}_{action.name}"

        if action_key in self.action_history:
            history = self.action_history[action_key]

            if success:
                history["successes"] += 1
                history["success_scores"].append(success_score)

                # Keep only recent scores (last 100)
                if len(history["success_scores"]) > 100:
                    history["success_scores"] = history["success_scores"][-100:]

            logger.debug(f"Updated performance for {action_key}: {success}, score: {success_score}")

    def update_action_score(self, action: Action, success_score: float):
        """Compatibility method required by agent.py"""
        success = success_score > 0.5
        self.update_action_performance(action, success, success_score)
        logger.debug(f"Updated action score: {action.name} -> {success_score}")

    def get_action_recommendations(
        self, goal: Goal, available_actions: List[Action]
    ) -> List[Tuple[Action, float]]:
        """Get ranked recommendations for actions given a goal."""

        if not available_actions:
            return []

        recommendations = []

        for action in available_actions:
            alignment = self._calculate_goal_alignment(action, goal)
            performance = self._get_historical_performance_score(action)
            type_score = self._get_action_type_score(action)

            # Combined recommendation score
            rec_score = (alignment * 0.5) + (performance * 0.3) + (type_score * 0.2)

            recommendations.append((action, rec_score))

        # Sort by recommendation score
        recommendations.sort(key=lambda x: x[1], reverse=True)

        return recommendations

    def learn_from_success_pattern(
        self, goal: Goal, successful_actions: List[Action], success_score: float
    ):
        """Learn from successful action sequences."""

        if success_score > 0.7:  # Only learn from highly successful episodes
            goal_key = self._create_goal_pattern_key(goal.description)

            if goal_key not in self.goal_patterns:
                self.goal_patterns[goal_key] = []

            # Store successful pattern
            pattern = {
                "actions": [action.name for action in successful_actions],
                "score": success_score,
                "timestamp": goal.created_at.isoformat() if hasattr(goal, "created_at") else None,
            }

            self.goal_patterns[goal_key].append(pattern)

            # Keep only best patterns
            self.goal_patterns[goal_key].sort(key=lambda x: x["score"], reverse=True)
            self.goal_patterns[goal_key] = self.goal_patterns[goal_key][:10]  # Keep top 10

            logger.info(f"Learned pattern for {goal_key}: {' -> '.join(pattern['actions'])}")

    def _create_goal_pattern_key(self, goal_description: str) -> str:
        """Create a pattern key from goal description."""

        keywords = self._extract_keywords(goal_description.lower())
        if len(keywords) >= 3:
            return "_".join(keywords[:3])
        elif len(keywords) >= 2:
            return "_".join(keywords[:2])
        elif len(keywords) >= 1:
            return keywords[0]
        else:
            return "general"  # Fallback
