"""
Advanced Monitoring with Custom Business Metrics
Enterprise-grade observability and business intelligence
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from types import TracebackType
from typing import Any, Callable, Dict, List, Optional, ParamSpec, Type, TypeVar, cast

import psutil
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    PlatformCollector,
    ProcessCollector,
    Summary,
    generate_latest,
)
from prometheus_client.core import REGISTRY

from .cache_manager import cache_manager
from .job_manager import job_store

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric types for business monitoring."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class BusinessMetric:
    """Business metric definition."""

    name: str
    metric_type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    value: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AdvancedMonitoringSystem:
    """
    Advanced monitoring system with:
    - Custom business metrics
    - Performance metrics
    - Resource usage tracking
    - SLA monitoring
    - Business KPI tracking
    """

    def __init__(self, registry: Optional[CollectorRegistry] = None) -> None:
        self.registry: CollectorRegistry = registry or CollectorRegistry()
        self._owns_registry: bool = registry is None
        self.metrics: Dict[str, Any] = {}
        self.business_metrics: Dict[str, BusinessMetric] = {}
        self.alert_rules: List[Dict[str, Any]] = []
        self.sla_thresholds: Dict[str, Dict[str, Any]] = {}
        self.is_initialized: bool = False
        self.start_time: datetime = datetime.now()
        self.cache_state: Dict[str, int] = {"hit": 0, "miss": 0}
        self._last_network_counters: Optional[Any] = None

        # Initialize metric collectors
        self._init_prometheus_collectors()
        self._init_system_collectors()
        self._init_business_collectors()

    def _init_prometheus_collectors(self) -> None:
        """Initialize Prometheus metric collectors."""
        if not self._owns_registry:
            logger.debug("Using shared Prometheus registry; base collectors already registered")
            return
        try:
            # Add process and platform collectors
            ProcessCollector(registry=self.registry)
            PlatformCollector(registry=self.registry)

            logger.info("✅ Prometheus collectors initialized")
        except Exception as e:
            logger.error(f"❌ Prometheus collectors initialization failed: {e}")

    def _init_system_collectors(self) -> None:
        """Initialize system resource collectors."""
        # CPU Usage
        self.metrics["cpu_usage_percent"] = Gauge(
            "system_cpu_usage_percent", "CPU usage percentage", registry=self.registry
        )

        # Memory Usage
        self.metrics["memory_usage_bytes"] = Gauge(
            "system_memory_usage_bytes", "Memory usage in bytes", registry=self.registry
        )

        self.metrics["memory_usage_percent"] = Gauge(
            "system_memory_usage_percent", "Memory usage percentage", registry=self.registry
        )

        # Disk Usage
        self.metrics["disk_usage_percent"] = Gauge(
            "system_disk_usage_percent", "Disk usage percentage", registry=self.registry
        )

        # Network I/O
        self.metrics["network_bytes_sent"] = Counter(
            "system_network_bytes_sent_total", "Total network bytes sent", registry=self.registry
        )

        self.metrics["network_bytes_recv"] = Counter(
            "system_network_bytes_recv_total",
            "Total network bytes received",
            registry=self.registry,
        )

        # Process Info
        self.metrics["process_count"] = Gauge(
            "system_process_count", "Number of running processes", registry=self.registry
        )

        self.metrics["load_average_1m"] = Gauge(
            "system_load_average_1m", "System load average (1 minute)", registry=self.registry
        )

        self.metrics["load_average_5m"] = Gauge(
            "system_load_average_5m", "System load average (5 minutes)", registry=self.registry
        )

        self.metrics["load_average_15m"] = Gauge(
            "system_load_average_15m", "System load average (15 minutes)", registry=self.registry
        )

        self.metrics["uptime_seconds"] = Gauge(
            "system_uptime_seconds", "Application uptime in seconds", registry=self.registry
        )

        self.metrics["thread_count"] = Gauge(
            "system_thread_count", "Number of threads in agent process", registry=self.registry
        )

        self.metrics["open_file_descriptors"] = Gauge(
            "system_open_file_descriptors",
            "Total open file descriptors for agent process",
            registry=self.registry,
        )

        # Queue depth metric
        self.metrics["agent_job_queue_depth"] = Gauge(
            "agent_job_queue_depth",
            "Current depth of agent job queue",
            registry=self.registry,
        )

    def _init_business_collectors(self) -> None:
        """Initialize business-specific metric collectors."""
        # Request Metrics
        self.metrics["agent_requests_total"] = Counter(
            "agent_requests_total",
            "Total number of agent requests",
            ["method", "endpoint", "status"],
            registry=self.registry,
        )

        self.metrics["agent_request_duration_seconds"] = Histogram(
            "agent_request_duration_seconds",
            "Request duration in seconds",
            ["method", "endpoint"],
            registry=self.registry,
        )

        self.metrics["agent_request_size_bytes"] = Summary(
            "agent_request_size_bytes",
            "Request size in bytes",
            ["method", "endpoint"],
            registry=self.registry,
        )

        self.metrics["agent_response_size_bytes"] = Summary(
            "agent_response_size_bytes",
            "Response size in bytes",
            ["method", "endpoint"],
            registry=self.registry,
        )

        # Cache Metrics
        self.metrics["cache_requests_total"] = Counter(
            "cache_requests_total",
            "Total cache requests",
            ["operation", "status"],  # hit, miss, error
            registry=self.registry,
        )

        self.metrics["cache_duration_seconds"] = Summary(
            "cache_operation_duration_seconds",
            "Cache operation duration",
            ["operation"],
            registry=self.registry,
        )

        self.metrics["cache_size_bytes"] = Gauge(
            "cache_size_bytes", "Cache size in bytes", registry=self.registry
        )

        self.metrics["cache_items"] = Gauge(
            "cache_items_total", "Total number of cache items", registry=self.registry
        )

        # Queue Metrics
        self.metrics["queue_jobs_total"] = Counter(
            "queue_jobs_total",
            "Total queue jobs",
            ["status", "priority"],  # queued, started, finished, failed
            registry=self.registry,
        )

        self.metrics["queue_job_duration_seconds"] = Histogram(
            "queue_job_duration_seconds", "Queue job duration", ["priority"], registry=self.registry
        )

        self.metrics["queue_backlog_size"] = Gauge(
            "queue_backlog_size", "Current queue backlog size", ["priority"], registry=self.registry
        )

        self.metrics["queue_worker_count"] = Gauge(
            "queue_workers_total",
            "Total number of queue workers",
            ["priority"],
            registry=self.registry,
        )

        # AI/Agent Metrics
        self.metrics["agent_goals_total"] = Counter(
            "agent_goals_total",
            "Total number of goals processed",
            ["status"],  # completed, failed, cancelled
            registry=self.registry,
        )

        self.metrics["agent_goal_duration_seconds"] = Histogram(
            "agent_goal_duration_seconds",
            "Goal processing duration",
            ["priority"],
            registry=self.registry,
        )

        self.metrics["agent_actions_total"] = Counter(
            "agent_actions_total",
            "Total number of actions executed",
            ["tool", "status"],
            registry=self.registry,
        )

        self.metrics["agent_action_duration_seconds"] = Summary(
            "agent_action_duration_seconds",
            "Action execution duration",
            ["tool"],
            registry=self.registry,
        )

        # Session Metrics
        self.metrics["active_sessions"] = Gauge(
            "agent_active_sessions_total", "Number of active user sessions", registry=self.registry
        )

        self.metrics["session_duration_seconds"] = Histogram(
            "agent_session_duration_seconds", "User session duration", registry=self.registry
        )

        # Error Metrics
        self.metrics["errors_total"] = Counter(
            "agent_errors_total",
            "Total number of errors",
            ["type", "severity"],  # error, warning, critical
            registry=self.registry,
        )

        self.metrics["database_operations_total"] = Counter(
            "database_operations_total",
            "Total database operations",
            ["operation", "table", "status"],
            registry=self.registry,
        )

        self.metrics["database_operation_duration_seconds"] = Summary(
            "database_operation_duration_seconds",
            "Database operation duration",
            ["operation", "table"],
            registry=self.registry,
        )

        # System Health Metrics
        self.metrics["system_health_score"] = Gauge(
            "agent_system_health_score",
            "Overall system health score (0-100)",
            registry=self.registry,
        )

        self.metrics["component_health_score"] = Gauge(
            "agent_component_health_score",
            "Health score per subsystem (0-100)",
            ["component"],
            registry=self.registry,
        )

        self.metrics["active_incidents"] = Gauge(
            "agent_active_incidents_total",
            "Number of active health incidents",
            registry=self.registry,
        )

        # AI Performance Metrics
        self.metrics["ai_decision_accuracy"] = Gauge(
            "agent_decision_accuracy_ratio",
            "Current AI decision accuracy ratio",
            registry=self.registry,
        )

        self.metrics["ai_goal_completion_rate"] = Gauge(
            "agent_goal_completion_rate",
            "Goal completion rate ratio",
            registry=self.registry,
        )

        self.metrics["ai_learning_velocity"] = Gauge(
            "agent_learning_velocity",
            "Learning velocity ratio",
            registry=self.registry,
        )

        self.metrics["ai_decision_latency"] = Histogram(
            "agent_decision_latency_seconds",
            "Observed decision latency in seconds",
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
            registry=self.registry,
        )

        # Cache effectiveness
        self.metrics["cache_hit_ratio"] = Gauge(
            "cache_hit_ratio",
            "Rolling cache hit ratio (0-1)",
            registry=self.registry,
        )

        # Alerting metrics
        self.metrics["alert_events_total"] = Counter(
            "agent_alert_events_total",
            "Total alert events emitted",
            ["severity", "source"],
            registry=self.registry,
        )

    def record_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None,
    ) -> None:
        """Record HTTP request metrics."""
        try:
            # Record request
            self.metrics["agent_requests_total"].labels(
                method=method,
                endpoint=endpoint,
                status=f"{status_code // 100}xx",  # Group by status class
            ).inc()

            # Record duration
            self.metrics["agent_request_duration_seconds"].labels(
                method=method, endpoint=endpoint
            ).observe(duration)

            # Record sizes
            if request_size is not None:
                self.metrics["agent_request_size_bytes"].labels(
                    method=method, endpoint=endpoint
                ).observe(request_size)

            if response_size is not None:
                self.metrics["agent_response_size_bytes"].labels(
                    method=method, endpoint=endpoint
                ).observe(response_size)

        except Exception as e:
            logger.error(f"Error recording request metrics: {e}")

    def record_cache_operation(
        self,
        operation: str,  # get, set, delete
        status: str,  # hit, miss, error
        duration: Optional[float] = None,
    ) -> None:
        """Record cache operation metrics."""
        try:
            # Record operation count
            self.metrics["cache_requests_total"].labels(operation=operation, status=status).inc()

            # Record duration
            if duration is not None:
                self.metrics["cache_duration_seconds"].labels(operation=operation).observe(duration)

            if operation == "get":
                if status == "hit":
                    self.cache_state["hit"] += 1
                elif status == "miss":
                    self.cache_state["miss"] += 1
                self._update_cache_hit_ratio()

        except Exception as e:
            logger.error(f"Error recording cache metrics: {e}")

    def _update_cache_hit_ratio(self) -> None:
        """Update cache hit ratio gauge."""
        try:
            total = self.cache_state["hit"] + self.cache_state["miss"]
            if total == 0:
                return
            ratio = self.cache_state["hit"] / total
            self.metrics["cache_hit_ratio"].set(ratio)
        except Exception as e:
            logger.error(f"Error updating cache hit ratio: {e}")

    def record_queue_job(
        self,
        status: str,  # queued, started, finished, failed
        priority: str,  # low, normal, high, critical
        duration: Optional[float] = None,
    ) -> None:
        """Record queue job metrics."""
        try:
            # Record job count
            self.metrics["queue_jobs_total"].labels(status=status, priority=priority).inc()

            # Record duration
            if duration is not None:
                self.metrics["queue_job_duration_seconds"].labels(priority=priority).observe(
                    duration
                )

        except Exception as e:
            logger.error(f"Error recording queue metrics: {e}")

    def record_goal(
        self,
        status: str,  # completed, failed, cancelled
        priority: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> None:
        """Record goal metrics."""
        try:
            # Record goal count
            self.metrics["agent_goals_total"].labels(status=status).inc()

            # Record duration
            if duration is not None and priority:
                self.metrics["agent_goal_duration_seconds"].labels(priority=priority).observe(
                    duration
                )

        except Exception as e:
            logger.error(f"Error recording goal metrics: {e}")

    def record_action(
        self, tool: str, status: str, duration: Optional[float] = None  # success, failure
    ) -> None:
        """Record action metrics."""
        try:
            # Record action count
            self.metrics["agent_actions_total"].labels(tool=tool, status=status).inc()

            # Record duration
            if duration is not None:
                self.metrics["agent_action_duration_seconds"].labels(tool=tool).observe(duration)

        except Exception as e:
            logger.error(f"Error recording action metrics: {e}")

    def update_active_sessions(self, count: int) -> None:
        """Update active session count."""
        try:
            self.metrics["active_sessions"].set(count)
        except Exception as e:
            logger.error(f"Error updating active sessions: {e}")

    def record_session_duration(self, duration: float) -> None:
        """Record session duration."""
        try:
            self.metrics["session_duration_seconds"].observe(duration)
        except Exception as e:
            logger.error(f"Error recording session duration: {e}")

    def record_error(self, error_type: str, severity: str) -> None:  # error, warning, critical
        """Record error occurrence."""
        try:
            self.metrics["errors_total"].labels(type=error_type, severity=severity).inc()
        except Exception as e:
            logger.error(f"Error recording error metrics: {e}")

    def record_database_operation(
        self,
        operation: str,  # select, insert, update, delete
        table: str,
        status: str,  # success, error
        duration: Optional[float] = None,
    ) -> None:
        """Record database operation metrics."""
        try:
            # Record operation count
            self.metrics["database_operations_total"].labels(
                operation=operation, table=table, status=status
            ).inc()

            # Record duration
            if duration is not None:
                self.metrics["database_operation_duration_seconds"].labels(
                    operation=operation, table=table
                ).observe(duration)

        except Exception as e:
            logger.error(f"Error recording database metrics: {e}")

    def update_system_metrics(self) -> None:
        """Update system resource metrics."""
        try:
            # CPU Usage
            cpu_percent = psutil.cpu_percent(interval=None)
            self.metrics["cpu_usage_percent"].set(cpu_percent)

            # Memory Usage
            memory = psutil.virtual_memory()
            self.metrics["memory_usage_bytes"].set(memory.used)
            self.metrics["memory_usage_percent"].set(memory.percent)

            # Disk Usage
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100
            self.metrics["disk_usage_percent"].set(disk_percent)

            # Network I/O (incremental)
            network = psutil.net_io_counters()
            if self._last_network_counters is None:
                self._last_network_counters = network
            else:
                sent_diff = max(0, network.bytes_sent - self._last_network_counters.bytes_sent)
                recv_diff = max(0, network.bytes_recv - self._last_network_counters.bytes_recv)
                if sent_diff:
                    self.metrics["network_bytes_sent"].inc(sent_diff)
                if recv_diff:
                    self.metrics["network_bytes_recv"].inc(recv_diff)
                self._last_network_counters = network

            # Process info
            process_count = len(psutil.pids())
            self.metrics["process_count"].set(process_count)
            try:
                process = psutil.Process()
                if hasattr(process, "num_threads"):
                    self.metrics["thread_count"].set(process.num_threads())
                if hasattr(process, "num_fds"):
                    self.metrics["open_file_descriptors"].set(process.num_fds())
            except Exception:
                pass

            # Load Average (Unix only)
            try:
                load1, load5, load15 = psutil.getloadavg()
                self.metrics["load_average_1m"].set(load1)
                self.metrics["load_average_5m"].set(load5)
                self.metrics["load_average_15m"].set(load15)
            except AttributeError:
                # Windows doesn't have load average
                pass

            # Uptime
            uptime = (datetime.now() - self.start_time).total_seconds()
            self.metrics["uptime_seconds"].set(uptime)

        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")

    def update_health_metrics(self) -> None:
        """Update health-related gauges from the health monitor."""
        try:
            from .system_health_dashboard import system_health_monitor
        except Exception as e:
            logger.debug(f"System health monitor unavailable: {e}")
            return

        try:
            health = system_health_monitor.get_comprehensive_health_check()
            overall = getattr(health, "overall_health_score", 0) * 100
            self.metrics["system_health_score"].set(max(0, min(100, overall)))
            component_scores = getattr(health, "component_health", {}) or {}
            for component, score in component_scores.items():
                self.metrics["component_health_score"].labels(component=component).set(
                    max(0, min(100, score * 100))
                )
            active_issues = len(getattr(health, "active_issues", []) or [])
            self.metrics["active_incidents"].set(active_issues)
        except Exception as e:
            logger.error(f"Error updating health metrics: {e}")

    def update_ai_performance_metrics(self) -> None:
        """Update AI performance gauges using the performance monitor."""
        try:
            from .ai_performance_monitor import ai_performance_monitor
        except Exception as e:
            logger.debug(f"AI performance monitor unavailable: {e}")
            return

        try:
            performance = ai_performance_monitor.get_current_performance()
            metrics = (
                performance.get("current_metrics", {}) if isinstance(performance, dict) else {}
            )

            accuracy = metrics.get("decision_accuracy")
            if accuracy is not None:
                self.metrics["ai_decision_accuracy"].set(accuracy)

            goal_rate = metrics.get("goal_completion_rate")
            if goal_rate is not None:
                self.metrics["ai_goal_completion_rate"].set(goal_rate)

            learning_velocity = metrics.get("learning_velocity")
            if learning_velocity is not None:
                self.metrics["ai_learning_velocity"].set(learning_velocity)

            decision_time_ms = metrics.get("decision_time_ms")
            if decision_time_ms is not None:
                self.metrics["ai_decision_latency"].observe(max(0.0, decision_time_ms / 1000.0))
        except Exception as e:
            logger.error(f"Error updating AI performance metrics: {e}")

    async def update_queue_metrics(self) -> None:
        """Update queue depth metrics."""
        try:
            queue_depth = await job_store.get_queue_depth()
            self.metrics["agent_job_queue_depth"].set(queue_depth)
        except Exception as e:
            logger.error(f"Error updating queue metrics: {e}")

    def record_alert_event(self, severity: str, source: str) -> None:
        """Record alert events for Prometheus tracking."""
        try:
            self.metrics["alert_events_total"].labels(severity=severity, source=source).inc()
        except Exception as e:
            logger.error(f"Error recording alert event: {e}")

    def add_business_metric(
        self,
        name: str,
        metric_type: MetricType,
        description: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a custom business metric."""
        try:
            self.business_metrics[name] = BusinessMetric(
                name=name,
                metric_type=metric_type,
                description=description,
                value=value,
                metadata=metadata or {},
                labels=list(labels.keys()) if labels else [],
            )

            cache_key = f"metrics:business:{name}"
            payload = {
                "name": name,
                "type": metric_type.value,
                "description": description,
                "value": value,
                "labels": labels or {},
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat(),
            }

            async def _persist() -> None:
                try:
                    await cache_manager.set("metrics", cache_key, payload, ttl=3600)
                except Exception as exc:
                    logger.debug("Failed to persist business metric %s: %s", name, exc)

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_persist())
            except RuntimeError:
                asyncio.run(_persist())

            logger.debug(f"Business metric '{name}' recorded: {value}")

        except Exception as e:
            logger.error(f"Error adding business metric: {e}")

    async def get_business_metrics(self) -> Dict[str, Any]:
        """Get all business metrics."""
        try:
            metrics: Dict[str, Any] = {
                name: {
                    "name": metric.name,
                    "type": metric.metric_type.value,
                    "description": metric.description,
                    "value": metric.value,
                    "timestamp": metric.timestamp.isoformat(),
                    "labels": metric.labels,
                    "metadata": metric.metadata,
                }
                for name, metric in self.business_metrics.items()
            }

            try:
                cached_keys = await cache_manager.scan_namespace("metrics", "metrics:business:*")
                for cache_key in cached_keys:
                    cached_metric = await cache_manager.get("metrics", cache_key)
                    if not cached_metric:
                        continue

                    metric_name = cached_metric.get("name") or cache_key.split("metrics:business:")[-1]
                    cached_metric.setdefault("name", metric_name)
                    cached_ts = cached_metric.get("timestamp")

                    existing = metrics.get(metric_name)
                    if existing:
                        existing_ts = existing.get("timestamp")
                        if existing_ts and cached_ts and str(cached_ts) <= str(existing_ts):
                            continue

                    metrics[metric_name] = cached_metric
            except Exception as cache_error:
                logger.debug("Failed to load cached business metrics: %s", cache_error)

            return metrics
        except Exception as e:
            logger.error(f"Error getting business metrics: {e}")
            return {}

    def add_sla_threshold(self, metric_name: str, threshold: float, operator: str = "gt") -> None:
        """Add SLA threshold for monitoring."""
        self.sla_thresholds[metric_name] = {
            "threshold": threshold,
            "operator": operator,
            "created_at": datetime.now().isoformat(),
        }

    def check_sla_compliance(self) -> Dict[str, Any]:
        """Check SLA compliance against thresholds."""
        violations: list[dict[str, Any]] = []
        compliant: list[str] = []

        for metric_name, threshold_info in self.sla_thresholds.items():
            # This would be implemented with actual metric values
            # For now, just return structure
            violations.append(
                {
                    "metric": metric_name,
                    "threshold": threshold_info["threshold"],
                    "operator": threshold_info["operator"],
                    "status": "unknown",
                }
            )

        return {
            "compliant": compliant,
            "violations": violations,
            "total_metrics": len(self.sla_thresholds),
            "compliance_rate": (
                len(compliant) / len(self.sla_thresholds) * 100 if self.sla_thresholds else 0
            ),
        }

    def get_health_score(self) -> Dict[str, Any]:
        """Calculate overall system health score."""
        try:
            score = 100
            issues = []

            # Check system resources
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()

            if cpu_percent > 80:
                score -= 20
                issues.append(f"High CPU usage: {cpu_percent}%")

            if memory.percent > 85:
                score -= 25
                issues.append(f"High memory usage: {memory.percent}%")

            # Check error rates (would need actual metrics)
            # This is a placeholder for actual implementation

            return {
                "health_score": max(0, score),
                "status": "healthy" if score > 80 else "degraded" if score > 60 else "unhealthy",
                "issues": issues,
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            }

        except Exception as e:
            logger.error(f"Error calculating health score: {e}")
            return {"health_score": 0, "status": "error", "error": str(e)}

    def get_metricsExposition(self) -> bytes:
        """Get Prometheus metrics for exposition."""
        try:
            return cast(bytes, generate_latest(self.registry))
        except Exception as e:
            logger.error(f"Error generating metrics exposition: {e}")
            return b"# No metrics available"

    def get_metrics_info(self) -> Dict[str, Any]:
        """Get metrics system information."""
        return {
            "initialized": self.is_initialized,
            "metrics_count": len(self.metrics),
            "business_metrics_count": len(self.business_metrics),
            "sla_thresholds": len(self.sla_thresholds),
            "start_time": self.start_time.isoformat(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
        }


# Global monitoring instance
monitoring_system = AdvancedMonitoringSystem(REGISTRY)
cache_manager.register_monitoring_system(monitoring_system)


def _register_performance_alert_callback() -> None:
    try:
        from .ai_performance_monitor import ai_performance_monitor
    except Exception as e:
        logger.debug(f"AI performance monitor import failed for alert callbacks: {e}")
        return

    def _handle_alert(alert: Any) -> None:
        severity = getattr(alert, "severity", "unknown")
        severity_value = getattr(severity, "value", str(severity))
        source = getattr(alert, "metric_name", "unknown")
        monitoring_system.record_alert_event(severity_value, source)

    ai_performance_monitor.add_alert_callback(_handle_alert)


_register_performance_alert_callback()


# Decorator for automatic metrics collection
P = ParamSpec("P")
R = TypeVar("R")


def monitor_performance(
    metric_name: Optional[str] = None, track_errors: bool = True, track_duration: bool = True
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to automatically collect performance metrics."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start_time = time.time()
            error_occurred = False

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_occurred = True
                if track_errors:
                    monitoring_system.record_error(error_type=type(e).__name__, severity="error")
                raise
            finally:
                if track_duration:
                    duration = time.time() - start_time
                    metric_name_to_use = metric_name or f"{func.__module__}.{func.__name__}"
                    monitoring_system.record_action(
                        tool=metric_name_to_use,
                        status="error" if error_occurred else "success",
                        duration=duration,
                    )

        return wrapper

    return decorator


# Initialize monitoring system
async def initialize_monitoring() -> bool:
    """Initialize the global monitoring system."""
    try:
        if monitoring_system.is_initialized:
            return True
        monitoring_system.is_initialized = True
        monitoring_system.update_system_metrics()
        monitoring_system.update_health_metrics()
        monitoring_system.update_ai_performance_metrics()
        await monitoring_system.update_queue_metrics()

        # Set up periodic system metrics updates
        asyncio.create_task(_periodic_metrics_update())

        logger.info("✅ Advanced monitoring system initialized")
        return True
    except Exception as e:
        logger.error(f"❌ Monitoring system initialization failed: {e}")
        return False


async def _periodic_metrics_update() -> None:
    """Periodically update system metrics."""
    while True:
        try:
            monitoring_system.update_system_metrics()
            monitoring_system.update_health_metrics()
            monitoring_system.update_ai_performance_metrics()
            await monitoring_system.update_queue_metrics()
            await asyncio.sleep(60)  # Update every minute
        except Exception as e:
            logger.error(f"Error in periodic metrics update: {e}")
            await asyncio.sleep(60)


# Context manager for request monitoring
class RequestMonitor:
    """Context manager for monitoring individual requests."""

    def __init__(self, method: str, endpoint: str) -> None:
        self.method: str = method
        self.endpoint: str = endpoint
        self.start_time: Optional[float] = None

    def __enter__(self) -> "RequestMonitor":
        self.start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        duration = time.time() - (self.start_time or time.time())
        status_code = 200

        if exc_type is not None:
            status_code = 500

        monitoring_system.record_request(
            method=self.method, endpoint=self.endpoint, status_code=status_code, duration=duration
        )


# Convenience functions
def record_request(method: str, endpoint: str, status_code: int, duration: float) -> None:
    """Record a request."""
    monitoring_system.record_request(method, endpoint, status_code, duration)


def record_cache_hit(operation: str = "get") -> None:
    """Record cache hit."""
    monitoring_system.record_cache_operation(operation, "hit")


def record_cache_miss(operation: str = "get") -> None:
    """Record cache miss."""
    monitoring_system.record_cache_operation(operation, "miss")


def record_queue_job(status: str, priority: str, duration: Optional[float] = None) -> None:
    """Record queue job."""
    monitoring_system.record_queue_job(status, priority, duration)


def record_goal(
    status: str, priority: Optional[str] = None, duration: Optional[float] = None
) -> None:
    """Record goal."""
    monitoring_system.record_goal(status, priority, duration)


def get_health_status() -> Dict[str, Any]:
    """Get current health status."""
    return monitoring_system.get_health_score()


def get_metrics() -> bytes:
    """Get Prometheus metrics."""
    return monitoring_system.get_metricsExposition()


def get_metrics_info() -> Dict[str, Any]:
    """Get metrics information."""
    return monitoring_system.get_metrics_info()
