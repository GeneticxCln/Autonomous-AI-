"""
Performance Tracking System for Autonomous Agents
Monitors and tracks agent performance metrics and optimization opportunities
"""

from __future__ import annotations

import json
import logging
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Individual performance metric."""

    name: str
    value: float
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    unit: str = "count"
    category: str = "general"


@dataclass
class PerformanceSnapshot:
    """Snapshot of performance at a point in time."""

    timestamp: datetime
    metrics: Dict[str, float] = field(default_factory=dict)
    system_info: Dict[str, Any] = field(default_factory=dict)
    agent_status: Dict[str, Any] = field(default_factory=dict)


class PerformanceTracker:
    """
    Comprehensive performance tracking system for autonomous agents.

    Tracks:
    - Response times and latencies
    - Success/failure rates
    - Resource utilization
    - Task completion metrics
    - Quality scores
    - User satisfaction
    """

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.snapshots: List[PerformanceSnapshot] = []
        self.current_metrics: Dict[str, float] = {}
        self.start_time = datetime.now()
        self.performance_data = {}

    def track_response_time(self, operation: str, duration: float, success: bool = True):
        """Track response time for an operation."""
        metric_name = f"response_time_{operation}"
        self._record_metric(
            metric_name,
            duration,
            {"operation": operation, "success": success, "timestamp": time.time()},
            "milliseconds",
        )

        # Update current metrics
        if metric_name not in self.current_metrics:
            self.current_metrics[metric_name] = []
        if isinstance(self.current_metrics[metric_name], list):
            self.current_metrics[metric_name].append(duration)
            if len(self.current_metrics[metric_name]) > 10:
                self.current_metrics[metric_name] = self.current_metrics[metric_name][-10:]

    def track_success_rate(self, operation: str, successful: bool, total_attempts: int = 1):
        """Track success rate for an operation."""
        metric_name = f"success_rate_{operation}"
        success_key = f"{operation}_successes"
        total_key = f"{operation}_total"

        # Track successes and totals
        if success_key not in self.performance_data:
            self.performance_data[success_key] = 0
        if total_key not in self.performance_data:
            self.performance_data[total_key] = 0

        self.performance_data[total_key] += total_attempts
        if successful:
            self.performance_data[success_key] += total_attempts

        # Calculate success rate
        if self.performance_data[total_key] > 0:
            success_rate = self.performance_data[success_key] / self.performance_data[total_key]
            self._record_metric(
                metric_name,
                success_rate,
                {
                    "operation": operation,
                    "successes": self.performance_data[success_key],
                    "total": self.performance_data[total_key],
                },
                "percentage",
            )

    def track_resource_usage(self, cpu_percent: float, memory_mb: float, disk_usage: float):
        """Track system resource usage."""
        self._record_metric("cpu_usage", cpu_percent, {}, "percentage")
        self._record_metric("memory_usage", memory_mb, {}, "megabytes")
        self._record_metric("disk_usage", disk_usage, {}, "percentage")

    def track_task_completion(
        self, task_type: str, duration: float, quality_score: Optional[float] = None
    ):
        """Track task completion metrics."""
        self._record_metric(
            f"task_duration_{task_type}",
            duration,
            {"task_type": task_type, "timestamp": time.time()},
            "seconds",
        )

        if quality_score is not None:
            self._record_metric(
                f"task_quality_{task_type}",
                quality_score,
                {"task_type": task_type, "timestamp": time.time()},
                "score",
            )

    def track_user_satisfaction(self, rating: float, context: Dict[str, Any] = None):
        """Track user satisfaction ratings."""
        self._record_metric("user_satisfaction", rating, context or {}, "rating")

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        now = datetime.now()
        uptime = (now - self.start_time).total_seconds()

        summary = {
            "uptime_seconds": uptime,
            "uptime_hours": uptime / 3600,
            "timestamp": now.isoformat(),
            "metrics": {},
        }

        # Calculate summary statistics for key metrics
        for metric_name, values in self.metrics_history.items():
            if values:
                metric_values = [m.value for m in values]
                summary["metrics"][metric_name] = {
                    "count": len(metric_values),
                    "average": statistics.mean(metric_values),
                    "median": statistics.median(metric_values),
                    "min": min(metric_values),
                    "max": max(metric_values),
                    "latest": metric_values[-1] if metric_values else None,
                }

        # Add performance data
        summary["performance_data"] = self.performance_data.copy()

        return summary

    def get_trend_analysis(self, metric_name: str, hours: int = 24) -> Dict[str, Any]:
        """Analyze trends for a specific metric."""
        if metric_name not in self.metrics_history:
            return {"error": f"Metric {metric_name} not found"}

        values = self.metrics_history[metric_name]
        if not values:
            return {"error": f"No data for metric {metric_name}"}

        # Filter by time window
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_values = [m for m in values if m.timestamp >= cutoff_time]

        if not recent_values:
            return {"error": f"No recent data for metric {metric_name}"}

        # Calculate trend
        recent_metric_values = [m.value for m in recent_values]
        if len(recent_metric_values) >= 2:
            # Simple linear trend
            first_half = recent_metric_values[: len(recent_metric_values) // 2]
            second_half = recent_metric_values[len(recent_metric_values) // 2 :]

            first_avg = statistics.mean(first_half) if first_half else 0
            second_avg = statistics.mean(second_half) if second_half else 0

            if first_avg > 0:
                trend_percent = ((second_avg - first_avg) / first_avg) * 100
            else:
                trend_percent = 0

            trend_direction = (
                "improving" if trend_percent < 0 else "degrading" if trend_percent > 0 else "stable"
            )
        else:
            trend_percent = 0
            trend_direction = "insufficient_data"

        return {
            "metric": metric_name,
            "time_window_hours": hours,
            "data_points": len(recent_values),
            "trend_percent": trend_percent,
            "trend_direction": trend_direction,
            "current_value": recent_metric_values[-1] if recent_metric_values else None,
            "average": statistics.mean(recent_metric_values),
            "min": min(recent_metric_values),
            "max": max(recent_metric_values),
        }

    def get_performance_health_score(self) -> Dict[str, Any]:
        """Calculate overall performance health score."""
        health_factors = {}
        health_score = 100

        # Check response times
        response_metrics = [k for k in self.current_metrics.keys() if "response_time" in k]
        if response_metrics:
            avg_response_time = statistics.mean(
                [
                    self._get_latest_value(metric)
                    for metric in response_metrics
                    if self._get_latest_value(metric) is not None
                ]
            )
            if avg_response_time > 2.0:  # > 2 seconds
                health_score -= 20
                health_factors["response_time"] = "poor"
            elif avg_response_time > 1.0:  # > 1 second
                health_score -= 10
                health_factors["response_time"] = "fair"
            else:
                health_factors["response_time"] = "good"

        # Check success rates
        success_metrics = [k for k in self.current_metrics.keys() if "success_rate" in k]
        if success_metrics:
            avg_success_rate = statistics.mean(
                [
                    self._get_latest_value(metric)
                    for metric in success_metrics
                    if self._get_latest_value(metric) is not None
                ]
            )
            if avg_success_rate < 0.8:  # < 80%
                health_score -= 25
                health_factors["success_rate"] = "poor"
            elif avg_success_rate < 0.9:  # < 90%
                health_score -= 10
                health_factors["success_rate"] = "fair"
            else:
                health_factors["success_rate"] = "good"

        # Check user satisfaction
        satisfaction_values = self.metrics_history.get("user_satisfaction", [])
        if satisfaction_values:
            avg_satisfaction = statistics.mean([m.value for m in satisfaction_values])
            if avg_satisfaction < 3.0:  # < 3/5
                health_score -= 15
                health_factors["satisfaction"] = "poor"
            elif avg_satisfaction < 4.0:  # < 4/5
                health_score -= 5
                health_factors["satisfaction"] = "fair"
            else:
                health_factors["satisfaction"] = "good"

        # Determine overall health status
        if health_score >= 90:
            status = "excellent"
        elif health_score >= 75:
            status = "good"
        elif health_score >= 60:
            status = "fair"
        else:
            status = "poor"

        return {
            "health_score": max(0, health_score),
            "status": status,
            "factors": health_factors,
            "timestamp": datetime.now().isoformat(),
        }

    def take_snapshot(
        self, system_info: Dict[str, Any] = None, agent_status: Dict[str, Any] = None
    ):
        """Take a performance snapshot."""
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(),
            metrics=self.current_metrics.copy(),
            system_info=system_info or {},
            agent_status=agent_status or {},
        )
        self.snapshots.append(snapshot)

        # Keep only recent snapshots
        if len(self.snapshots) > 100:
            self.snapshots = self.snapshots[-100:]

    def _record_metric(self, name: str, value: float, context: Dict[str, Any], unit: str = "count"):
        """Record a performance metric."""
        metric = PerformanceMetric(
            name=name, value=value, timestamp=datetime.now(), context=context, unit=unit
        )
        self.metrics_history[name].append(metric)

    def _get_latest_value(self, metric_name: str) -> Optional[float]:
        """Get the latest value for a metric."""
        if metric_name in self.metrics_history and self.metrics_history[metric_name]:
            return self.metrics_history[metric_name][-1].value
        return None

    def export_performance_data(self, filename: str = None) -> str:
        """Export performance data to JSON file."""
        if filename is None:
            filename = f"performance_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "metrics_history": {
                name: [
                    {
                        "value": m.value,
                        "timestamp": m.timestamp.isoformat(),
                        "context": m.context,
                        "unit": m.unit,
                    }
                    for m in metrics
                ]
                for name, metrics in self.metrics_history.items()
            },
            "performance_data": self.performance_data,
            "snapshots": [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "metrics": s.metrics,
                    "system_info": s.system_info,
                    "agent_status": s.agent_status,
                }
                for s in self.snapshots
            ],
        }

        with open(filename, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Performance data exported to {filename}")
        return filename

    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Generate performance optimization recommendations."""
        recommendations = []

        # Response time recommendations
        for metric_name in self.metrics_history.keys():
            if "response_time" in metric_name:
                trend = self.get_trend_analysis(metric_name, hours=24)
                if trend.get("trend_direction") == "degrading":
                    recommendations.append(
                        {
                            "type": "response_time",
                            "priority": "high",
                            "metric": metric_name,
                            "issue": f"Response time is degrading ({trend.get('trend_percent', 0):.1f}% increase)",
                            "recommendation": "Consider optimizing the operation or increasing resources",
                        }
                    )

        # Success rate recommendations
        for metric_name in self.metrics_history.keys():
            if "success_rate" in metric_name:
                latest_value = self._get_latest_value(metric_name)
                if latest_value is not None and latest_value < 0.8:
                    recommendations.append(
                        {
                            "type": "success_rate",
                            "priority": "high",
                            "metric": metric_name,
                            "issue": f"Low success rate ({latest_value:.1%})",
                            "recommendation": "Review error handling and validation logic",
                        }
                    )

        # Resource usage recommendations
        cpu_values = [m.value for m in self.metrics_history.get("cpu_usage", [])]
        if cpu_values and statistics.mean(cpu_values[-10:]) > 80:
            recommendations.append(
                {
                    "type": "resource_usage",
                    "priority": "medium",
                    "metric": "cpu_usage",
                    "issue": "High CPU usage detected",
                    "recommendation": "Consider scaling resources or optimizing CPU-intensive operations",
                }
            )

        return recommendations


# Global performance tracker instance
performance_tracker = PerformanceTracker()


def get_performance_tracker() -> PerformanceTracker:
    """Get the global performance tracker instance."""
    return performance_tracker


def track_agent_performance(operation: str, duration: float, success: bool = True):
    """Track agent performance metrics."""
    tracker = get_performance_tracker()
    tracker.track_response_time(operation, duration, success)
    tracker.track_success_rate(operation, success)


def get_system_performance_summary() -> Dict[str, Any]:
    """Get system performance summary."""
    tracker = get_performance_tracker()
    return tracker.get_performance_summary()


def get_performance_health() -> Dict[str, Any]:
    """Get system performance health score."""
    tracker = get_performance_tracker()
    return tracker.get_performance_health_score()
