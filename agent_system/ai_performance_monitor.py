"""
AI Performance Monitoring system for real-time tracking and optimization.
"""
from __future__ import annotations

import logging
import time
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, asdict, field
from collections import defaultdict, deque
from pathlib import Path
from enum import Enum

# Try to import numpy for performance calculations
NUMPY_AVAILABLE = False
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    # Create a minimal numpy-like fallback for basic operations
    class np:
        @staticmethod
        def mean(arr):
            return sum(arr) / len(arr) if arr else 0
        @staticmethod
        def std(arr):
            if not arr:
                return 0
            mean_val = sum(arr) / len(arr)
            return (sum((x - mean_val) ** 2 for x in arr) / len(arr)) ** 0.5

logger = logging.getLogger(__name__)


class PerformanceLevel(Enum):
    """Performance levels for metrics."""
    EXCELLENT = "excellent"      # 90-100%
    GOOD = "good"               # 75-89%
    AVERAGE = "average"         # 60-74%
    POOR = "poor"               # 40-59%
    CRITICAL = "critical"       # 0-39%


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MetricPoint:
    """Represents a single metric data point."""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MetricPoint:
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class PerformanceAlert:
    """Represents a performance alert."""
    alert_id: str
    timestamp: datetime
    severity: AlertSeverity
    metric_name: str
    current_value: float
    threshold: float
    message: str
    suggested_actions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity.value
        }


@dataclass
class MetricThresholds:
    """Defines thresholds for a performance metric."""
    warning_low: float
    warning_high: float
    error_low: float
    error_high: float
    unit: str = ""
    description: str = ""

    def evaluate(self, value: float) -> PerformanceLevel:
        """Evaluate a metric value against thresholds."""
        if value >= self.error_high or value <= self.error_low:
            return PerformanceLevel.CRITICAL
        elif value >= self.warning_high or value <= self.warning_low:
            return PerformanceLevel.POOR
        elif value >= 0.75:  # Good threshold for positive metrics
            return PerformanceLevel.GOOD
        else:
            return PerformanceLevel.AVERAGE


class AIPerformanceMonitor:
    """Real-time AI performance monitoring and alerting system."""

    def __init__(self, monitor_dir: str = ".agent_monitoring"):
        self.monitor_dir = Path(monitor_dir)
        self.monitor_dir.mkdir(exist_ok=True)

        # Time series data storage
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.current_metrics: Dict[str, float] = {}

        # Performance tracking
        self.decision_times = deque(maxlen=100)
        self.accuracy_scores = deque(maxlen=100)
        self.goal_completion_rates = deque(maxlen=50)
        self.learning_progress = deque(maxlen=100)

        # Alert system
        self.active_alerts: List[PerformanceAlert] = []
        self.alert_history: List[PerformanceAlert] = []
        self.alert_callbacks: List[Callable[[PerformanceAlert], None]] = []

        # Thresholds configuration
        self.thresholds = self._setup_default_thresholds()

        # Performance baselines
        self.baselines: Dict[str, float] = {}
        self.baseline_period_days = 7

        # Export configuration
        self.export_interval = 3600  # Export every hour
        self.last_export = time.time()

        # Start background monitoring
        self._start_monitoring()

    def _setup_default_thresholds(self) -> Dict[str, MetricThresholds]:
        """Setup default performance thresholds."""
        return {
            'decision_accuracy': MetricThresholds(
                warning_low=0.6, warning_high=1.0,
                error_low=0.4, error_high=1.0,
                unit="ratio", description="Accuracy of AI decisions"
            ),
            'decision_time_ms': MetricThresholds(
                warning_low=0, warning_high=2000,
                error_low=0, error_high=5000,
                unit="ms", description="Time to make decisions"
            ),
            'goal_completion_rate': MetricThresholds(
                warning_low=0.5, warning_high=1.0,
                error_low=0.3, error_high=1.0,
                unit="ratio", description="Rate of goal completion"
            ),
            'learning_velocity': MetricThresholds(
                warning_low=0.1, warning_high=1.0,
                error_low=0.0, error_high=1.0,
                unit="rate", description="Speed of learning new patterns"
            ),
            'semantic_similarity_quality': MetricThresholds(
                warning_low=0.5, warning_high=1.0,
                error_low=0.3, error_high=1.0,
                unit="score", description="Quality of semantic similarity matches"
            ),
            'cross_session_knowledge_retention': MetricThresholds(
                warning_low=0.4, warning_high=1.0,
                error_low=0.2, error_high=1.0,
                unit="ratio", description="Knowledge retention between sessions"
            ),
            'planning_confidence': MetricThresholds(
                warning_low=0.5, warning_high=1.0,
                error_low=0.3, error_high=1.0,
                unit="score", description="Confidence in planning decisions"
            )
        }

    def _start_monitoring(self):
        """Start background monitoring tasks."""
        # Export data periodically
        self._schedule_next_export()

    def _schedule_next_export(self):
        """Schedule next data export."""
        self.last_export = time.time()

    def record_decision_metrics(
        self,
        decision_type: str,
        execution_time_ms: float,
        confidence: float,
        success: bool,
        metadata: Dict[str, Any] = None
    ):
        """Record metrics for an AI decision."""
        timestamp = datetime.now()

        # Record decision time
        self._record_metric('decision_time_ms', execution_time_ms, {
            'decision_type': decision_type,
            'confidence': confidence
        })

        # Record confidence level
        self._record_metric('decision_confidence', confidence, {
            'decision_type': decision_type,
            'success': success
        })

        # Update decision time history
        self.decision_times.append(execution_time_ms)

        # Calculate and record accuracy
        accuracy = confidence if success else (1.0 - confidence)
        self.accuracy_scores.append(accuracy)
        self._record_metric('decision_accuracy', accuracy, {
            'decision_type': decision_type,
            'execution_time': execution_time_ms
        })

    def record_goal_metrics(self, goal_completed: bool, total_goals: int, completed_goals: int):
        """Record goal completion metrics."""
        completion_rate = completed_goals / total_goals if total_goals > 0 else 0.0
        self.goal_completion_rates.append(completion_rate)

        self._record_metric('goal_completion_rate', completion_rate, {
            'completed': completed_goals,
            'total': total_goals,
            'last_goal_success': goal_completed
        })

        # Trigger alerts if necessary
        self._check_thresholds('goal_completion_rate', completion_rate)

    def record_learning_metrics(self, patterns_learned: int, knowledge_base_size: int, confidence_scores: List[float]):
        """Record learning system performance metrics."""
        timestamp = datetime.now()

        # Learning velocity (patterns per time period)
        self.learning_progress.append(patterns_learned)
        learning_velocity = patterns_learned  # Simplified for now

        self._record_metric('learning_velocity', learning_velocity, {
            'patterns_learned': patterns_learned,
            'knowledge_base_size': knowledge_base_size
        })

        # Average confidence of learned patterns
        if confidence_scores:
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            self._record_metric('learned_pattern_confidence', avg_confidence, {
                'pattern_count': len(confidence_scores),
                'min_confidence': min(confidence_scores),
                'max_confidence': max(confidence_scores)
            })

    def record_semantic_similarity_metrics(self, similarity_scores: List[float], match_quality: float):
        """Record semantic similarity performance metrics."""
        if similarity_scores:
            avg_similarity = sum(similarity_scores) / len(similarity_scores)
            self._record_metric('semantic_similarity_quality', avg_similarity, {
                'match_quality': match_quality,
                'score_count': len(similarity_scores),
                'min_score': min(similarity_scores),
                'max_score': max(similarity_scores)
            })

    def record_planning_metrics(self, plan_confidence: float, action_count: int, execution_success_rate: float):
        """Record planning system performance metrics."""
        self._record_metric('planning_confidence', plan_confidence, {
            'action_count': action_count,
            'execution_success_rate': execution_success_rate
        })

    def record_cross_session_metrics(self, knowledge_retention_rate: float, pattern_reuse_success: float):
        """Record cross-session learning performance metrics."""
        self._record_metric('cross_session_knowledge_retention', knowledge_retention_rate, {
            'pattern_reuse_success': pattern_reuse_success
        })

    def _record_metric(self, metric_name: str, value: float, metadata: Dict[str, Any] = None):
        """Record a metric data point."""
        timestamp = datetime.now()
        metric_point = MetricPoint(
            timestamp=timestamp,
            value=value,
            metadata=metadata or {}
        )

        # Store in history
        self.metrics_history[metric_name].append(metric_point)

        # Update current value
        self.current_metrics[metric_name] = value

        # Check thresholds
        self._check_thresholds(metric_name, value)

    def _check_thresholds(self, metric_name: str, current_value: float):
        """Check if metric value triggers any alerts."""
        if metric_name not in self.thresholds:
            return

        thresholds = self.thresholds[metric_name]
        level = thresholds.evaluate(current_value)

        # Generate alert if performance is poor or critical
        if level in [PerformanceLevel.POOR, PerformanceLevel.CRITICAL]:
            alert = self._create_performance_alert(metric_name, current_value, level, thresholds)
            if alert:
                self._trigger_alert(alert)

    def _create_performance_alert(
        self,
        metric_name: str,
        current_value: float,
        level: PerformanceLevel,
        thresholds: MetricThresholds
    ) -> Optional[PerformanceAlert]:
        """Create a performance alert."""
        # Check if similar alert already exists (avoid spam)
        recent_alerts = [
            a for a in self.active_alerts
            if a.metric_name == metric_name and
            (datetime.now() - a.timestamp).seconds < 300  # 5 minutes
        ]
        if recent_alerts:
            return None  # Don't create duplicate alerts

        # Determine severity
        if level == PerformanceLevel.CRITICAL:
            severity = AlertSeverity.CRITICAL
        elif level == PerformanceLevel.POOR:
            severity = AlertSeverity.ERROR
        else:
            severity = AlertSeverity.WARNING

        # Generate message and suggestions
        message, suggested_actions = self._generate_alert_message(
            metric_name, current_value, level, thresholds
        )

        alert = PerformanceAlert(
            alert_id=f"alert_{int(time.time() * 1000)}",
            timestamp=datetime.now(),
            severity=severity,
            metric_name=metric_name,
            current_value=current_value,
            threshold=thresholds.warning_low if level == PerformanceLevel.POOR else thresholds.error_low,
            message=message,
            suggested_actions=suggested_actions
        )

        return alert

    def _generate_alert_message(
        self,
        metric_name: str,
        current_value: float,
        level: PerformanceLevel,
        thresholds: MetricThresholds
    ) -> tuple[str, List[str]]:
        """Generate alert message and suggested actions."""
        metric_display = metric_name.replace('_', ' ').title()

        if level == PerformanceLevel.CRITICAL:
            message = f"CRITICAL: {metric_display} is critically low at {current_value:.2f}"
            suggestions = [
                "Immediately review AI decision algorithms",
                "Check input data quality",
                "Consider reverting to previous stable configuration",
                "Enable manual oversight for critical decisions"
            ]
        elif level == PerformanceLevel.POOR:
            message = f"WARNING: {metric_display} is below acceptable threshold at {current_value:.2f}"
            suggestions = [
                "Analyze recent decision patterns for anomalies",
                "Review training data and learning algorithms",
                "Check system resources and performance",
                "Consider adjusting confidence thresholds"
            ]
        else:
            message = f"INFO: {metric_display} at {current_value:.2f}"
            suggestions = ["Monitor for further changes"]

        return message, suggestions

    def _trigger_alert(self, alert: PerformanceAlert):
        """Trigger a performance alert."""
        self.active_alerts.append(alert)
        self.alert_history.append(alert)

        # Call registered callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

        # Log the alert
        logger.warning(f"Performance Alert [{alert.severity.value}]: {alert.message}")

    def add_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """Add a callback function for alerts."""
        self.alert_callbacks.append(callback)

    def get_current_performance(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        performance_data = {
            'timestamp': datetime.now().isoformat(),
            'current_metrics': dict(self.current_metrics),
            'performance_levels': {},
            'active_alerts': [asdict(alert) for alert in self.active_alerts],
            'summary': self._generate_performance_summary()
        }

        # Calculate performance levels for each metric
        for metric_name, value in self.current_metrics.items():
            if metric_name in self.thresholds:
                level = self.thresholds[metric_name].evaluate(value)
                performance_data['performance_levels'][metric_name] = {
                    'level': level.value,
                    'value': value,
                    'target': self._get_metric_target(metric_name)
                }

        return performance_data

    def _get_metric_target(self, metric_name: str) -> str:
        """Get target performance for a metric."""
        targets = {
            'decision_accuracy': '> 80%',
            'decision_time_ms': '< 1000ms',
            'goal_completion_rate': '> 70%',
            'learning_velocity': '> 0.5',
            'semantic_similarity_quality': '> 70%',
            'planning_confidence': '> 60%'
        }
        return targets.get(metric_name, 'N/A')

    def _generate_performance_summary(self) -> Dict[str, Any]:
        """Generate overall performance summary."""
        if not self.current_metrics:
            return {'overall_health': 'unknown', 'score': 0}

        # Calculate overall health score
        total_score = 0
        metric_count = 0

        for metric_name, value in self.current_metrics.items():
            if metric_name in self.thresholds:
                level = self.thresholds[metric_name].evaluate(value)
                # Map performance level to score
                level_scores = {
                    PerformanceLevel.EXCELLENT: 100,
                    PerformanceLevel.GOOD: 80,
                    PerformanceLevel.AVERAGE: 60,
                    PerformanceLevel.POOR: 30,
                    PerformanceLevel.CRITICAL: 10
                }
                total_score += level_scores.get(level, 50)
                metric_count += 1

        overall_score = total_score / max(1, metric_count)

        # Determine overall health
        if overall_score >= 90:
            health = 'excellent'
        elif overall_score >= 75:
            health = 'good'
        elif overall_score >= 60:
            health = 'average'
        elif overall_score >= 40:
            health = 'poor'
        else:
            health = 'critical'

        return {
            'overall_health': health,
            'score': overall_score,
            'active_alert_count': len(self.active_alerts),
            'monitored_metrics': len(self.current_metrics)
        }

    def get_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance trends over specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        trends = {}

        for metric_name, history in self.metrics_history.items():
            # Filter data points within time window
            recent_points = [
                point for point in history
                if point.timestamp >= cutoff_time
            ]

            if recent_points:
                values = [point.value for point in recent_points]
                trends[metric_name] = {
                    'data_points': len(values),
                    'min_value': min(values),
                    'max_value': max(values),
                    'avg_value': sum(values) / len(values),
                    'current_value': self.current_metrics.get(metric_name, 0),
                    'trend': self._calculate_trend(values),
                    'time_span_hours': hours
                }

        return {
            'trend_period_hours': hours,
            'generated_at': datetime.now().isoformat(),
            'trends': trends,
            'summary': self._analyze_trends(trends)
        }

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction for a series of values."""
        if len(values) < 2:
            return 'stable'

        # Simple linear trend calculation
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        change_percent = ((second_avg - first_avg) / first_avg) * 100

        if change_percent > 5:
            return 'improving'
        elif change_percent < -5:
            return 'declining'
        else:
            return 'stable'

    def _analyze_trends(self, trends: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze overall trends and generate insights."""
        improving_metrics = []
        declining_metrics = []
        stable_metrics = []

        for metric_name, trend_data in trends.items():
            trend = trend_data.get('trend', 'stable')
            if trend == 'improving':
                improving_metrics.append(metric_name)
            elif trend == 'declining':
                declining_metrics.append(metric_name)
            else:
                stable_metrics.append(metric_name)

        return {
            'improving_count': len(improving_metrics),
            'declining_count': len(declining_metrics),
            'stable_count': len(stable_metrics),
            'improving_metrics': improving_metrics,
            'declining_metrics': declining_metrics,
            'stable_metrics': stable_metrics,
            'insights': self._generate_trend_insights(improving_metrics, declining_metrics)
        }

    def _generate_trend_insights(self, improving: List[str], declining: List[str]) -> List[str]:
        """Generate insights from trend analysis."""
        insights = []

        if improving:
            insights.append(f"Performance improving in: {', '.join(improving[:3])}")

        if declining:
            insights.append(f"Performance declining in: {', '.join(declining[:3])}")
            insights.append("Consider investigating declining metrics for root causes")

        if not improving and not declining:
            insights.append("All metrics showing stable performance")

        return insights

    def export_performance_data(self, filepath: str = None) -> str:
        """Export all performance data to file."""
        if not filepath:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = self.monitor_dir / f"performance_export_{timestamp}.json"

        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'export_period': 'all',
            'current_performance': self.get_current_performance(),
            'trends_24h': self.get_performance_trends(24),
            'trends_7d': self.get_performance_trends(168),  # 7 days
            'alert_history': [asdict(alert) for alert in self.alert_history[-100:]],  # Last 100 alerts
            'metrics_history': {
                metric_name: [point.to_dict() for point in history]
                for metric_name, history in self.metrics_history.items()
            }
        }

        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Performance data exported to {filepath}")
        return str(filepath)

    def get_optimization_suggestions(self) -> List[Dict[str, Any]]:
        """Generate AI optimization suggestions based on performance data."""
        suggestions = []
        current_perf = self.get_current_performance()

        # Analyze current performance
        for metric_name, perf_data in current_perf.get('performance_levels', {}).items():
            level = perf_data['level']
            value = perf_data['value']

            if level in ['poor', 'critical']:
                suggestion = {
                    'metric': metric_name,
                    'current_level': level,
                    'current_value': value,
                    'target_value': perf_data['target'],
                    'priority': 'high' if level == 'critical' else 'medium',
                    'actions': self._get_optimization_actions(metric_name, level)
                }
                suggestions.append(suggestion)

        # Add proactive suggestions based on trends
        trends = self.get_performance_trends(24)
        for metric_name, trend_data in trends.get('trends', {}).items():
            if trend_data.get('trend') == 'declining':
                suggestions.append({
                    'metric': metric_name,
                    'current_level': 'declining',
                    'priority': 'medium',
                    'actions': [
                        f"Investigate root cause of declining {metric_name}",
                        "Review recent configuration changes",
                        "Monitor for patterns in declining performance"
                    ]
                })

        return suggestions

    def _get_optimization_actions(self, metric_name: str, level: str) -> List[str]:
        """Get specific optimization actions for a metric."""
        action_map = {
            'decision_accuracy': [
                "Review decision algorithm parameters",
                "Improve training data quality",
                "Adjust confidence thresholds",
                "Enable ensemble methods for critical decisions"
            ],
            'decision_time_ms': [
                "Optimize algorithm complexity",
                "Implement caching for frequent operations",
                "Use faster hardware or distributed processing",
                "Profile and optimize slow code paths"
            ],
            'goal_completion_rate': [
                "Improve goal decomposition algorithms",
                "Enhance action selection strategy",
                "Add more sophisticated planning heuristics",
                "Implement goal retry mechanisms"
            ],
            'learning_velocity': [
                "Increase learning rate parameters",
                "Improve pattern recognition algorithms",
                "Add more diverse training examples",
                "Implement active learning strategies"
            ]
        }

        return action_map.get(metric_name, ["Review and optimize the relevant algorithms"])

    def reset_baseline(self) -> None:
        """Reset performance baselines using current data."""
        logger.info("Resetting performance baselines")
        self.baselines = dict(self.current_metrics)

    def get_baseline_comparison(self) -> Dict[str, float]:
        """Compare current performance to baselines."""
        if not self.baselines:
            return {}

        comparisons = {}
        for metric_name, current_value in self.current_metrics.items():
            if metric_name in self.baselines:
                baseline_value = self.baselines[metric_name]
                if baseline_value != 0:
                    change_percent = ((current_value - baseline_value) / baseline_value) * 100
                    comparisons[metric_name] = change_percent

        return comparisons


# Global performance monitor instance
ai_performance_monitor = AIPerformanceMonitor()