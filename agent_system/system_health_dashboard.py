"""
System Health Dashboard
Provides real-time monitoring and health status for the entire agent system.
"""
from __future__ import annotations

import time
import psutil
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, timedelta
import logging

from .unified_config import unified_config
from .performance_optimizer import performance_optimizer
from .security_validator import security_audit
from .ai_performance_monitor import ai_performance_monitor
from .cross_session_learning import cross_session_learning
from .ai_debugging import ai_debugger

logger = logging.getLogger(__name__)


@dataclass
class HealthMetrics:
    """System health metrics."""
    timestamp: float
    overall_health_score: float
    component_health: Dict[str, float]
    active_issues: List[str]
    performance_summary: Dict[str, Any]
    security_status: Dict[str, Any]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'overall_health_score': self.overall_health_score,
            'component_health': self.component_health,
            'active_issues': self.active_issues,
            'performance_summary': self.performance_summary,
            'security_status': self.security_status,
            'recommendations': self.recommendations
        }


class SystemHealthMonitor:
    """Monitors overall system health."""

    def __init__(self):
        self.health_history = deque(maxlen=100)
        self.last_check = 0
        self.check_interval = 30  # seconds
        self.component_weights = {
            'ai_performance': 0.25,
            'memory_optimization': 0.20,
            'security_validation': 0.20,
            'cross_session_learning': 0.15,
            'debug_system': 0.10,
            'configuration': 0.10
        }

    def get_comprehensive_health_check(self) -> HealthMetrics:
        """Perform comprehensive health check of all components."""
        try:
            component_health = self._check_all_components()
            overall_score = self._calculate_overall_health(component_health)
            active_issues = self._identify_active_issues(component_health)
            performance_summary = self._get_performance_summary()
            security_status = self._get_security_status()
            recommendations = self._generate_health_recommendations(component_health, performance_summary, security_status)

            health_metrics = HealthMetrics(
                timestamp=time.time(),
                overall_health_score=overall_score,
                component_health=component_health,
                active_issues=active_issues,
                performance_summary=performance_summary,
                security_status=security_status,
                recommendations=recommendations
            )

            # Store in history
            self.health_history.append(health_metrics)

            return health_metrics

        except Exception as e:
            logger.error(f"Error during health check: {e}")
            return HealthMetrics(
                timestamp=time.time(),
                overall_health_score=0.0,
                component_health={},
                active_issues=[f"Health check error: {str(e)}"],
                performance_summary={},
                security_status={},
                recommendations=["Investigate system health check errors"]
            )

    def _check_all_components(self) -> Dict[str, float]:
        """Check health of all system components."""
        component_scores = {}

        # AI Performance Monitor
        try:
            ai_perf = ai_performance_monitor.get_current_performance()
            ai_score = ai_perf.get('summary', {}).get('score', 0) / 100.0
            component_scores['ai_performance'] = ai_score
        except Exception as e:
            logger.error(f"AI performance check failed: {e}")
            component_scores['ai_performance'] = 0.0

        # Memory Optimizer
        try:
            memory_stats = performance_optimizer.memory_optimizer.get_memory_stats()
            memory_usage = memory_stats.get('percent', 0) / 100.0
            # Health score is inverse of memory usage (lower usage = higher health)
            memory_health = max(0.0, 1.0 - memory_usage)
            component_scores['memory_optimization'] = memory_health
        except Exception as e:
            logger.error(f"Memory optimization check failed: {e}")
            component_scores['memory_optimization'] = 0.0

        # Security Validation
        try:
            security_report = security_audit.generate_security_report()
            success_rate = security_report.get('summary', {}).get('success_rate', 0)
            component_scores['security_validation'] = success_rate
        except Exception as e:
            logger.error(f"Security validation check failed: {e}")
            component_scores['security_validation'] = 0.0

        # Cross-Session Learning
        try:
            learning_stats = cross_session_learning.get_knowledge_statistics()
            knowledge_health = learning_stats.get('knowledge_health', 0) / 100.0
            component_scores['cross_session_learning'] = knowledge_health
        except Exception as e:
            logger.error(f"Cross-session learning check failed: {e}")
            component_scores['cross_session_learning'] = 0.0

        # Debug System
        try:
            debug_stats = ai_debugger.generate_debug_report()
            decisions_tracked = debug_stats.get('statistics', {}).get('total_decisions', 0)
            # More decisions tracked indicates better observability
            debug_health = min(1.0, decisions_tracked / 100.0)
            component_scores['debug_system'] = debug_health
        except Exception as e:
            logger.error(f"Debug system check failed: {e}")
            component_scores['debug_system'] = 0.0

        # Configuration
        try:
            config_health = self._check_configuration_health()
            component_scores['configuration'] = config_health
        except Exception as e:
            logger.error(f"Configuration check failed: {e}")
            component_scores['configuration'] = 0.0

        return component_scores

    def _calculate_overall_health(self, component_scores: Dict[str, float]) -> float:
        """Calculate overall health score from component scores."""
        if not component_scores:
            return 0.0

        weighted_sum = 0.0
        total_weight = 0.0

        for component, score in component_scores.items():
            weight = self.component_weights.get(component, 0.0)
            weighted_sum += score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _identify_active_issues(self, component_scores: Dict[str, float]) -> List[str]:
        """Identify active issues based on component health."""
        issues = []

        for component, score in component_scores.items():
            if score < 0.3:
                issues.append(f"Critical issue in {component.replace('_', ' ')} (score: {score:.2f})")
            elif score < 0.6:
                issues.append(f"Performance issue in {component.replace('_', ' ')} (score: {score:.2f})")

        # Check system resources
        try:
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                issues.append(f"Critical memory usage: {memory.percent:.1f}%")

            cpu_percent = psutil.cpu_percent()
            if cpu_percent > 90:
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")

        except Exception as e:
            issues.append(f"Error checking system resources: {e}")

        return issues

    def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary from various sources."""
        try:
            perf_stats = performance_optimizer.get_comprehensive_stats()
            return perf_stats
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {'error': str(e)}

    def _get_security_status(self) -> Dict[str, Any]:
        """Get security status from audit system."""
        try:
            security_report = security_audit.generate_security_report()
            return security_report
        except Exception as e:
            logger.error(f"Error getting security status: {e}")
            return {'error': str(e)}

    def _check_configuration_health(self) -> float:
        """Check configuration health."""
        try:
            # Check if all required configuration sections are present
            required_sections = ['agent', 'tools', 'api', 'security', 'logging', 'ai']
            configured_providers = unified_config.get_configured_providers()

            # Base score for having configuration
            config_score = 0.5

            # Bonus for configured API providers
            provider_bonus = min(0.5, len(configured_providers) * 0.1)

            # Check for critical configurations
            if unified_config.security.secret_key != "change-this-in-production":
                config_score += 0.1

            return min(1.0, config_score + provider_bonus)

        except Exception as e:
            logger.error(f"Configuration health check failed: {e}")
            return 0.0

    def _generate_health_recommendations(
        self,
        component_scores: Dict[str, float],
        performance_summary: Dict[str, Any],
        security_status: Dict[str, Any]
    ) -> List[str]:
        """Generate health improvement recommendations."""
        recommendations = []

        # Component-specific recommendations
        for component, score in component_scores.items():
            if score < 0.3:
                if component == 'ai_performance':
                    recommendations.append("Review AI performance metrics and optimize slow components")
                elif component == 'memory_optimization':
                    recommendations.append("Increase memory cleanup frequency and optimize memory usage")
                elif component == 'security_validation':
                    recommendations.append("Improve input validation and security checks")
                elif component == 'cross_session_learning':
                    recommendations.append("Review learning patterns and knowledge base")
                elif component == 'debug_system':
                    recommendations.append("Enable more detailed debugging and monitoring")
                elif component == 'configuration':
                    recommendations.append("Review and complete system configuration")

        # Performance-based recommendations
        try:
            if 'memory' in performance_summary:
                memory_percent = performance_summary['memory'].get('percent', 0)
                if memory_percent > 80:
                    recommendations.append("High memory usage detected - consider optimizing memory-intensive operations")

            if 'response_times' in performance_summary:
                avg_response = performance_summary['response_times'].get('avg_response_time', 0)
                if avg_response > 1.0:
                    recommendations.append("Slow response times - consider implementing caching and optimization")

        except Exception as e:
            logger.error(f"Error generating performance recommendations: {e}")

        # Security-based recommendations
        try:
            failed_audits = security_status.get('summary', {}).get('failed_audits', 0)
            if failed_audits > 0:
                recommendations.append("Address security validation failures and improve input sanitization")

            critical_issues = security_status.get('critical_issues', 0)
            if critical_issues > 0:
                recommendations.append("Immediately address critical security issues")

        except Exception as e:
            logger.error(f"Error generating security recommendations: {e}")

        # General recommendations
        overall_score = self._calculate_overall_health(component_scores)
        if overall_score < 0.6:
            recommendations.append("Overall system health is poor - perform comprehensive system review")

        return recommendations

    def get_health_trend(self, hours: int = 24) -> Dict[str, Any]:
        """Get health trend over specified time period."""
        if not self.health_history:
            return {'message': 'No health history available'}

        cutoff_time = time.time() - (hours * 3600)
        recent_health = [
            h for h in self.health_history
            if h.timestamp >= cutoff_time
        ]

        if not recent_health:
            return {'message': 'No health data for specified period'}

        # Calculate trend
        health_scores = [h.overall_health_score for h in recent_health]
        avg_health = sum(health_scores) / len(health_scores)
        min_health = min(health_scores)
        max_health = max(health_scores)

        # Determine trend direction
        if len(health_scores) >= 2:
            recent_avg = sum(health_scores[-5:]) / min(5, len(health_scores))
            earlier_avg = sum(health_scores[:5]) / min(5, len(health_scores))
            if recent_avg > earlier_avg + 0.1:
                trend = "improving"
            elif recent_avg < earlier_avg - 0.1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            'period_hours': hours,
            'data_points': len(recent_health),
            'average_health': avg_health,
            'minimum_health': min_health,
            'maximum_health': max_health,
            'trend': trend,
            'health_distribution': {
                'excellent': sum(1 for score in health_scores if score >= 0.8),
                'good': sum(1 for score in health_scores if 0.6 <= score < 0.8),
                'fair': sum(1 for score in health_scores if 0.4 <= score < 0.6),
                'poor': sum(1 for score in health_scores if score < 0.4)
            }
        }

    def get_system_summary(self) -> Dict[str, Any]:
        """Get comprehensive system summary."""
        current_health = self.get_comprehensive_health_check()
        health_trend = self.get_health_trend(24)

        return {
            'timestamp': datetime.now().isoformat(),
            'overall_health': {
                'score': current_health.overall_health_score,
                'status': self._get_health_status(current_health.overall_health_score),
                'active_issues': current_health.active_issues
            },
            'component_health': current_health.component_health,
            'trends': health_trend,
            'recommendations': current_health.recommendations[:5],  # Top 5 recommendations
            'monitoring_status': {
                'performance_monitoring': 'active',
                'security_auditing': 'active',
                'health_monitoring': 'active',
                'optimization': 'enabled' if performance_optimizer.is_enabled else 'disabled'
            }
        }

    def _get_health_status(self, score: float) -> str:
        """Convert health score to status string."""
        if score >= 0.9:
            return "excellent"
        elif score >= 0.7:
            return "good"
        elif score >= 0.5:
            return "fair"
        elif score >= 0.3:
            return "poor"
        else:
            return "critical"

    def export_health_report(self, filepath: str = None) -> str:
        """Export comprehensive health report to file."""
        if not filepath:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = f"system_health_report_{timestamp}.json"

        try:
            import json
            report = {
                'export_timestamp': datetime.now().isoformat(),
                'system_summary': self.get_system_summary(),
                'health_history': [h.to_dict() for h in self.health_history],
                'recommendations': self.get_comprehensive_health_check().recommendations
            }

            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"Health report exported to {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to export health report: {e}")
            return ""


# Global health monitor instance
system_health_monitor = SystemHealthMonitor()