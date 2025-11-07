from __future__ import annotations

import unittest

from agent_system.goal_manager import GoalManager
from agent_system.models import GoalStatus


class GoalManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = GoalManager()

    def test_highest_priority_goal_selected_first(self):
        self.manager.add_goal("Low priority task", priority=0.1)
        high = self.manager.add_goal("High priority task", priority=0.9)

        next_goal = self.manager.get_next_goal()
        self.assertIsNotNone(next_goal)
        self.assertEqual(next_goal.id, high.id)

    def test_dependencies_block_until_completed(self):
        parent = self.manager.add_goal("Parent task", priority=0.5)
        child = self.manager.add_goal("Child task", priority=0.7, parent_id=parent.id)
        self.manager.add_dependency(child.id, parent.id)

        # First call should return parent since child is blocked
        first = self.manager.get_next_goal()
        self.assertEqual(first.id, parent.id)

        # Complete parent and ensure child becomes available
        self.manager.update_goal_status(parent.id, GoalStatus.COMPLETED, progress=1.0)
        second = self.manager.get_next_goal()
        self.assertEqual(second.id, child.id)


if __name__ == "__main__":
    unittest.main()
