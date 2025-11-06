from __future__ import annotations

import unittest

from agent_system import main


class CLITests(unittest.TestCase):
    def test_main_accepts_cli_arguments(self):
        status = main(["--max-cycles", "1", "--goal", "Quick task::0.4", "--log-level", "ERROR"])

        self.assertIsInstance(status, dict)
        self.assertIn("goals", status)
        goals = status["goals"]["goals"]
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["description"], "Quick task")
        self.assertLessEqual(goals[0]["progress"], 1.0)
        self.assertFalse(status["is_running"])

    def test_goal_priority_default_applied(self):
        status = main(["--max-cycles", "0", "--goal", "Default priority task", "--log-level", "ERROR"])
        goals = status["goals"]["goals"]
        self.assertEqual(goals[0]["priority"], 0.5)


if __name__ == "__main__":
    unittest.main()
