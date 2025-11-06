from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .action_selector import ActionSelector
from .config_simple import settings
from .goal_manager import GoalManager
from .learning import LearningSystem
from .memory import MemorySystem
from .models import Action, ActionStatus, Goal, GoalStatus, Plan
from .observation import ObservationAnalyzer
from .planning import HierarchicalPlanner
from .tools import (
    CodeExecutorTool,
    FileReaderTool,
    FileWriterTool,
    GenericTool,
    ToolRegistry,
    WebSearchTool,
)
from .enhanced_tools import EnhancedToolRegistry
from .enhanced_persistence import load_all, save_all, get_storage_info

# Import intelligent components
from .reasoning_engine import reasoning_engine
from .ai_planner import AIHierarchicalPlanner
from .intelligent_action_selector import IntelligentActionSelector
from .intelligent_observation_analyzer import intelligent_analyzer
from .cross_session_learning import cross_session_learning
from .ai_debugging import ai_debugger
from .ai_performance_monitor import ai_performance_monitor

logger = logging.getLogger(__name__)


class AutonomousAgent:
    """Main agent that integrates all subsystems."""

    def __init__(self):
        self.goal_manager = GoalManager()
        self.planner = AIHierarchicalPlanner()  # Use AI-powered planner
        self.action_selector = IntelligentActionSelector()  # Use intelligent action selector
        self.tool_registry = EnhancedToolRegistry()
        self.memory_system = MemorySystem()
        self.observation_analyzer = intelligent_analyzer  # Use intelligent observation analyzer
        self.learning_system = LearningSystem()
        self.cross_session_learning = cross_session_learning  # Enable cross-session learning
        self.ai_debugger = ai_debugger  # Enable AI debugging and explainability
        self.performance_monitor = ai_performance_monitor  # Enable real-time performance monitoring

        self.current_goal: Optional[Goal] = None
        self.current_plan: Optional[Plan] = None
        self.completed_actions: List[str] = []
        self.is_running = False

        # Enable real tools if APIs are configured
        if self._should_use_real_tools():
            self.tool_registry.enable_real_tools()
            logger.info("Agent initialized with real tools enabled")
        else:
            logger.info("Agent initialized with mock tools (no API keys configured)")

        self._register_default_tools()
        # Load persisted state if present
        load_all(self)

        # Log storage information
        storage_info = get_storage_info()
        logger.info(f"Agent initialized with {storage_info['storage_type']} persistence")
        if storage_info.get('database_stats'):
            total_records = sum(storage_info['database_stats'].values())
            logger.info(f"Database contains {total_records} total records")

    def _should_use_real_tools(self) -> bool:
        """Determine if real tools should be used based on configuration."""
        # Prefer explicit environment setting; otherwise, enable by default.
        from .config_simple import get_api_key, settings
        if hasattr(settings, "USE_REAL_TOOLS"):
            return bool(settings.USE_REAL_TOOLS)
        return bool(get_api_key("serpapi") or get_api_key("bing") or get_api_key("google"))

    def _register_default_tools(self):
        """Register default tools."""
        self.tool_registry.register_tool(GenericTool())
        self.tool_registry.register_tool(FileReaderTool())
        self.tool_registry.register_tool(FileWriterTool())
        self.tool_registry.register_tool(CodeExecutorTool())
        # Only register web search when not in terminal-only mode
        if not settings.TERMINAL_ONLY:
            self.tool_registry.register_tool(WebSearchTool())

    def add_goal(
        self,
        description: str,
        priority: float = 0.5,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Goal:
        """Add a new goal for the agent."""
        return self.goal_manager.add_goal(description, priority, constraints=constraints)

    def run(self, max_cycles: int = 100):
        """Run the agent for a maximum number of cycles."""
        self.is_running = True
        cycle = 0

        logger.info("Starting agent (max %s cycles)", max_cycles)

        while self.is_running and cycle < max_cycles:
            cycle += 1
            worked = self.run_cycle()

            if not worked:
                logger.info("Agent idle, no more work")
                break

        self.is_running = False
        logger.info("Agent stopped after %s cycles", cycle)

    def stop(self):
        """Stop the agent."""
        self.is_running = False
        # End cross-session learning session
        self.cross_session_learning.end_current_session()

    def run_cycle(self) -> bool:
        """Run one cycle of the agent loop."""
        if not self.current_goal:
            self.current_goal = self.goal_manager.get_next_goal()

            if not self.current_goal:
                logger.info("No pending goals")
                return False

            logger.info("Starting goal: %s", self.current_goal.description)

            # Check for cross-session learning patterns
            best_sequence = self.cross_session_learning.get_best_action_sequence(self.current_goal.description)
            if best_sequence:
                logger.info("Found cross-session pattern: %s", " -> ".join(best_sequence))

            # Log goal analysis decision and record performance metrics
            start_time = time.time() * 1000
            if hasattr(self.planner, 'reasoning_engine') and self.planner.reasoning_engine:
                if hasattr(self.planner.reasoning_engine, 'enhanced_analyze_goal'):
                    goal_analysis = self.planner.reasoning_engine.enhanced_analyze_goal(self.current_goal.description)
                else:
                    goal_analysis = self.planner.reasoning_engine.analyze_goal(self.current_goal.description)
                execution_time = (time.time() * 1000 - start_time)
                self.ai_debugger.log_goal_analysis(self.current_goal.description, goal_analysis, execution_time)

                # Record performance metrics
                confidence = goal_analysis.get('confidence', 0.0)
                self.performance_monitor.record_decision_metrics(
                    'goal_analysis', execution_time, confidence, True
                )

            context = self.memory_system.get_working_memory_context()
            self.current_plan = self.planner.create_plan(
                self.current_goal, self.tool_registry.get_available_tools(), context
            )

            suggestions = self.learning_system.suggest_improvements(
                self.current_goal, self.current_plan
            )
            if suggestions:
                logger.info("Learning suggestions: %s", suggestions)

            self.completed_actions = []

        if not self.current_plan:
            return False

        available_actions = [
            action for action in self.current_plan.actions if action.id not in self.completed_actions
        ]

        if not available_actions:
            self._finalize_goal(success=True)
            return True

        # Log action selection decision
        start_time = time.time() * 1000
        selected_action = self.action_selector.select_action(
            available_actions,
            self.current_goal,
            self.memory_system.get_working_memory_context(),
            self.completed_actions,
        )
        execution_time = (time.time() * 1000 - start_time)

        # Log the action selection decision with debugging info
        if hasattr(selected_action, '__dict__'):
            action_dict = {
                'name': selected_action.name,
                'id': selected_action.id,
                'tool_name': getattr(selected_action, 'tool_name', ''),
                'parameters': getattr(selected_action, 'parameters', {})
            }
        else:
            action_dict = selected_action if selected_action else None

        selection_criteria = {
            'final_score': 0.7,  # Placeholder - in real implementation, get from action selector
            'context_match': 0.8,
            'learning_bonus': 0.1
        }
        self.ai_debugger.log_action_selection(
            [{'name': a.name, 'id': a.id, 'tool_name': getattr(a, 'tool_name', '')} for a in available_actions],
            action_dict,
            selection_criteria,
            execution_time
        )

        # Record action selection performance metrics
        confidence = selection_criteria.get('final_score', 0.0)
        self.performance_monitor.record_decision_metrics(
            'action_selection', execution_time, confidence, selected_action is not None
        )

        if not selected_action:
            logger.warning("No suitable action found")
            self._finalize_goal(success=False)
            return True

        observation = self.tool_registry.execute_action(selected_action)

        # Log observation analysis decision
        start_time = time.time() * 1000
        analysis = self.observation_analyzer.analyze_observation(
            observation, selected_action.expected_outcome, self.current_goal
        )
        execution_time = (time.time() * 1000 - start_time)

        # Log the observation analysis decision
        self.ai_debugger.log_observation_analysis(
            {
                'status': observation.status.value,
                'result': str(observation.result)[:200] if observation.result else '',
                'tool_name': selected_action.tool_name
            },
            selected_action.expected_outcome,
            analysis,
            execution_time
        )

        # Record observation analysis performance metrics
        analysis_confidence = analysis.get('confidence', 0.0)
        self.performance_monitor.record_decision_metrics(
            'observation_analysis', execution_time, analysis_confidence, observation.status == ActionStatus.SUCCESS
        )

        logger.info("Action result: %s - %s", observation.status.value, analysis)

        success_score = 1.0 if observation.status == ActionStatus.SUCCESS else 0.0
        self.memory_system.store_memory(
            self.current_goal.id,
            selected_action,
            observation,
            {"goal_description": self.current_goal.description},
            success_score,
        )

        self.action_selector.update_action_score(selected_action, success_score)

        progress_increment = analysis.get("goal_progress", 0.0)
        new_progress = min(self.current_goal.progress + progress_increment, 1.0)
        self.goal_manager.update_goal_status(
            self.current_goal.id, GoalStatus.IN_PROGRESS, new_progress
        )

        if analysis.get("replanning_needed", False):
            logger.warning("Replanning needed due to unexpected outcomes")

        self.completed_actions.append(selected_action.id)

        recent_observations = [
            memory.observation for memory in self.memory_system.working_memory[-5:]
        ]
        anomalies = self.observation_analyzer.detect_anomalies(recent_observations)
        if anomalies:
            logger.warning("Anomalies detected: %s", anomalies)

        return True

    def _finalize_goal(self, success: bool):
        """Finalize current goal."""
        if not self.current_goal or not self.current_plan:
            return

        final_status = GoalStatus.COMPLETED if success else GoalStatus.FAILED
        self.goal_manager.update_goal_status(
            self.current_goal.id,
            final_status,
            1.0 if success else self.current_goal.progress,
        )

        actions_taken = [
            action
            for action in self.current_plan.actions
            if action.id in self.completed_actions
        ]
        observations = [
            memory.observation
            for memory in self.memory_system.working_memory
            if memory.goal_id == self.current_goal.id
        ]

        self.learning_system.learn_from_episode(
            self.current_goal, actions_taken, observations, success
        )

        # Learn from this goal for cross-session knowledge
        action_dicts = [
            {
                'id': action.id,
                'name': action.name,
                'tool_name': getattr(action, 'tool_name', ''),
                'parameters': getattr(action, 'parameters', {})
            }
            for action in actions_taken
        ]
        success_score = 1.0 if success else 0.0
        self.cross_session_learning.learn_from_goal(
            self.current_goal.description, action_dicts, success_score
        )

        # Record goal completion metrics
        self.performance_monitor.record_goal_metrics(success, 1, 1 if success else 0)

        # Record learning metrics
        knowledge_stats = self.cross_session_learning.get_knowledge_statistics()
        self.performance_monitor.record_learning_metrics(
            patterns_learned=knowledge_stats.get('total_patterns', 0),
            knowledge_base_size=knowledge_stats.get('high_confidence_patterns', 0),
            confidence_scores=[success_score]  # Simplified for now
        )

        logger.info("Goal %s: %s", final_status.value, self.current_goal.description)

        # Persist state after finishing a goal
        save_all(self)

        self.current_goal = None
        self.current_plan = None
        self.completed_actions = []

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive agent status."""
        return {
            "current_goal": self.current_goal.description if self.current_goal else None,
            "goals": self.goal_manager.get_goal_hierarchy(),
            "memory_stats": self.memory_system.get_memory_stats(),
            "tool_stats": self.tool_registry.get_tool_stats(),
            "learning_stats": self.learning_system.get_learning_stats(),
            "cross_session_learning_stats": self.cross_session_learning.get_knowledge_statistics(),
            "ai_debug_stats": self.ai_debugger.generate_debug_report(),
            "performance_monitor_stats": self.performance_monitor.get_current_performance(),
            "is_running": self.is_running,
        }

    def get_debug_explanation(self, decision_id: str = None) -> Dict[str, Any]:
        """Get AI decision explanations for debugging."""
        if decision_id:
            return self.ai_debugger.get_decision_explanation(decision_id)
        else:
            return self.ai_debugger.generate_debug_report()

    def save_debug_data(self) -> str:
        """Save all debug data to file."""
        return self.ai_debugger.save_debug_data()

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get real-time performance monitoring metrics."""
        return {
            'current_performance': self.performance_monitor.get_current_performance(),
            'trends_24h': self.performance_monitor.get_performance_trends(24),
            'optimization_suggestions': self.performance_monitor.get_optimization_suggestions()
        }

    def save_performance_data(self) -> str:
        """Save performance monitoring data to file."""
        return self.performance_monitor.export_performance_data()

    def get_performance_insights(self) -> Dict[str, Any]:
        """Get comprehensive performance insights and recommendations."""
        current_perf = self.performance_monitor.get_current_performance()
        trends = self.performance_monitor.get_performance_trends(24)
        suggestions = self.performance_monitor.get_optimization_suggestions()

        return {
            'overall_health': current_perf.get('summary', {}),
            'trends_analysis': trends.get('summary', {}),
            'critical_issues': [s for s in suggestions if s.get('priority') == 'high'],
            'improvement_opportunities': [s for s in suggestions if s.get('priority') == 'medium'],
            'performance_baseline_comparison': self.performance_monitor.get_baseline_comparison()
        }
