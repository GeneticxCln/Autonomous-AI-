"""
Intelligent observation analyzer with real AI capabilities.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List

from .models import ActionStatus, Goal, Observation

logger = logging.getLogger(__name__)


class IntelligentObservationAnalyzer:
    """AI-powered observation analyzer that provides meaningful insights."""

    def __init__(self):
        self.outcome_patterns = self._load_outcome_patterns()
        self.success_indicators = self._load_success_indicators()
        self.learning_data = {}

    def _load_outcome_patterns(self) -> Dict[str, Any]:
        """Load patterns for understanding different types of outcomes."""
        return {
            "search_results": {
                "success_indicators": ["results", "found", "returned", "items", "hits"],
                "failure_indicators": ["error", "failed", "not found", "no results", "timeout"],
                "metrics": ["count", "number", "total", "found"],
            },
            "file_operations": {
                "success_indicators": ["read successfully", "loaded", "parsed", "extracted"],
                "failure_indicators": ["permission denied", "not found", "corrupted", "invalid"],
                "metrics": ["size", "lines", "characters", "records"],
            },
            "code_execution": {
                "success_indicators": ["executed", "completed", "success", "output"],
                "failure_indicators": ["syntax error", "runtime error", "failed", "exception"],
                "metrics": ["execution time", "lines of code", "memory usage"],
            },
            "data_analysis": {
                "success_indicators": ["analyzed", "processed", "calculated", "summary"],
                "failure_indicators": ["invalid data", "processing error", "calculation failed"],
                "metrics": ["records processed", "accuracy", "completion percentage"],
            },
        }

    def _load_success_indicators(self) -> Dict[str, Any]:
        """Load indicators for different types of success."""
        return {
            "high_success": [
                "completed successfully",
                "task finished",
                "goal achieved",
                "all objectives met",
                "100% complete",
            ],
            "medium_success": [
                "partially completed",
                "significant progress",
                "major objectives met",
                "approaching completion",
            ],
            "low_success": [
                "minimal progress",
                "preliminary results",
                "initial stage",
                "requires additional work",
            ],
            "failure": [
                "failed",
                "error",
                "unsuccessful",
                "cannot complete",
                "insufficient data",
                "invalid input",
            ],
        }

    def analyze_observation(
        self, observation: Observation, expected_outcome: str, goal: Goal
    ) -> Dict[str, Any]:
        """Perform intelligent analysis of an observation."""

        logger.info(f"Analyzing observation for action: {observation.action_id}")

        # Determine outcome type
        outcome_type = self._classify_outcome_type(observation, expected_outcome)

        # Calculate success metrics
        success_score = self._calculate_success_score(observation, expected_outcome, goal)

        # Assess goal progress
        goal_progress = self._assess_goal_progress(observation, expected_outcome, goal)

        # Determine if replanning is needed
        replanning_needed = self._determine_replanning_need(
            observation, success_score, goal_progress
        )

        # Generate insights and recommendations
        insights = self._generate_insights(observation, outcome_type, success_score, goal)

        # Detect anomalies
        anomalies = self._detect_anomalies(observation, expected_outcome, goal)

        analysis = {
            "outcome_type": outcome_type,
            "success_score": success_score,
            "goal_progress": goal_progress,
            "replanning_needed": replanning_needed,
            "insights": insights,
            "anomalies": anomalies,
            "recommendations": self._generate_recommendations(
                observation, outcome_type, success_score
            ),
            "metadata": {
                "analysis_timestamp": datetime.now().isoformat(),
                "expected_outcome": expected_outcome,
                "actual_status": observation.status.value,
                "processing_time": self._calculate_processing_time(observation),
            },
        }

        # Store for learning
        self._store_analysis_for_learning(observation, analysis)

        return analysis

    def _classify_outcome_type(self, observation: Observation, expected_outcome: str) -> str:
        """Classify the type of outcome achieved."""

        result = observation.result
        status = observation.status

        if status == ActionStatus.SUCCESS:
            if self._contains_success_indicators(result, "search_results"):
                return "search_completed"
            elif self._contains_success_indicators(result, "file_operations"):
                return "file_processed"
            elif self._contains_success_indicators(result, "code_execution"):
                return "code_executed"
            elif self._contains_success_indicators(result, "data_analysis"):
                return "analysis_completed"
            else:
                return "task_completed"

        elif status == ActionStatus.PARTIAL:
            return "partial_completion"

        elif status == ActionStatus.FAILURE:
            if self._contains_failure_indicators(result, "search_results"):
                return "search_failed"
            elif self._contains_failure_indicators(result, "file_operations"):
                return "file_operation_failed"
            elif self._contains_failure_indicators(result, "code_execution"):
                return "execution_failed"
            else:
                return "task_failed"

        return "unknown_outcome"

    def _calculate_success_score(
        self, observation: Observation, expected_outcome: str, goal: Goal
    ) -> float:
        """Calculate a quantitative success score (0.0 to 1.0)."""

        base_score = 0.0

        # Base score from status
        if observation.status == ActionStatus.SUCCESS:
            base_score = 0.8
        elif observation.status == ActionStatus.PARTIAL:
            base_score = 0.5
        else:
            base_score = 0.1

        # Adjust based on result content
        result_str = str(observation.result).lower()

        # Positive indicators boost score
        positive_words = ["success", "completed", "achieved", "finished", "done", "excellent"]
        for word in positive_words:
            if word in result_str:
                base_score += 0.1

        # Negative indicators reduce score
        negative_words = ["error", "failed", "failed", "problem", "issue", "invalid"]
        for word in negative_words:
            if word in result_str:
                base_score -= 0.2

        # Outcome matching
        if expected_outcome.lower() in result_str:
            base_score += 0.1

        # Quality metrics from result
        quality_score = self._extract_quality_metrics(observation.result)
        base_score += quality_score * 0.2

        return max(0.0, min(1.0, base_score))

    def _assess_goal_progress(
        self, observation: Observation, expected_outcome: str, goal: Goal
    ) -> float:
        """Assess how much progress this observation makes toward the goal."""

        progress_indicators = {
            "search": 0.3,  # Information gathering
            "analysis": 0.4,  # Deep processing
            "execution": 0.5,  # Direct implementation
            "synthesis": 0.6,  # Combining results
            "completion": 0.8,  # Finalizing task
        }

        # Determine progress based on action type and outcome
        result_str = str(observation.result).lower()

        if any(word in result_str for word in ["search", "find", "query"]):
            return progress_indicators["search"]
        elif any(word in result_str for word in ["analyze", "process", "examine"]):
            return progress_indicators["analysis"]
        elif any(word in result_str for word in ["execute", "run", "implement"]):
            return progress_indicators["execution"]
        elif any(word in result_str for word in ["synthesize", "combine", "merge"]):
            return progress_indicators["synthesis"]
        elif any(word in result_str for word in ["complete", "finish", "finalize"]):
            return progress_indicators["completion"]
        else:
            return 0.2  # Default progress for generic actions

    def _determine_replanning_need(
        self, observation: Observation, success_score: float, goal_progress: float
    ) -> bool:
        """Determine if replanning is needed based on observation."""

        # Need replanning if:
        # 1. Success score is very low (< 0.3)
        # 2. Progress is minimal (< 0.1) despite reasonable effort
        # 3. Unexpected outcome patterns
        # 4. Error conditions

        if success_score < 0.3:
            return True

        if goal_progress < 0.1 and observation.status == ActionStatus.FAILURE:
            return True

        # Check for unexpected patterns
        result_str = str(observation.result).lower()
        unexpected_patterns = ["unexpected", "anomaly", "unusual", "strange"]

        if any(pattern in result_str for pattern in unexpected_patterns):
            return True

        return False

    def _generate_insights(
        self, observation: Observation, outcome_type: str, success_score: float, goal: Goal
    ) -> List[str]:
        """Generate intelligent insights from the observation."""

        insights = []

        # Performance insights
        if success_score > 0.8:
            insights.append("Action completed successfully with high quality")
        elif success_score > 0.5:
            insights.append("Action showed moderate success with room for improvement")
        else:
            insights.append("Action encountered difficulties and may need alternative approach")

        # Outcome-specific insights
        if outcome_type == "search_completed":
            insights.append("Information gathering phase completed - ready for analysis")
        elif outcome_type == "analysis_completed":
            insights.append("Analysis phase completed - insights available for synthesis")
        elif outcome_type == "code_executed":
            insights.append("Code execution completed - results ready for validation")
        elif outcome_type == "task_failed":
            insights.append("Current approach failed - recommend trying alternative methods")

        # Goal alignment insights
        goal_alignment = self._assess_goal_alignment(observation, goal)
        if goal_alignment > 0.7:
            insights.append("Strong alignment with overall goal objectives")
        elif goal_alignment > 0.4:
            insights.append("Moderate progress toward goal - continuing current approach")
        else:
            insights.append("Limited goal alignment - consider strategy adjustment")

        return insights

    def _detect_anomalies(
        self, observation: Observation, expected_outcome: str, goal: Goal
    ) -> List[str]:
        """Detect anomalies or unusual patterns in the observation."""

        anomalies = []

        # Status anomalies
        if observation.status == ActionStatus.FAILURE:
            if "unexpected" in str(observation.result).lower():
                anomalies.append("Unexpected failure detected")

        # Result anomalies
        result_str = str(observation.result).lower()

        # Check for unusual result patterns
        if len(result_str) > 10000:  # Very long result
            anomalies.append("Unusually verbose result - potential data overflow")

        if result_str.count("error") > 3:  # Multiple errors
            anomalies.append("Multiple error conditions detected")

        # Time anomalies (if timestamp available)
        if hasattr(observation, "timestamp"):
            time_taken = (datetime.now() - observation.timestamp).total_seconds()
            if time_taken > 300:  # 5 minutes
                anomalies.append("Unusually long execution time")

        # Expectation anomalies
        if expected_outcome.lower() not in result_str:
            anomalies.append("Outcome does not match expectations")

        return anomalies

    def _generate_recommendations(
        self, observation: Observation, outcome_type: str, success_score: float
    ) -> List[str]:
        """Generate actionable recommendations based on observation."""

        recommendations = []

        if success_score < 0.3:
            recommendations.append("Consider alternative approach or tool for this task")
            recommendations.append("Review input parameters for accuracy and completeness")

        elif success_score < 0.7:
            recommendations.append("Current approach shows promise - continue with adjustments")
            recommendations.append("Monitor progress closely for optimization opportunities")

        else:
            recommendations.append("Current approach is effective - maintain strategy")
            recommendations.append("Consider scaling this successful pattern to similar tasks")

        # Outcome-specific recommendations
        if outcome_type == "search_failed":
            recommendations.append("Try alternative search terms or sources")
            recommendations.append("Consider breaking search into smaller, more specific queries")

        elif outcome_type == "file_operation_failed":
            recommendations.append("Verify file permissions and accessibility")
            recommendations.append("Check file format and encoding compatibility")

        elif outcome_type == "execution_failed":
            recommendations.append("Review code syntax and logic")
            recommendations.append("Test code components individually")

        return recommendations

    def _contains_success_indicators(self, result: Any, category: str) -> bool:
        """Check if result contains success indicators for a category."""

        if category not in self.outcome_patterns:
            return False

        result_str = str(result).lower()
        indicators = self.outcome_patterns[category]["success_indicators"]

        return any(indicator in result_str for indicator in indicators)

    def _contains_failure_indicators(self, result: Any, category: str) -> bool:
        """Check if result contains failure indicators for a category."""

        if category not in self.outcome_patterns:
            return False

        result_str = str(result).lower()
        indicators = self.outcome_patterns[category]["failure_indicators"]

        return any(indicator in result_str for indicator in indicators)

    def _extract_quality_metrics(self, result: Any) -> float:
        """Extract quality metrics from result."""

        if not isinstance(result, dict):
            return 0.0

        metrics_score = 0.0

        # Count positive metrics
        positive_metrics = ["count", "number", "total", "success_rate", "accuracy"]
        for metric in positive_metrics:
            if metric in result:
                try:
                    value = float(result[metric])
                    if value > 0:
                        metrics_score += 0.1
                except (ValueError, TypeError):
                    pass

        return min(1.0, metrics_score)

    def _assess_goal_alignment(self, observation: Observation, goal: Goal) -> float:
        """Assess how well the observation aligns with the goal."""

        # Simple keyword matching for goal alignment
        goal_keywords = set(re.findall(r"\b\w+\b", goal.description.lower()))
        result_keywords = set(re.findall(r"\b\w+\b", str(observation.result).lower()))

        if not goal_keywords:
            return 0.5

        common_keywords = goal_keywords & result_keywords
        alignment = len(common_keywords) / len(goal_keywords)

        return alignment

    def _calculate_processing_time(self, observation: Observation) -> float:
        """Calculate processing time if timestamp available."""

        if hasattr(observation, "timestamp"):
            return (datetime.now() - observation.timestamp).total_seconds()

        return 0.0

    def _store_analysis_for_learning(self, observation: Observation, analysis: Dict[str, Any]):
        """Store analysis data for machine learning."""

        learning_key = f"{observation.action_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self.learning_data[learning_key] = {
            "observation": {
                "status": observation.status.value,
                "result": observation.result,
                "feedback": observation.feedback,
            },
            "analysis": analysis,
            "timestamp": datetime.now().isoformat(),
        }

        # Keep only recent learning data (limit to 1000 entries)
        if len(self.learning_data) > 1000:
            # Remove oldest entries
            sorted_keys = sorted(self.learning_data.keys())
            for key in sorted_keys[:-1000]:
                del self.learning_data[key]

    def get_learning_insights(self) -> Dict[str, Any]:
        """Get insights from accumulated learning data."""

        if not self.learning_data:
            return {"message": "No learning data available"}

        total_analyses = len(self.learning_data)
        success_count = sum(
            1 for data in self.learning_data.values() if data["analysis"]["success_score"] > 0.7
        )

        avg_success_score = (
            sum(data["analysis"]["success_score"] for data in self.learning_data.values())
            / total_analyses
        )

        common_outcomes = {}
        for data in self.learning_data.values():
            outcome_type = data["analysis"]["outcome_type"]
            common_outcomes[outcome_type] = common_outcomes.get(outcome_type, 0) + 1

        return {
            "total_analyses": total_analyses,
            "high_success_rate": success_count / total_analyses,
            "average_success_score": avg_success_score,
            "common_outcome_types": common_outcomes,
            "anomaly_patterns": self._identify_anomaly_patterns(),
        }

    def _identify_anomaly_patterns(self) -> List[str]:
        """Identify common anomaly patterns."""

        anomaly_count = {}

        for data in self.learning_data.values():
            for anomaly in data["analysis"]["anomalies"]:
                anomaly_count[anomaly] = anomaly_count.get(anomaly, 0) + 1

        # Return most common anomalies
        sorted_anomalies = sorted(anomaly_count.items(), key=lambda x: x[1], reverse=True)

        return [f"{anomaly} ({count} occurrences)" for anomaly, count in sorted_anomalies[:5]]

    def detect_anomalies(self, observations: List[Observation]) -> List[str]:
        """Detect anomalies from a list of recent observations (required for agent compatibility)."""

        if not observations:
            return []

        anomalies = []

        # Check for repeated failures
        failure_count = sum(1 for obs in observations if obs.status == ActionStatus.FAILURE)
        if failure_count > len(observations) * 0.5:
            anomalies.append("High failure rate detected")

        # Check for unusual patterns
        statuses = [obs.status for obs in observations]
        if len(set(statuses)) == 1 and statuses[0] == ActionStatus.FAILURE:
            anomalies.append("All recent actions failed")

        # Check for timing anomalies
        import time

        now = time.time()
        for obs in observations:
            if hasattr(obs, "timestamp"):
                time_diff = now - obs.timestamp.timestamp()
                if time_diff > 300:  # 5 minutes old
                    anomalies.append("Stale observation detected")

        return anomalies


# Global analyzer instance
intelligent_analyzer = IntelligentObservationAnalyzer()
