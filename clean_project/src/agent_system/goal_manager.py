from __future__ import annotations

import heapq
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .models import Goal, GoalStatus

logger = logging.getLogger(__name__)


class GoalManager:
    """
    Manages goals with priorities, dependencies, and dynamic updates.
    """

    def __init__(self) -> None:
        self.goals: Dict[str, Goal] = {}
        self.active_goals: List[Tuple[float, str]] = []
        self.goal_dependencies: Dict[str, List[str]] = defaultdict(list)
        self.goal_counter = 0

    def add_goal(
        self,
        description: str,
        priority: float = 0.5,
        parent_id: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Goal:
        """Add a new goal to the system."""
        self.goal_counter += 1
        goal_id = f"goal_{self.goal_counter}"

        goal = Goal(
            id=goal_id,
            description=description,
            priority=priority,
            parent_goal_id=parent_id,
            constraints=constraints or {},
        )

        self.goals[goal_id] = goal

        if parent_id and parent_id in self.goals:
            self.goals[parent_id].subgoals.append(goal_id)

        heapq.heappush(self.active_goals, (-priority, goal_id))

        logger.info("Added goal: %s - %s (priority: %s)", goal_id, description, priority)
        return goal

    def get_next_goal(self) -> Optional[Goal]:
        """Get the highest priority pending goal."""
        while self.active_goals:
            _, goal_id = heapq.heappop(self.active_goals)

            if goal_id not in self.goals:
                continue

            goal = self.goals[goal_id]

            if goal.status == GoalStatus.PENDING:
                if self._check_dependencies(goal_id):
                    goal.status = GoalStatus.IN_PROGRESS
                    return goal

                goal.status = GoalStatus.BLOCKED
                heapq.heappush(self.active_goals, (-goal.priority, goal_id))

        return None

    def update_goal_status(self, goal_id: str, status: GoalStatus, progress: float | None = None) -> None:
        """Update goal status and progress."""
        if goal_id not in self.goals:
            return

        goal = self.goals[goal_id]
        goal.status = status

        if progress is not None:
            goal.progress = min(max(progress, 0.0), 1.0)

        if goal.parent_goal_id:
            self._update_parent_progress(goal.parent_goal_id)

        if status == GoalStatus.COMPLETED:
            self._unblock_dependent_goals(goal_id)

    def add_dependency(self, goal_id: str, depends_on: str) -> None:
        """Add a dependency between goals."""
        self.goal_dependencies[goal_id].append(depends_on)

    def get_goal_hierarchy(self) -> Dict[str, Any]:
        """Get a tree representation of all goals."""
        root_goals = [goal for goal in self.goals.values() if goal.parent_goal_id is None]

        def build_tree(goal: Goal) -> Dict[str, Any]:
            return {
                "id": goal.id,
                "description": goal.description,
                "status": goal.status.value,
                "progress": goal.progress,
                "priority": goal.priority,
                "subgoals": [
                    build_tree(self.goals[sub_id])
                    for sub_id in goal.subgoals
                    if sub_id in self.goals
                ],
            }

        return {"goals": [build_tree(goal) for goal in root_goals]}

    def _check_dependencies(self, goal_id: str) -> bool:
        """Check if all dependencies for a goal are met."""
        dependencies = self.goal_dependencies.get(goal_id, [])
        return all(
            self.goals[dep_id].status == GoalStatus.COMPLETED
            for dep_id in dependencies
            if dep_id in self.goals
        )

    def _update_parent_progress(self, parent_id: str) -> None:
        """Update parent goal progress based on subgoals."""
        if parent_id not in self.goals:
            return

        parent = self.goals[parent_id]
        if not parent.subgoals:
            return

        total_progress = sum(
            self.goals[sub_id].progress for sub_id in parent.subgoals if sub_id in self.goals
        )
        parent.progress = total_progress / len(parent.subgoals)

        if parent.progress >= 1.0:
            parent.status = GoalStatus.COMPLETED

    def _unblock_dependent_goals(self, completed_goal_id: str) -> None:
        """Unblock goals that were waiting for this goal."""
        for goal_id, dependencies in self.goal_dependencies.items():
            if completed_goal_id in dependencies:
                goal = self.goals.get(goal_id)
                if goal and goal.status == GoalStatus.BLOCKED and self._check_dependencies(goal_id):
                    goal.status = GoalStatus.PENDING
                    heapq.heappush(self.active_goals, (-goal.priority, goal_id))

    def has_pending_goals(self) -> bool:
        """Return True if any goals are pending or queued for processing."""
        if any(g.status in (GoalStatus.PENDING, GoalStatus.BLOCKED) for g in self.goals.values()):
            return True
        return len(self.active_goals) > 0
