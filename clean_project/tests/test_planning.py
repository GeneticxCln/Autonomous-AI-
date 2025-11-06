from __future__ import annotations

import unittest

from agent_system.models import Goal
from agent_system.planning import HierarchicalPlanner


class PlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = HierarchicalPlanner()
        self.available_tools = ["generic_tool", "code_executor", "web_search", "file_reader"]

    def test_create_document_plan(self):
        goal = Goal(id="goal_1", description="Create project report", priority=0.9)
        plan = self.planner.create_plan(goal, self.available_tools, context={})

        action_names = [action.name for action in plan.actions]
        self.assertEqual(action_names, ["gather_requirements", "draft_content", "review_and_edit"])
        self.assertGreater(plan.confidence, 0.0)

    def test_code_task_includes_code_executor(self):
        goal = Goal(id="goal_2", description="Implement code module", priority=0.6)
        plan = self.planner.create_plan(goal, self.available_tools, context={})

        tool_names = {action.tool_name for action in plan.actions}
        self.assertIn("code_executor", tool_names)


if __name__ == "__main__":
    unittest.main()
