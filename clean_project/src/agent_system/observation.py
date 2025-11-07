from __future__ import annotations

import logging
from typing import Any, Dict, List

from .models import ActionStatus, Goal, Observation

logger = logging.getLogger(__name__)


class ObservationAnalyzer:
    """Analyzes observations and provides feedback for plan adaptation."""

    def analyze_observation(
        self, observation: Observation, expected_outcome: str, goal: Goal
    ) -> Dict[str, Any]:
        """Analyze an observation and determine if replanning is needed."""
        analysis = {
            "success": observation.status == ActionStatus.SUCCESS,
            "outcome_match": self._check_outcome_match(observation, expected_outcome),
            "goal_progress": 0.0,
            "replanning_needed": False,
            "recommendations": [],
        }

        if not analysis["outcome_match"]:
            analysis["recommendations"].append(
                "Expected outcome not achieved, consider alternative approach"
            )
            analysis["replanning_needed"] = True

        if observation.status == ActionStatus.SUCCESS:
            analysis["goal_progress"] = 0.2

        if observation.status == ActionStatus.FAILURE:
            analysis["recommendations"].append(
                "Action failed, may need different tool or parameters"
            )
            analysis["replanning_needed"] = True

        if observation.metrics:
            if observation.metrics.get("error_rate", 0) > 0.5:
                analysis["recommendations"].append("High error rate detected, verify inputs")

        return analysis

    def detect_anomalies(self, recent_observations: List[Observation]) -> List[str]:
        """Detect patterns that might indicate problems."""
        anomalies: List[str] = []

        if not recent_observations:
            return anomalies

        failures = sum(1 for obs in recent_observations if obs.status == ActionStatus.FAILURE)
        failure_rate = failures / len(recent_observations)

        if failure_rate > 0.5:
            anomalies.append(f"High failure rate: {failure_rate:.1%}")

        if len(recent_observations) >= 3:
            last_three = recent_observations[-3:]
            if all(obs.status == ActionStatus.FAILURE for obs in last_three):
                anomalies.append("Three consecutive failures detected")

        return anomalies

    def _check_outcome_match(self, observation: Observation, expected_outcome: str) -> bool:
        """Check if observation result matches expected outcome."""
        if observation.status != ActionStatus.SUCCESS:
            return False

        result_str = str(observation.result).lower()
        expected_words = expected_outcome.lower().split()

        matches = sum(1 for word in expected_words if word in result_str)
        return matches >= len(expected_words) * 0.5
