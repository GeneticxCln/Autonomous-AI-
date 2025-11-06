"""
Performance Optimization System
Addresses memory usage, I/O operations, and resource management bottlenecks.
"""
from __future__ import annotations

import gc
import time
import psutil
import threading
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from collections import deque
from pathlib import Path
import logging

from .unified_config import unified_config

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Real-time performance metrics."""
    timestamp: float
    cpu_percent: float
    memory_usage_mb: float
    memory_percent: float
    active_goals: int
    memory_size: int
    action_count: int
    avg_response_time: float
    error_rate: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'cpu_percent': self.cpu_percent,
            'memory_usage_mb': self.memory_usage_mb,
            'memory_percent': self.memory_percent,
            'active_goals': self.active_goals,
            'memory_size': self.memory_size,
            'action_count': self.action_count,
            'avg_response_time': self.avg_response_time,
            'error_rate': self.error_rate
        }


class MemoryOptimizer:
    """Manages memory usage optimization."""

    def __init__(self):
        self.memory_history = deque(maxlen=100)
        self.gc_threshold = 500  # MB
        self.cleanup_interval = 60  # seconds
        self.last_cleanup = time.time()
        self._start_background_monitoring()

    def _start_background_monitoring(self):
        """Start background memory monitoring."""
        def monitor():
            while True:
                try:
                    self.check_and_optimize_memory()
                    time.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    logger.error(f"Memory monitoring error: {e}")
                    time.sleep(60)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def check_and_optimize_memory(self):
        """Check memory usage and optimize if needed."""
        current_memory = psutil.virtual_memory()
        memory_mb = current_memory.used / (1024 * 1024)

        # Record memory history
        self.memory_history.append({
            'timestamp': time.time(),
            'memory_mb': memory_mb,
            'percent': current_memory.percent
        })

        # Auto cleanup if threshold exceeded
        if memory_mb > self.gc_threshold:
            logger.info(f"Memory usage ({memory_mb:.1f}MB) exceeds threshold, optimizing...")
            self.optimize_memory()

        # Periodic cleanup
        if time.time() - self.last_cleanup > self.cleanup_interval:
            self.cleanup_old_data()
            self.last_cleanup = time.time()

    def optimize_memory(self):
        """Perform memory optimization."""
        # Force garbage collection
        collected = gc.collect()
        logger.info(f"Garbage collection freed {collected} objects")

        # Clear memory history if too large
        if len(self.memory_history) > 80:
            self.memory_history = deque(list(self.memory_history)[-40:], maxlen=100)

    def cleanup_old_data(self):
        """Clean up old data from memory."""
        # Implementation would depend on specific data structures
        current_time = time.time()
        cutoff_time = current_time - 3600  # 1 hour

        # Clean up old memory entries in agent if accessible
        try:
            # This would be called from agent context
            if hasattr(self, 'agent') and self.agent:
                self._cleanup_agent_memories(cutoff_time)
        except Exception as e:
            logger.debug(f"Cleanup error: {e}")

    def _cleanup_agent_memories(self, cutoff_time: float):
        """Clean up old memories from agent."""
        # Implementation would depend on agent structure
        pass

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current memory statistics."""
        memory = psutil.virtual_memory()
        return {
            'total_mb': memory.total / (1024 * 1024),
            'used_mb': memory.used / (1024 * 1024),
            'available_mb': memory.available / (1024 * 1024),
            'percent': memory.percent,
            'history_size': len(self.memory_history),
            'gc_threshold_mb': self.gc_threshold
        }


class IOOptimizer:
    """Optimizes I/O operations and file access."""

    def __init__(self):
        self.file_cache = {}
        self.cache_size_limit = 100
        self.last_cache_cleanup = time.time()

    def optimize_file_operations(self):
        """Optimize file operation patterns."""
        # Implement file operation batching
        # Reduce redundant file reads
        # Cache frequently accessed files
        pass

    def cleanup_file_cache(self):
        """Clean up file cache."""
        current_time = time.time()
        if current_time - self.last_cache_cleanup > 300:  # 5 minutes
            # Remove old cache entries
            old_entries = [k for k, v in self.file_cache.items()
                          if current_time - v.get('timestamp', 0) > 600]  # 10 minutes

            for key in old_entries:
                del self.file_cache[key]

            self.last_cache_cleanup = current_time


class ResourceMonitor:
    """Monitors and manages system resources."""

    def __init__(self):
        self.performance_history = deque(maxlen=1000)
        self.resource_limits = unified_config.security
        self.alert_thresholds = {
            'cpu_percent': 80,
            'memory_percent': 85,
            'disk_percent': 90
        }
        self._start_monitoring()

    def _start_monitoring(self):
        """Start resource monitoring."""
        def monitor():
            while True:
                try:
                    self.record_metrics()
                    self.check_resource_limits()
                    time.sleep(10)  # Check every 10 seconds
                except Exception as e:
                    logger.error(f"Resource monitoring error: {e}")
                    time.sleep(30)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def record_metrics(self) -> PerformanceMetrics:
        """Record current performance metrics."""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Get process-specific metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            process_cpu = process.cpu_percent()

            metrics = PerformanceMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_usage_mb=process_memory.rss / (1024 * 1024),
                memory_percent=memory.percent,
                active_goals=getattr(self, 'active_goals', 0),
                memory_size=getattr(self, 'memory_size', 0),
                action_count=getattr(self, 'action_count', 0),
                avg_response_time=getattr(self, 'avg_response_time', 0.0),
                error_rate=getattr(self, 'error_rate', 0.0)
            )

            self.performance_history.append(metrics)
            return metrics

        except Exception as e:
            logger.error(f"Error recording metrics: {e}")
            return PerformanceMetrics(
                timestamp=time.time(),
                cpu_percent=0, memory_usage_mb=0, memory_percent=0,
                active_goals=0, memory_size=0, action_count=0,
                avg_response_time=0.0, error_rate=0.0
            )

    def check_resource_limits(self):
        """Check if resource limits are exceeded."""
        try:
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            alerts = []

            if cpu_percent > self.alert_thresholds['cpu_percent']:
                alerts.append(f"High CPU usage: {cpu_percent:.1f}%")

            if memory.percent > self.alert_thresholds['memory_percent']:
                alerts.append(f"High memory usage: {memory.percent:.1f}%")

            if disk.percent > self.alert_thresholds['disk_percent']:
                alerts.append(f"High disk usage: {disk.percent:.1f}%")

            # Check configured limits
            if memory.percent > self.resource_limits.max_memory_mb / 1024 * 100:
                alerts.append(f"Memory usage exceeds configured limit: {memory.percent:.1f}%")

            if alerts:
                logger.warning("Resource alerts: " + "; ".join(alerts))

            return alerts

        except Exception as e:
            logger.error(f"Error checking resource limits: {e}")
            return []

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary from history."""
        if not self.performance_history:
            return {'error': 'No performance data available'}

        recent_metrics = list(self.performance_history)[-10:]  # Last 10 entries

        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_usage_mb for m in recent_metrics]

        return {
            'avg_cpu_percent': sum(cpu_values) / len(cpu_values),
            'max_cpu_percent': max(cpu_values),
            'avg_memory_mb': sum(memory_values) / len(memory_values),
            'max_memory_mb': max(memory_values),
            'sample_count': len(recent_metrics),
            'alerts': self.check_resource_limits()
        }


class ResponseTimeOptimizer:
    """Optimizes response times."""

    def __init__(self):
        self.response_times = deque(maxlen=1000)
        self.slow_operations = []

    def record_operation(self, operation_name: str, duration: float, success: bool = True):
        """Record operation response time."""
        self.response_times.append({
            'timestamp': time.time(),
            'operation': operation_name,
            'duration': duration,
            'success': success
        })

        # Track slow operations
        if duration > 1.0:  # Operations taking more than 1 second
            self.slow_operations.append({
                'timestamp': time.time(),
                'operation': operation_name,
                'duration': duration
            })

    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance report."""
        if not self.response_times:
            return {'error': 'No response time data available'}

        # Calculate statistics
        durations = [op['duration'] for op in self.response_times]
        successful_ops = [op for op in self.response_times if op['success']]

        return {
            'total_operations': len(self.response_times),
            'successful_operations': len(successful_ops),
            'success_rate': len(successful_ops) / len(self.response_times) if self.response_times else 0,
            'avg_response_time': sum(durations) / len(durations),
            'max_response_time': max(durations),
            'min_response_time': min(durations),
            'slow_operations_count': len(self.slow_operations),
            'slowest_operations': sorted(self.slow_operations, key=lambda x: x['duration'], reverse=True)[:5]
        }


class PerformanceOptimizer:
    """Main performance optimization system."""

    def __init__(self):
        self.memory_optimizer = MemoryOptimizer()
        self.io_optimizer = IOOptimizer()
        self.resource_monitor = ResourceMonitor()
        self.response_optimizer = ResponseTimeOptimizer()
        self.is_enabled = True

    def optimize_system(self):
        """Perform comprehensive system optimization."""
        if not self.is_enabled:
            return

        try:
            # Memory optimization
            self.memory_optimizer.optimize_memory()

            # I/O optimization
            self.io_optimizer.cleanup_file_cache()

            # Resource monitoring
            self.resource_monitor.check_resource_limits()

            logger.debug("System optimization completed")

        except Exception as e:
            logger.error(f"Error during system optimization: {e}")

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        return {
            'memory': self.memory_optimizer.get_memory_stats(),
            'performance': self.resource_monitor.get_performance_summary(),
            'response_times': self.response_optimizer.get_performance_report(),
            'optimization_enabled': self.is_enabled
        }

    def create_optimization_suggestions(self) -> List[str]:
        """Generate optimization suggestions based on current metrics."""
        suggestions = []

        try:
            memory_stats = self.memory_optimizer.get_memory_stats()
            perf_summary = self.resource_monitor.get_performance_summary()
            response_report = self.response_optimizer.get_performance_report()

            # Memory-based suggestions
            if memory_stats['percent'] > 80:
                suggestions.append("High memory usage detected. Consider reducing memory-intensive operations.")

            if memory_stats['history_size'] > 80:
                suggestions.append("Large memory history. Implement more aggressive memory cleanup.")

            # CPU-based suggestions
            if perf_summary.get('avg_cpu_percent', 0) > 70:
                suggestions.append("High CPU usage. Consider optimizing computational processes.")

            # Response time suggestions
            if 'avg_response_time' in response_report and response_report['avg_response_time'] > 0.5:
                suggestions.append("Slow response times detected. Consider implementing caching.")

            if response_report.get('slow_operations_count', 0) > 10:
                suggestions.append("Many slow operations. Profile and optimize slow components.")

            # Success rate suggestions
            if response_report.get('success_rate', 1.0) < 0.95:
                suggestions.append("Low success rate. Review error handling and retry mechanisms.")

        except Exception as e:
            logger.error(f"Error generating optimization suggestions: {e}")

        return suggestions

    def enable_optimization(self):
        """Enable performance optimization."""
        self.is_enabled = True
        logger.info("Performance optimization enabled")

    def disable_optimization(self):
        """Disable performance optimization."""
        self.is_enabled = False
        logger.info("Performance optimization disabled")


# Global performance optimizer instance
performance_optimizer = PerformanceOptimizer()