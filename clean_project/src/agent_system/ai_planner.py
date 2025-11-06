"""
AI-powered hierarchical planner with real intelligence.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import Action, Plan, Goal
try:
    from .reasoning_engine import reasoning_engine
except ImportError:
    reasoning_engine = None

logger = logging.getLogger(__name__)


class AIPlanner:
    """AI-powered planner that uses reasoning engine for intelligent planning."""
    
    def __init__(self):
        self.reasoning_engine = reasoning_engine
        self.goal_cache = {}  # Cache analyzed goals
        
    def create_intelligent_plan(self, goal: Goal, available_tools: List[str], context: Dict[str, Any] = None) -> Plan:
        """Create an intelligent plan using AI reasoning."""
        
        logger.info(f"Creating intelligent plan for goal: {goal.description}")
        
        if self.reasoning_engine is None:
            # Fallback to simple planning
            return self._create_simple_plan(goal, available_tools)
        
        # Analyze the goal with AI (use enhanced method if available)
        if hasattr(self.reasoning_engine, 'enhanced_analyze_goal'):
            goal_analysis = self.reasoning_engine.enhanced_analyze_goal(goal.description)
        else:
            goal_analysis = self.reasoning_engine.analyze_goal(goal.description)

        # Generate action plan using AI
        actions = self.reasoning_engine.generate_action_plan(goal_analysis)
        
        # Optimize actions based on available tools
        optimized_actions = self._optimize_actions_for_tools(actions, available_tools)
        
        # Calculate plan metrics
        estimated_cost = self._estimate_plan_cost(optimized_actions)
        confidence = goal_analysis["confidence"]
        
        # Create plan
        plan = Plan(
            goal_id=goal.id,
            actions=optimized_actions,
            estimated_cost=estimated_cost,
            confidence=confidence
        )
        
        # Store analysis for learning
        self.goal_cache[goal.id] = goal_analysis
        
        logger.info(f"Created plan with {len(optimized_actions)} actions, confidence: {confidence:.2f}")
        
        return plan
    
    def _optimize_actions_for_tools(self, actions: List[Dict], available_tools: List[str]) -> List[Action]:
        """Optimize actions to match available tools."""
        
        optimized = []
        
        for action_data in actions:
            tool_name = action_data["tool_name"]
            
            # Check if tool is available
            if tool_name in available_tools:
                # Create Action object
                action = Action(
                    id=action_data["id"],
                    name=action_data["name"],
                    tool_name=tool_name,
                    parameters=action_data["parameters"],
                    expected_outcome=action_data.get("estimated_outcome", "task_completed"),
                    cost=self._estimate_action_cost(action_data),
                    prerequisites=action_data.get("prerequisites", [])
                )
                optimized.append(action)
            else:
                # Try to map to alternative tool
                alternative_tool = self._find_alternative_tool(tool_name, available_tools)
                if alternative_tool:
                    action_data["tool_name"] = alternative_tool
                    action = Action(
                        id=action_data["id"],
                        name=action_data["name"],
                        tool_name=alternative_tool,
                        parameters=action_data["parameters"],
                        expected_outcome=action_data.get("estimated_outcome", "task_completed"),
                        cost=self._estimate_action_cost(action_data),
                        prerequisites=action_data.get("prerequisites", [])
                    )
                    optimized.append(action)
                    logger.info(f"Mapped {tool_name} to {alternative_tool}")
        
        return optimized
    
    def _find_alternative_tool(self, original_tool: str, available_tools: List[str]) -> Optional[str]:
        """Find alternative tool when original is not available."""
        
        tool_mapping = {
            "web_search": ["generic_tool"],
            "file_reader": ["generic_tool"],
            "code_executor": ["generic_tool"],
            "file_writer": ["generic_tool"],
            "generic_tool": ["generic_tool"]
        }
        
        alternatives = tool_mapping.get(original_tool, [])
        for alt in alternatives:
            if alt in available_tools:
                return alt
        
        return "generic_tool"  # Ultimate fallback
    
    def _estimate_action_cost(self, action_data: Dict[str, Any]) -> float:
        """Estimate cost for an action based on type and complexity."""
        
        base_costs = {
            "search_information": 0.3,
            "load_data": 0.2,
            "execute_code": 0.4,
            "analyze_sources": 0.3,
            "synthesize_findings": 0.2,
            "save_results": 0.1,
            "generic": 0.2
        }
        
        action_name = action_data.get("name", "generic")
        base_cost = base_costs.get(action_name, base_costs["generic"])
        
        # Adjust based on parameters complexity
        parameters = action_data.get("parameters", {})
        complexity_factor = 1.0
        
        if "query" in parameters:
            complexity_factor += len(str(parameters["query"])) / 1000
        
        if "code" in parameters:
            complexity_factor += len(str(parameters["code"])) / 100
        
        return base_cost * complexity_factor
    
    def _estimate_plan_cost(self, actions: List[Action]) -> float:
        """Estimate total cost of a plan."""
        return sum(action.cost for action in actions)
    
    def refine_plan_based_on_feedback(self, original_plan: Plan, feedback: Dict[str, Any]) -> Plan:
        """Refine plan based on action feedback and outcomes."""
        
        logger.info("Refining plan based on feedback")
        
        # Analyze what went wrong or could be improved
        failed_actions = feedback.get("failed_actions", [])
        slow_actions = feedback.get("slow_actions", [])
        unexpected_outcomes = feedback.get("unexpected_outcomes", [])
        
        # Create refined plan
        refined_actions = []
        
        for action in original_plan.actions:
            action_id = action.id
            
            # Skip or modify failed actions
            if any(failed_id in action_id for failed_id in failed_actions):
                # Try alternative approach
                alternative = self._create_alternative_action(action)
                if alternative:
                    refined_actions.append(alternative)
                    logger.info(f"Created alternative for failed action: {action_id}")
                    continue
            
            # Optimize slow actions
            if any(slow_id in action_id for slow_id in slow_actions):
                # Reduce complexity or use faster tool
                optimized_action = self._optimize_action(action)
                refined_actions.append(optimized_action)
                logger.info(f"Optimized slow action: {action_id}")
                continue
            
            # Keep successful actions
            refined_actions.append(action)
        
        # Create new plan with refined actions
        refined_plan = Plan(
            goal_id=original_plan.goal_id,
            actions=refined_actions,
            estimated_cost=self._estimate_plan_cost(refined_actions),
            confidence=original_plan.confidence * 0.9  # Slightly reduce confidence for refined plans
        )
        
        return refined_plan
    
    def _create_alternative_action(self, failed_action: Action) -> Optional[Action]:
        """Create alternative action when original fails."""
        
        # Simple fallback logic
        if failed_action.tool_name == "web_search":
            # Fallback to generic processing
            return Action(
                id=f"{failed_action.id}_fallback",
                name="process_offline",
                tool_name="generic_tool",
                parameters={"task": f"Offline analysis of: {failed_action.parameters.get('query', 'unknown')}"},
                expected_outcome="offline_analysis",
                cost=failed_action.cost * 0.5,
                prerequisites=failed_action.prerequisites
            )
        
        return None
    
    def _optimize_action(self, slow_action: Action) -> Action:
        """Optimize a slow action for better performance."""
        
        # Simple optimization: reduce parameters or use simpler approach
        optimized_params = slow_action.parameters.copy()
        
        if "max_results" in optimized_params:
            optimized_params["max_results"] = min(5, optimized_params["max_results"])
        
        if "timeout" in optimized_params:
            optimized_params["timeout"] = max(5, optimized_params["timeout"])
        
        return Action(
            id=slow_action.id,
            name=slow_action.name,
            tool_name=slow_action.tool_name,
            parameters=optimized_params,
            expected_outcome=slow_action.expected_outcome,
            cost=slow_action.cost * 0.8,  # Reduced cost estimate
            prerequisites=slow_action.prerequisites
        )


# Replace the original HierarchicalPlanner with AI-powered version
class AIHierarchicalPlanner(AIPlanner):
    """AI-powered hierarchical planner (drop-in replacement)."""
    
    def create_plan(self, goal: Goal, available_tools: List[str], context: Dict[str, Any] = None) -> Plan:
        """Create plan using AI reasoning."""
        return self.create_intelligent_plan(goal, available_tools, context)
    
    def create_plan_with_fallback(self, goal: Goal, available_tools: List[str], context: Dict[str, Any] = None) -> Plan:
        """Create plan with fallback strategies."""
        try:
            return self.create_intelligent_plan(goal, available_tools, context)
        except Exception as e:
            logger.warning(f"AI planning failed: {e}, using fallback")
            return self._create_fallback_plan(goal, available_tools)
    
    def _create_fallback_plan(self, goal: Goal, available_tools: List[str]) -> Plan:
        """Create simple fallback plan when AI planning fails."""
        
        simple_action = Action(
            id="fallback_action",
            name="generic_task",
            tool_name="generic_tool" if "generic_tool" in available_tools else available_tools[0],
            parameters={"goal": goal.description},
            expected_outcome="task_attempted",
            cost=0.5
        )
        
        return Plan(
            goal_id=goal.id,
            actions=[simple_action],
            estimated_cost=0.5,
            confidence=0.3
        )
    
    def _create_simple_plan(self, goal: Goal, available_tools: List[str]) -> Plan:
        """Create a simple plan when AI reasoning is not available."""
        
        # Simple goal-based action selection
        goal_lower = goal.description.lower()
        
        if any(word in goal_lower for word in ["research", "find", "search"]):
            action = Action(
                id="simple_search",
                name="search_information",
                tool_name="web_search" if "web_search" in available_tools else available_tools[0],
                parameters={"query": goal.description},
                expected_outcome="information_found",
                cost=0.3
            )
        elif any(word in goal_lower for word in ["analyze", "process", "data"]):
            action = Action(
                id="simple_analysis",
                name="analyze_data",
                tool_name="file_reader" if "file_reader" in available_tools else available_tools[0],
                parameters={"task": goal.description},
                expected_outcome="analysis_completed",
                cost=0.4
            )
        else:
            action = Action(
                id="simple_task",
                name="generic_task",
                tool_name="generic_tool" if "generic_tool" in available_tools else available_tools[0],
                parameters={"goal": goal.description},
                expected_outcome="task_completed",
                cost=0.5
            )
        
        return Plan(
            goal_id=goal.id,
            actions=[action],
            estimated_cost=action.cost,
            confidence=0.5
        )