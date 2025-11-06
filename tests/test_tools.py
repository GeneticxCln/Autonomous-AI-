from __future__ import annotations

import unittest

from agent_system.models import Action, ActionStatus
from agent_system.tools import GenericTool, ToolRegistry


class ToolRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry()
        self.registry.register_tool(GenericTool())

    def test_generic_tool_execution_succeeds(self):
        action = Action(
            id="goal_1_action_0",
            name="generic_step",
            tool_name="generic_tool",
            parameters={"goal": "Demo goal", "context": {}, "action": "generic_step"},
            expected_outcome="task_completed",
            cost=0.2,
        )

        observation = self.registry.execute_action(action)
        self.assertEqual(observation.status, ActionStatus.SUCCESS)

        stats = self.registry.get_tool_stats()["generic_tool"]
        self.assertEqual(stats["successes"], 1)
        self.assertEqual(stats["failures"], 0)

    def test_missing_tool_reports_failure(self):
        action = Action(
            id="goal_1_action_1",
            name="missing_tool_step",
            tool_name="missing_tool",
            parameters={},
            expected_outcome="task_completed",
            cost=0.1,
        )

        observation = self.registry.execute_action(action, retry=False)
        self.assertEqual(observation.status, ActionStatus.FAILURE)


if __name__ == "__main__":
    unittest.main()
