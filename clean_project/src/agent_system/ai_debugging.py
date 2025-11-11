"""
AI Debugging and Explainability system for transparent decision-making.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Types of AI decisions that can be explained."""

    GOAL_ANALYSIS = "goal_analysis"
    ACTION_SELECTION = "action_selection"
    PLANNING = "planning"
    OBSERVATION_ANALYSIS = "observation_analysis"
    LEARNING = "learning"


class ConfidenceLevel(Enum):
    """Confidence levels for decisions."""

    VERY_HIGH = "very_high"  # 0.8-1.0
    HIGH = "high"  # 0.6-0.8
    MODERATE = "moderate"  # 0.4-0.6
    LOW = "low"  # 0.2-0.4
    VERY_LOW = "very_low"  # 0.0-0.2


@dataclass
class DecisionFactor:
    """Represents a factor that influenced a decision."""

    factor_name: str
    description: str
    weight: float
    value: Any
    impact: str  # "positive", "negative", "neutral"


@dataclass
class AIDecision:
    """Represents a transparent AI decision with full explanation."""

    decision_id: str
    decision_type: DecisionType
    timestamp: datetime
    input_data: Dict[str, Any]
    output_result: Any
    confidence: float
    confidence_level: ConfidenceLevel
    factors: List[DecisionFactor]
    reasoning_chain: List[str]
    alternatives_considered: List[str]
    execution_time_ms: float
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type.value,
            "timestamp": self.timestamp.isoformat(),
            "input_data": self.input_data,
            "output_result": self.output_result,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "factors": [asdict(factor) for factor in self.factors],
            "reasoning_chain": self.reasoning_chain,
            "alternatives_considered": self.alternatives_considered,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }


class AIDebugger:
    """Main class for debugging and explaining AI decisions."""

    def __init__(self, debug_dir: str = ".agent_debug"):
        self.debug_dir = Path(debug_dir)
        self.debug_dir.mkdir(exist_ok=True)
        self.decisions: List[AIDecision] = []
        self.decision_history: Dict[str, List[str]] = {}  # For session tracking
        self.max_decisions = 1000  # Keep last 1000 decisions

    def _generate_decision_id(self) -> str:
        """Generate unique decision ID."""
        return f"decision_{int(time.time() * 1000)}"

    def _determine_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Determine confidence level from numerical value."""
        if confidence >= 0.8:
            return ConfidenceLevel.VERY_HIGH
        elif confidence >= 0.6:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.4:
            return ConfidenceLevel.MODERATE
        elif confidence >= 0.2:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def log_goal_analysis(
        self, goal_description: str, analysis_result: Dict[str, Any], execution_time_ms: float = 0.0
    ) -> str:
        """Log and explain a goal analysis decision."""

        decision_id = self._generate_decision_id()
        factors = []

        # Extract key factors from analysis
        confidence = analysis_result.get("confidence", 0.0)
        pattern = analysis_result.get("pattern", "unknown")
        method = analysis_result.get("analysis_method", "unknown")

        # Add factors
        if "keyword_confidence" in analysis_result:
            factors.append(
                DecisionFactor(
                    factor_name="keyword_match",
                    description="Strength of keyword-based pattern matching",
                    weight=0.4,
                    value=analysis_result["keyword_confidence"],
                    impact="positive" if analysis_result["keyword_confidence"] > 0.3 else "neutral",
                )
            )

        if "semantic_confidence" in analysis_result:
            factors.append(
                DecisionFactor(
                    factor_name="semantic_similarity",
                    description="Strength of semantic similarity to known patterns",
                    weight=0.6,
                    value=analysis_result["semantic_confidence"],
                    impact=(
                        "positive" if analysis_result["semantic_confidence"] > 0.5 else "negative"
                    ),
                )
            )

        # Add explanation factor
        if "explanation" in analysis_result:
            factors.append(
                DecisionFactor(
                    factor_name="analysis_explanation",
                    description="Human-readable explanation of the analysis",
                    weight=0.1,
                    value=analysis_result["explanation"][:100] + "...",
                    impact="positive",
                )
            )

        # Build reasoning chain
        reasoning_chain = [
            f"Received goal: '{goal_description[:50]}{'...' if len(goal_description) > 50 else ''}'",
            f"Applied analysis method: {method}",
            f"Matched pattern: {pattern}",
            f"Calculated confidence: {confidence:.2f}",
            f"Final result: {analysis_result.get('suggested_actions', [])}",
        ]

        # Create decision
        decision = AIDecision(
            decision_id=decision_id,
            decision_type=DecisionType.GOAL_ANALYSIS,
            timestamp=datetime.now(),
            input_data={"goal_description": goal_description},
            output_result=analysis_result,
            confidence=confidence,
            confidence_level=self._determine_confidence_level(confidence),
            factors=factors,
            reasoning_chain=reasoning_chain,
            alternatives_considered=[
                f"Pattern: {p}" for p in analysis_result.get("all_pattern_scores", {}).keys()
            ],
            execution_time_ms=execution_time_ms,
            metadata={"pattern": pattern, "method": method},
        )

        self._store_decision(decision)
        return decision_id

    def log_action_selection(
        self,
        available_actions: List[Dict[str, Any]],
        selected_action: Optional[Dict[str, Any]],
        selection_criteria: Dict[str, Any],
        execution_time_ms: float = 0.0,
    ) -> str:
        """Log and explain an action selection decision."""

        decision_id = self._generate_decision_id()
        factors = []
        reasoning_chain = []

        if not selected_action:
            # Log why no action was selected
            reasoning_chain = [
                "Evaluated available actions",
                "No action met minimum criteria",
                "Decision: Skip this cycle",
            ]
            confidence = 0.0
            alternatives_considered = [
                action.get("name", "unknown") for action in available_actions
            ]
        else:
            # Build factors from selection criteria
            confidence = selection_criteria.get("final_score", 0.0)

            for criterion, value in selection_criteria.items():
                if criterion != "final_score":
                    factors.append(
                        DecisionFactor(
                            factor_name=criterion,
                            description=f"Scoring criterion: {criterion}",
                            weight=0.2,
                            value=value,
                            impact=(
                                "positive"
                                if isinstance(value, (int, float)) and value > 0
                                else "neutral"
                            ),
                        )
                    )

            # Add specific action factors
            if "context_match" in selection_criteria:
                factors.append(
                    DecisionFactor(
                        factor_name="context_alignment",
                        description="How well the action aligns with current context",
                        weight=0.3,
                        value=selection_criteria["context_match"],
                        impact=(
                            "positive" if selection_criteria["context_match"] > 0.5 else "negative"
                        ),
                    )
                )

            if "learning_bonus" in selection_criteria:
                factors.append(
                    DecisionFactor(
                        factor_name="learning_opportunity",
                        description="Potential for learning from this action",
                        weight=0.2,
                        value=selection_criteria["learning_bonus"],
                        impact=(
                            "positive" if selection_criteria["learning_bonus"] > 0 else "neutral"
                        ),
                    )
                )

            reasoning_chain = [
                f"Evaluated {len(available_actions)} available actions",
                f"Applied scoring criteria: {list(selection_criteria.keys())}",
                f"Selected action: {selected_action.get('name', 'unknown')}",
                f"Final score: {confidence:.2f}",
            ]

            alternatives_considered = [
                action.get("name", "unknown") for action in available_actions[:5]
            ]  # Limit to 5

        # Create decision
        decision = AIDecision(
            decision_id=decision_id,
            decision_type=DecisionType.ACTION_SELECTION,
            timestamp=datetime.now(),
            input_data={
                "available_actions": [
                    a.get("name", a.get("id", str(a))) for a in available_actions
                ],
                "selection_criteria": selection_criteria,
            },
            output_result=selected_action,
            confidence=confidence,
            confidence_level=self._determine_confidence_level(confidence),
            factors=factors,
            reasoning_chain=reasoning_chain,
            alternatives_considered=alternatives_considered,
            execution_time_ms=execution_time_ms,
            metadata={"action_count": len(available_actions)},
        )

        self._store_decision(decision)
        return decision_id

    def log_planning(
        self,
        goal: Dict[str, Any],
        generated_plan: List[Dict[str, Any]],
        planning_method: str,
        execution_time_ms: float = 0.0,
    ) -> str:
        """Log and explain a planning decision."""

        decision_id = self._generate_decision_id()
        factors = []

        confidence = generated_plan[0].get("confidence", 0.0) if generated_plan else 0.0

        # Add planning factors
        factors.append(
            DecisionFactor(
                factor_name="plan_length",
                description="Number of actions in the plan",
                weight=0.1,
                value=len(generated_plan),
                impact="neutral",
            )
        )

        factors.append(
            DecisionFactor(
                factor_name="goal_alignment",
                description="How well the plan addresses the goal",
                weight=0.5,
                value=confidence,
                impact="positive" if confidence > 0.6 else "negative",
            )
        )

        factors.append(
            DecisionFactor(
                factor_name="planning_method",
                description="AI method used for planning",
                weight=0.1,
                value=planning_method,
                impact="positive",
            )
        )

        # Build reasoning chain
        reasoning_chain = [
            f"Analyzed goal: {goal.get('description', '')[:50]}...",
            f"Applied planning method: {planning_method}",
            f"Generated {len(generated_plan)} action steps",
            f"Estimated confidence: {confidence:.2f}",
        ]

        alternatives_considered = (
            [
                "Alternative 1: Direct approach",
                "Alternative 2: Research-first approach",
                "Alternative 3: Iterative approach",
            ]
            if not generated_plan
            else []
        )

        # Create decision
        decision = AIDecision(
            decision_id=decision_id,
            decision_type=DecisionType.PLANNING,
            timestamp=datetime.now(),
            input_data=goal,
            output_result=generated_plan,
            confidence=confidence,
            confidence_level=self._determine_confidence_level(confidence),
            factors=factors,
            reasoning_chain=reasoning_chain,
            alternatives_considered=alternatives_considered,
            execution_time_ms=execution_time_ms,
            metadata={"planning_method": planning_method, "action_count": len(generated_plan)},
        )

        self._store_decision(decision)
        return decision_id

    def log_observation_analysis(
        self,
        observation: Dict[str, Any],
        expected_outcome: str,
        analysis_result: Dict[str, Any],
        execution_time_ms: float = 0.0,
    ) -> str:
        """Log and explain an observation analysis decision."""

        decision_id = self._generate_decision_id()
        factors = []
        reasoning_chain = []

        confidence = analysis_result.get("confidence", 0.0)

        # Add analysis factors
        status = observation.get("status", "unknown")
        factors.append(
            DecisionFactor(
                factor_name="observation_status",
                description="Result status of the observed action",
                weight=0.3,
                value=status,
                impact=(
                    "positive"
                    if status == "success"
                    else "negative" if status == "failure" else "neutral"
                ),
            )
        )

        progress = analysis_result.get("goal_progress", 0.0)
        factors.append(
            DecisionFactor(
                factor_name="goal_progress",
                description="Estimated progress toward goal completion",
                weight=0.4,
                value=progress,
                impact="positive" if progress > 0.5 else "negative",
            )
        )

        if "anomalies_detected" in analysis_result:
            factors.append(
                DecisionFactor(
                    factor_name="anomaly_detection",
                    description="Whether anomalies were detected in the outcome",
                    weight=0.2,
                    value=analysis_result["anomalies_detected"],
                    impact="negative" if analysis_result["anomalies_detected"] else "positive",
                )
            )

        reasoning_chain = [
            f"Analyzed observation with status: {status}",
            f"Expected outcome: {expected_outcome}",
            f"Detected progress: {progress:.2f}",
            f"Generated analysis confidence: {confidence:.2f}",
        ]

        alternatives_considered = [
            "Interpretation 1: Outcome as expected",
            "Interpretation 2: Partial success",
            "Interpretation 3: Unexpected result requiring replanning",
        ]

        # Create decision
        decision = AIDecision(
            decision_id=decision_id,
            decision_type=DecisionType.OBSERVATION_ANALYSIS,
            timestamp=datetime.now(),
            input_data={"observation": observation, "expected_outcome": expected_outcome},
            output_result=analysis_result,
            confidence=confidence,
            confidence_level=self._determine_confidence_level(confidence),
            factors=factors,
            reasoning_chain=reasoning_chain,
            alternatives_considered=alternatives_considered,
            execution_time_ms=execution_time_ms,
            metadata={"observation_status": status, "goal_progress": progress},
        )

        self._store_decision(decision)
        return decision_id

    def _store_decision(self, decision: AIDecision) -> None:
        """Store a decision in the history."""
        self.decisions.append(decision)

        # Keep only the most recent decisions
        if len(self.decisions) > self.max_decisions:
            self.decisions = self.decisions[-self.max_decisions :]

        # Also store by decision type for quick access
        decision_type = decision.decision_type.value
        if decision_type not in self.decision_history:
            self.decision_history[decision_type] = []
        self.decision_history[decision_type].append(decision.decision_id)

    def get_decision_explanation(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get a human-readable explanation of a specific decision."""
        decision = next((d for d in self.decisions if d.decision_id == decision_id), None)
        if not decision:
            return None

        # Build human-readable explanation
        explanation = {
            "decision_id": decision.decision_id,
            "type": decision.decision_type.value,
            "timestamp": decision.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": self._build_decision_summary(decision),
            "confidence": f"{decision.confidence:.2f} ({decision.confidence_level.value.replace('_', ' ')})",
            "key_factors": [
                {
                    "factor": factor.factor_name,
                    "description": factor.description,
                    "weight": f"{factor.weight:.1%}",
                    "value": str(factor.value)[:100],
                    "impact": factor.impact,
                }
                for factor in decision.factors
            ],
            "reasoning_steps": decision.reasoning_chain,
            "alternatives_considered": decision.alternatives_considered,
            "execution_time": f"{decision.execution_time_ms:.1f}ms",
        }

        return explanation

    def _build_decision_summary(self, decision: AIDecision) -> str:
        """Build a concise summary of the decision."""
        decision_type = decision.decision_type.value.replace("_", " ").title()

        if decision.decision_type == DecisionType.GOAL_ANALYSIS:
            goal_desc = decision.input_data.get("goal_description", "")[:30]
            return f"Analyzed goal '{goal_desc}...' and matched it to a pattern with {decision.confidence:.0%} confidence"
        elif decision.decision_type == DecisionType.ACTION_SELECTION:
            action_name = (
                decision.output_result.get("name", "No action")
                if decision.output_result
                else "No action"
            )
            return f"Selected action '{action_name}' from {decision.metadata.get('action_count', 0)} available options"
        elif decision.decision_type == DecisionType.PLANNING:
            action_count = decision.metadata.get("action_count", 0)
            return f"Created a plan with {action_count} actions using {decision.metadata.get('planning_method', 'unknown')} method"
        elif decision.decision_type == DecisionType.OBSERVATION_ANALYSIS:
            status = decision.metadata.get("observation_status", "unknown")
            progress = decision.metadata.get("goal_progress", 0)
            return f"Analyzed observation with status '{status}' and detected {progress:.0%} goal progress"
        else:
            return f"Made a {decision_type} decision with {decision.confidence:.0%} confidence"

    def generate_debug_report(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate a comprehensive debug report."""
        if session_id:
            # Filter decisions by session
            session_decisions = self.decisions  # In a real implementation, we'd filter by session
        else:
            session_decisions = self.decisions

        # Calculate statistics
        total_decisions = len(session_decisions)
        decisions_by_type: Dict[str, int] = {}
        confidence_distribution = {
            "very_high": 0,
            "high": 0,
            "moderate": 0,
            "low": 0,
            "very_low": 0,
        }
        avg_execution_time = 0.0

        if total_decisions > 0:
            for decision in session_decisions:
                # Count by type
                decision_type = decision.decision_type.value
                decisions_by_type[decision_type] = decisions_by_type.get(decision_type, 0) + 1

                # Count confidence levels
                confidence_distribution[decision.confidence_level.value] += 1

                # Sum execution times
                avg_execution_time += decision.execution_time_ms

            avg_execution_time /= total_decisions

        # Generate insights
        insights = self._generate_debug_insights(session_decisions)

        return {
            "report_timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "statistics": {
                "total_decisions": total_decisions,
                "decisions_by_type": decisions_by_type,
                "confidence_distribution": confidence_distribution,
                "avg_execution_time_ms": avg_execution_time,
                "high_confidence_decisions": sum(
                    confidence_distribution[level] for level in ["very_high", "high"]
                ),
            },
            "recent_decisions": [
                {
                    "id": d.decision_id,
                    "type": d.decision_type.value,
                    "summary": self._build_decision_summary(d),
                    "confidence": d.confidence,
                    "timestamp": d.timestamp.isoformat(),
                }
                for d in session_decisions[-10:]  # Last 10 decisions
            ],
            "insights": insights,
        }

    def _generate_debug_insights(self, decisions: List[AIDecision]) -> List[str]:
        """Generate insights from decision history."""
        insights = []

        if not decisions:
            return ["No decisions to analyze"]

        # Analyze confidence patterns
        high_confidence = sum(1 for d in decisions if d.confidence > 0.7)
        if high_confidence / len(decisions) > 0.7:
            insights.append("Agent consistently makes high-confidence decisions")
        elif high_confidence / len(decisions) < 0.3:
            insights.append(
                "Agent often makes low-confidence decisions - consider improving input data or algorithms"
            )

        # Analyze decision types
        decision_types = [d.decision_type for d in decisions]
        most_common_type = max(set(decision_types), key=decision_types.count)
        insights.append(f"Most frequent decision type: {most_common_type.value.replace('_', ' ')}")

        # Analyze execution times
        avg_time = sum(d.execution_time_ms for d in decisions) / len(decisions)
        if avg_time > 1000:
            insights.append("Decision-making is slow on average - consider optimization")
        elif avg_time < 10:
            insights.append("Decision-making is very fast - excellent performance")

        # Analyze factors
        all_factors = []
        for decision in decisions:
            all_factors.extend(decision.factors)

        if all_factors:
            factor_impact = {}
            for factor in all_factors:
                if factor.impact not in factor_impact:
                    factor_impact[factor.impact] = 0
                factor_impact[factor.impact] += 1

            if factor_impact.get("positive", 0) > factor_impact.get("negative", 0) * 2:
                insights.append("Most decision factors have positive impact - good sign")
            elif factor_impact.get("negative", 0) > factor_impact.get("positive", 0):
                insights.append("Many negative factors in decisions - review decision criteria")

        return insights

    def save_debug_data(self, filepath: Optional[Path | str] = None) -> str:
        """Save all debug data to a file."""
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.debug_dir / f"debug_report_{timestamp}.json"

        debug_data = {
            "export_timestamp": datetime.now().isoformat(),
            "decisions": [decision.to_dict() for decision in self.decisions],
            "statistics": self.generate_debug_report()["statistics"],
        }

        with open(filepath, "w") as f:
            json.dump(debug_data, f, indent=2)

        logger.info(f"Debug data saved to {filepath}")
        return str(filepath)


# Global AI debugger instance
ai_debugger = AIDebugger()
