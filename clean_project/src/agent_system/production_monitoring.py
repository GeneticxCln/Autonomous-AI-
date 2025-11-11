"""
Production monitoring system with enterprise-grade observability.
Addresses performance optimization and monitoring requirements.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Deque, Dict, Iterator, List, Optional

import psutil

from .exceptions import MonitoringError

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Represents a single metric data point."""
    
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    """Defines alerting rules for metrics."""
    
    metric_name: str
    condition: str  # "gt", "lt", "eq"
    threshold: float
    severity: str  # "critical", "warning", "info"
    duration: int = 60  # seconds before triggering
    callback: Optional[Callable[[Dict[str, Any]], None]] = None


@dataclass
class PerformanceThreshold:
    """Performance thresholds for system optimization."""
    
    cpu_warning: float = 80.0
    cpu_critical: float = 90.0
    memory_warning: float = 85.0
    memory_critical: float = 95.0
    disk_warning: float = 80.0
    disk_critical: float = 90.0
    response_time_warning: float = 5.0  # seconds
    response_time_critical: float = 10.0
    error_rate_warning: float = 5.0  # percentage
    error_rate_critical: float = 10.0


class ProductionMonitoring:
    """
    Production monitoring system with:
    - Real-time metrics collection
    - Performance optimization alerts
    - System resource monitoring
    - Custom business metrics
    - Automated performance recommendations
    """
    
    def __init__(self) -> None:
        self.metrics: Dict[str, Deque[MetricPoint]] = defaultdict(lambda: deque(maxlen=1000))
        self.alert_rules: List[AlertRule] = []
        self.thresholds = PerformanceThreshold()
        self.start_time = datetime.now()
        self.last_alerts: Dict[str, datetime] = {}
        self.performance_baseline: Dict[str, float] = {}
        self._monitoring_active = False
        self._monitor_task: Optional[asyncio.Task[None]] = None
        
        # Initialize default alert rules
        self._setup_default_alerts()
        
    def _setup_default_alerts(self) -> None:
        """Set up default alert rules for critical system metrics."""
        self.alert_rules = [
            AlertRule("cpu_usage", "gt", self.thresholds.cpu_critical, "critical"),
            AlertRule("memory_usage", "gt", self.thresholds.memory_critical, "critical"),
            AlertRule("disk_usage", "gt", self.thresholds.disk_critical, "critical"),
            AlertRule("response_time", "gt", self.thresholds.response_time_critical, "critical"),
            AlertRule("error_rate", "gt", self.thresholds.error_rate_critical, "critical"),
        ]
    
    def record_metric(
        self, 
        name: str, 
        value: float, 
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a metric data point."""
        try:
            metric_point = MetricPoint(
                name=name,
                value=value,
                tags=tags or {},
                metadata=metadata or {}
            )
            self.metrics[name].append(metric_point)
            
            # Check alert rules
            self._check_alerts(name, value)
            
        except Exception as e:
            logger.error(f"Error recording metric {name}: {e}")
            raise MonitoringError(f"Failed to record metric {name}", metric_name=name)
    
    def _check_alerts(self, metric_name: str, value: float) -> None:
        """Check if metric value triggers any alert rules."""
        now = datetime.now()
        
        for rule in self.alert_rules:
            if rule.metric_name != metric_name:
                continue
                
            triggered = self._evaluate_condition(value, rule.condition, rule.threshold)
            
            if triggered:
                last_alert = self.last_alerts.get(f"{metric_name}_{rule.severity}")
                if last_alert and (now - last_alert).seconds < rule.duration:
                    continue
                
                self.last_alerts[f"{metric_name}_{rule.severity}"] = now
                self._trigger_alert(rule, value)
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Evaluate alert condition."""
        if condition == "gt":
            return value > threshold
        elif condition == "lt":
            return value < threshold
        elif condition == "eq":
            return abs(value - threshold) < 0.001
        return False
    
    def _trigger_alert(self, rule: AlertRule, value: float) -> None:
        """Trigger an alert."""
        alert_data = {
            "metric": rule.metric_name,
            "value": value,
            "threshold": rule.threshold,
            "condition": rule.condition,
            "severity": rule.severity,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.warning(f"Alert triggered: {rule.severity} - {rule.metric_name} = {value}")
        
        if rule.callback:
            try:
                rule.callback(alert_data)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
    
    def record_request(
        self, 
        endpoint: str, 
        method: str, 
        status_code: int, 
        duration: float,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None
    ) -> None:
        """Record HTTP request metrics."""
        try:
            # Basic request metrics
            self.record_metric("request_count", 1)
            self.record_metric("request_duration", duration)
            
            # Status code based metrics
            if status_code >= 500:
                self.record_metric("error_count", 1)
            elif status_code >= 400:
                self.record_metric("warning_count", 1)
            else:
                self.record_metric("success_count", 1)
            
            # Request/response sizes
            if request_size:
                self.record_metric("request_size", request_size)
            if response_size:
                self.record_metric("response_size", response_size)
            
        except Exception as e:
            logger.error(f"Error recording request metrics: {e}")
    
    def update_system_metrics(self) -> None:
        """Update system resource metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            self.record_metric("cpu_usage", cpu_percent, tags={"unit": "percent"})
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.record_metric("memory_usage", memory.percent, tags={"unit": "percent"})
            self.record_metric("memory_available", memory.available, tags={"unit": "bytes"})
            
            # Disk usage
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100
            self.record_metric("disk_usage", disk_percent, tags={"unit": "percent"})
            
            # Network I/O
            network = psutil.net_io_counters()
            if network:
                self.record_metric("network_bytes_sent", network.bytes_sent)
                self.record_metric("network_bytes_recv", network.bytes_recv)
            
            # Process info
            process = psutil.Process()
            if hasattr(process, "memory_info"):
                self.record_metric("process_memory", process.memory_info().rss)
            if hasattr(process, "num_threads"):
                self.record_metric("process_threads", process.num_threads())
                
        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")
    
    def get_current_performance(self) -> Dict[str, Any]:
        """Get current performance snapshot."""
        try:
            metrics: Dict[str, Any] = {}
            
            # Get recent values for key metrics
            for metric_name, points in self.metrics.items():
                if points:
                    latest = points[-1]
                    metrics[metric_name] = {
                        "current_value": latest.value,
                        "timestamp": latest.timestamp.isoformat(),
                        "tags": latest.tags
                    }
            
            # Calculate derived metrics
            metrics["error_rate"] = self._calculate_error_rate()
            metrics["response_time_p95"] = self._calculate_percentile("request_duration", 0.95)
            metrics["throughput"] = self._calculate_throughput()
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting current performance: {e}")
            return {}
    
    def _calculate_error_rate(self) -> float:
        """Calculate current error rate percentage."""
        try:
            error_points = [p for p in self.metrics.get("error_count", [])]
            success_points = [p for p in self.metrics.get("success_count", [])]
            
            total_errors = sum(p.value for p in error_points)
            total_success = sum(p.value for p in success_points)
            total_requests = total_errors + total_success
            
            if total_requests == 0:
                return 0.0
            
            return (total_errors / total_requests) * 100
            
        except Exception as e:
            logger.error(f"Error calculating error rate: {e}")
            return 0.0
    
    def _calculate_percentile(self, metric_name: str, percentile: float) -> float:
        """Calculate percentile for a metric."""
        try:
            points: List[MetricPoint] = list(self.metrics.get(metric_name, []))
            if not points:
                return 0.0
            
            values = sorted([p.value for p in points])
            index = int(percentile * len(values))
            return values[min(index, len(values) - 1)]
            
        except Exception as e:
            logger.error(f"Error calculating percentile for {metric_name}: {e}")
            return 0.0
    
    def _calculate_throughput(self) -> float:
        """Calculate current throughput (requests per minute)."""
        try:
            now = datetime.now()
            minute_ago = now - timedelta(minutes=1)
            
            recent_requests = [
                p for p in self.metrics.get("request_count", [])
                if p.timestamp >= minute_ago
            ]
            
            return sum(p.value for p in recent_requests)
            
        except Exception as e:
            logger.error(f"Error calculating throughput: {e}")
            return 0.0
    
    def get_performance_recommendations(self) -> List[Dict[str, Any]]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        try:
            # Get current performance snapshot
            current = self.get_current_performance()
            
            # CPU recommendations
            cpu_usage = current.get("cpu_usage", {}).get("current_value", 0)
            if cpu_usage > self.thresholds.cpu_warning:
                recommendations.append({
                    "type": "cpu_optimization",
                    "priority": "high" if cpu_usage > self.thresholds.cpu_critical else "medium",
                    "message": f"High CPU usage detected ({cpu_usage:.1f}%)",
                    "actions": [
                        "Review CPU-intensive operations",
                        "Consider horizontal scaling",
                        "Optimize algorithm complexity"
                    ]
                })
            
            # Memory recommendations
            memory_usage = current.get("memory_usage", {}).get("current_value", 0)
            if memory_usage > self.thresholds.memory_warning:
                recommendations.append({
                    "type": "memory_optimization",
                    "priority": "high" if memory_usage > self.thresholds.memory_critical else "medium",
                    "message": f"High memory usage detected ({memory_usage:.1f}%)",
                    "actions": [
                        "Review memory leaks",
                        "Optimize data structures",
                        "Consider garbage collection tuning"
                    ]
                })
            
            # Response time recommendations
            response_time = current.get("response_time_p95", 0)
            if response_time > self.thresholds.response_time_warning:
                recommendations.append({
                    "type": "response_time_optimization",
                    "priority": "high" if response_time > self.thresholds.response_time_critical else "medium",
                    "message": f"High response time detected (p95: {response_time:.2f}s)",
                    "actions": [
                        "Review database queries",
                        "Implement caching",
                        "Optimize API endpoints"
                    ]
                })
            
            # Error rate recommendations
            error_rate = current.get("error_rate", 0)
            if error_rate > self.thresholds.error_rate_warning:
                recommendations.append({
                    "type": "error_rate_optimization",
                    "priority": "high" if error_rate > self.thresholds.error_rate_critical else "medium",
                    "message": f"High error rate detected ({error_rate:.1f}%)",
                    "actions": [
                        "Review error logs",
                        "Fix failing dependencies",
                        "Implement circuit breakers"
                    ]
                })
            
            # Cache optimization
            if "cache_hit_ratio" in self.metrics:
                hit_ratio = self._get_latest_value("cache_hit_ratio", 0)
                if hit_ratio < 0.8:
                    recommendations.append({
                        "type": "cache_optimization",
                        "priority": "medium",
                        "message": f"Low cache hit ratio ({hit_ratio:.1%})",
                        "actions": [
                            "Review cache key strategy",
                            "Increase cache TTL",
                            "Add cache warming"
                        ]
                    })
            
        except Exception as e:
            logger.error(f"Error generating performance recommendations: {e}")
        
        return recommendations
    
    def _get_latest_value(self, metric_name: str, default: float = 0.0) -> float:
        """Get latest value for a metric."""
        points: List[MetricPoint] = list(self.metrics.get(metric_name, []))
        return points[-1].value if points else default
    
    def start_monitoring(self) -> None:
        """Start background monitoring tasks."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Production monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop background monitoring tasks."""
        self._monitoring_active = False
        if self._monitor_task:
            self._monitor_task.cancel()
        logger.info("Production monitoring stopped")
    
    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self._monitoring_active:
            try:
                self.update_system_metrics()
                await asyncio.sleep(60)  # Update every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)
    
    @contextmanager
    def performance_timer(self, operation_name: str) -> Iterator[None]:
        """Context manager for timing operations."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_metric(f"{operation_name}_duration", duration)
    
    def create_performance_baseline(self) -> Dict[str, float]:
        """Create performance baseline from current metrics."""
        try:
            baseline = {}
            
            for metric_name, points in self.metrics.items():
                if points:
                    # Use recent values for baseline (last 100 points)
                    recent_points = list(points)[-100:]
                    values = [p.value for p in recent_points]
                    baseline[metric_name] = sum(values) / len(values)
            
            self.performance_baseline = baseline
            logger.info(f"Created performance baseline with {len(baseline)} metrics")
            return baseline
            
        except Exception as e:
            logger.error(f"Error creating performance baseline: {e}")
            return {}
    
    def compare_to_baseline(self) -> Dict[str, Any]:
        """Compare current performance to baseline."""
        try:
            current = self.get_current_performance()
            comparison = {}
            
            for metric_name, baseline_value in self.performance_baseline.items():
                current_value = current.get(metric_name, {}).get("current_value", baseline_value)
                if baseline_value > 0:
                    deviation_percent = ((current_value - baseline_value) / baseline_value) * 100
                    comparison[metric_name] = {
                        "baseline": baseline_value,
                        "current": current_value,
                        "deviation_percent": deviation_percent,
                        "status": "degraded" if deviation_percent > 20 else "normal"
                    }
            
            return comparison
            
        except Exception as e:
            logger.error(f"Error comparing to baseline: {e}")
            return {}


# Global production monitoring instance
production_monitoring = ProductionMonitoring()


def get_monitoring() -> ProductionMonitoring:
    """Get the global production monitoring instance."""
    return production_monitoring