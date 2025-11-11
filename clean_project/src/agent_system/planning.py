from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .models import Action, Goal, Plan

logger = logging.getLogger(__name__)


class PlanningStrategy(ABC):
    """Abstract base class for planning strategies."""

    @abstractmethod
    def create_plan(self, goal: Goal, available_tools: List[str], context: Dict[str, Any]) -> Plan:
        raise NotImplementedError


class HierarchicalPlanner(PlanningStrategy):
    """
    Hierarchical Task Network (HTN) style planner that breaks down high-level goals
    into concrete action sequences.
    """

    def __init__(self) -> None:
        self.decomposition_rules = self._init_decomposition_rules()
        self.action_templates = self._init_action_templates()

    def _init_decomposition_rules(self) -> Dict[str, List[str]]:
        """Define how to decompose abstract goals into subgoals."""
        return {
            "research_topic": [
                "search_information",
                "analyze_results",
                "synthesize_findings",
            ],
            "create_document": [
                "gather_requirements",
                "draft_content",
                "review_and_edit",
            ],
            "analyze_data": ["load_data", "process_data", "visualize_results"],
            "web_task": ["navigate_to_page", "extract_information", "verify_data"],
            "code_task": [
                "understand_requirements",
                "design_solution",
                "implement_code",
                "test_code",
            ],
        }

    def _init_action_templates(self) -> Dict[str, Dict[str, Any]]:
        """Define templates for concrete actions."""
        return {
            "search_information": {
                "tool": "web_search",
                "cost": 0.3,
                "expected_outcome": "relevant_information",
            },
            "load_data": {
                "tool": "file_reader",
                "cost": 0.2,
                "expected_outcome": "data_loaded",
            },
            "process_data": {
                "tool": "generic_tool",
                "cost": 0.4,
                "expected_outcome": "data_processed",
            },
            "visualize_results": {
                "tool": "generic_tool",
                "cost": 0.4,
                "expected_outcome": "results_visualized",
            },
            "analyze_results": {
                "tool": "generic_tool",
                "cost": 0.4,
                "expected_outcome": "analysis_completed",
            },
            "synthesize_findings": {
                "tool": "generic_tool",
                "cost": 0.4,
                "expected_outcome": "findings_synthesized",
            },
            "gather_requirements": {
                "tool": "generic_tool",
                "cost": 0.3,
                "expected_outcome": "requirements_collected",
            },
            "draft_content": {
                "tool": "generic_tool",
                "cost": 0.5,
                "expected_outcome": "draft_created",
            },
            "review_and_edit": {
                "tool": "generic_tool",
                "cost": 0.4,
                "expected_outcome": "content_refined",
            },
            "navigate_to_page": {
                "tool": "generic_tool",
                "cost": 0.2,
                "expected_outcome": "page_opened",
            },
            "extract_information": {
                "tool": "generic_tool",
                "cost": 0.3,
                "expected_outcome": "information_extracted",
            },
            "verify_data": {
                "tool": "generic_tool",
                "cost": 0.3,
                "expected_outcome": "data_verified",
            },
            "understand_requirements": {
                "tool": "generic_tool",
                "cost": 0.3,
                "expected_outcome": "requirements_understood",
            },
            "design_solution": {
                "tool": "generic_tool",
                "cost": 0.5,
                "expected_outcome": "solution_designed",
            },
            "implement_code": {
                "tool": "code_executor",
                "cost": 0.8,
                "expected_outcome": "working_code",
            },
            "test_code": {
                "tool": "generic_tool",
                "cost": 0.4,
                "expected_outcome": "code_tested",
            },
            "execute_generic_task": {
                "tool": "generic_tool",
                "cost": 0.5,
                "expected_outcome": "task_completed",
            },
        }

    def create_plan(self, goal: Goal, available_tools: List[str], context: Dict[str, Any]) -> Plan:
        """Create a hierarchical plan for the goal."""
        goal_type = self._classify_goal(goal.description)
        subgoals = self.decomposition_rules.get(goal_type, ["execute_generic_task"])

        actions: List[Action] = []
        total_cost = 0.0

        for index, subgoal in enumerate(subgoals):
            action = self._create_action(subgoal, index, goal, context)
            actions.append(action)
            total_cost += action.cost

        confidence = self._calculate_confidence(actions, available_tools, context)

        return Plan(
            goal_id=goal.id,
            actions=actions,
            estimated_cost=total_cost,
            confidence=confidence,
        )

    def _classify_goal(self, description: str) -> str:
        """Classify goal type based on description."""
        desc_lower = description.lower()

        if any(kw in desc_lower for kw in ["research", "find", "search", "learn"]):
            return "research_topic"
        if any(kw in desc_lower for kw in ["write", "create", "document", "report"]):
            return "create_document"
        if any(kw in desc_lower for kw in ["analyze", "data", "statistics"]):
            return "analyze_data"
        if any(kw in desc_lower for kw in ["browse", "web", "website", "scrape"]):
            return "web_task"
        if any(kw in desc_lower for kw in ["code", "program", "implement", "develop"]):
            return "code_task"
        return "generic_task"

    def _create_action(
        self, subgoal: str, index: int, goal: Goal, context: Dict[str, Any]
    ) -> Action:
        """Create a concrete action from a subgoal."""
        template = self.action_templates.get(
            subgoal,
            {"tool": "generic_tool", "cost": 0.5, "expected_outcome": "task_completed"},
        )

        prerequisites = [f"{goal.id}_action_{i}" for i in range(index)]

        return Action(
            id=f"{goal.id}_action_{index}",
            name=subgoal,
            tool_name=template["tool"],
            parameters=self._build_parameters(subgoal, goal, context, template),
            expected_outcome=template["expected_outcome"],
            cost=template["cost"],
            prerequisites=prerequisites,
        )

    def _build_parameters(
        self,
        subgoal: str,
        goal: Goal,
        context: Dict[str, Any],
        template: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Assemble parameters for an action so tools receive the arguments they expect.
        Includes goal/context metadata for downstream components.
        """
        parameters: Dict[str, Any] = {
            "goal": goal.description,
            "context": context,
        }

        tool_name = template["tool"]

        if tool_name == "web_search":
            query = goal.constraints.get("query") if goal.constraints else None
            parameters["query"] = query or goal.description
        elif tool_name == "file_reader":
            filepath = goal.constraints.get("filepath") if goal.constraints else None
            if not filepath and context:
                filepath = context.get("default_filepath")
            parameters["filepath"] = filepath or "data/input.json"
        elif tool_name == "code_executor":
            code_snippet = goal.constraints.get("code") if goal.constraints else None
            if not code_snippet and context:
                code_snippet = context.get("code_snippet")
            parameters["code"] = (
                code_snippet
                or f"# placeholder for '{goal.description}'\nprint('Executing placeholder task')"
            )
        else:
            if "parameters" in template:
                parameters.update(template["parameters"])
            parameters.setdefault("action", subgoal)

        return parameters

    def _calculate_confidence(
        self, actions: List[Action], available_tools: List[str], context: Dict[str, Any]
    ) -> float:
        """Calculate confidence in the plan."""
        if not actions:
            return 0.0

        tools_available = sum(1 for action in actions if action.tool_name in available_tools) / len(
            actions
        )

        context_score = min(len(context) / 10.0, 1.0) if context else 0.0

        return (tools_available * 0.7) + (context_score * 0.3)
