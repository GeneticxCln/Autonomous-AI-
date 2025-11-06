from __future__ import annotations

import unittest

from agent_system.action_selector import ActionSelector
from agent_system.models import Action, Goal


class ActionSelectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.selector = ActionSelector()
        self.goal = Goal(id="goal_1", description="Analyze data reports", priority=0.5)

    def _create_action(self, idx: int, name: str, cost: float, prerequisites=None) -> Action:
        return Action(
            id=f"{self.goal.id}_action_{idx}",
            name=name,
            tool_name="generic_tool",
            parameters={"goal": self.goal.description, "context": {}, "action": name},
            expected_outcome="task_completed",
            cost=cost,
            prerequisites=prerequisites or [],
        )

    def test_prerequisites_enforced(self):
        without_prereq = self._create_action(0, "prepare_data", 0.2)
        with_prereq = self._create_action(1, "process_data", 0.4, prerequisites=[without_prereq.id])

        selected = self.selector.select_action(
            [with_prereq, without_prereq],
            self.goal,
            context={},
            completed_actions=[],
        )
        self.assertEqual(selected.id, without_prereq.id)

    def test_learning_updates_score(self):
        action = self._create_action(0, "evaluate_model", 0.5)

        initial = self.selector._score_action(action, self.goal, context={})
        self.selector.update_action_score(action, success_score=1.0)
        updated = self.selector._score_action(action, self.goal, context={})

        self.assertGreaterEqual(updated, initial)


if __name__ == "__main__":
    unittest.main()
