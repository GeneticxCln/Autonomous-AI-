"""
Enhanced Autonomous Agent with improved architecture.
Integrates all new optimization and security systems.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .agent import AutonomousAgent  # Import original agent
from .models import Goal
from .performance_optimizer import performance_optimizer
from .security_validator import input_validator, security_audit
from .system_health_dashboard import system_health_monitor
from .unified_config import unified_config

logger = logging.getLogger(__name__)


class EnhancedAutonomousAgent(AutonomousAgent):
    """Enhanced autonomous agent with performance optimization and security."""

    def __init__(self):
        # Initialize enhanced systems first
        self.config = unified_config
        self.performance_optimizer = performance_optimizer
        self.security_audit = security_audit
        self.health_monitor = system_health_monitor

        # Initialize parent class (original agent)
        super().__init__()

        # Initialize enhanced features
        self._setup_enhanced_logging()
        self._validate_initial_configuration()
        self._start_background_monitoring()

        logger.info("Enhanced Autonomous Agent initialized with optimization and security")

    def _setup_enhanced_logging(self):
        """Setup enhanced logging configuration."""
        try:
            log_level = getattr(logging, self.config.logging.level.upper(), logging.INFO)
            log_format = self.config.logging.format

            # Configure root logger
            logging.basicConfig(level=log_level, format=log_format, handlers=[])

            # Add console handler if enabled
            if self.config.logging.enable_console:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(log_level)
                console_handler.setFormatter(logging.Formatter(log_format))
                logging.getLogger().addHandler(console_handler)

            # Add file handler if enabled
            if self.config.logging.enable_file:
                try:
                    from logging.handlers import RotatingFileHandler

                    file_handler = RotatingFileHandler(
                        self.config.logging.file_path,
                        maxBytes=self.config.logging.max_file_size_mb * 1024 * 1024,
                        backupCount=self.config.logging.backup_count,
                    )
                    file_handler.setLevel(log_level)
                    file_handler.setFormatter(logging.Formatter(log_format))
                    logging.getLogger().addHandler(file_handler)
                except Exception as e:
                    logger.warning(f"Failed to setup file logging: {e}")

        except Exception as e:
            logger.error(f"Failed to setup enhanced logging: {e}")

    def _validate_initial_configuration(self):
        """Validate agent configuration on startup."""
        try:
            # Validate security configuration
            if self.config.security.enable_input_validation:
                logger.info("Input validation enabled")
            else:
                logger.warning("Input validation disabled - security risk")

            # Check API configuration
            configured_providers = self.config.get_configured_providers()
            if configured_providers:
                logger.info(f"Configured API providers: {', '.join(configured_providers)}")
            else:
                logger.warning("No API providers configured - using mock tools")

            # Validate resource limits
            if self.config.security.max_memory_mb < 512:
                logger.warning(
                    f"Low memory limit configured: {self.config.security.max_memory_mb}MB"
                )

        except Exception as e:
            logger.error(f"Configuration validation error: {e}")

    def _start_background_monitoring(self):
        """Start background monitoring and optimization."""
        try:
            # Start performance monitoring
            if self.config.agent.enable_performance_monitoring:
                logger.info("Performance monitoring enabled")

            # Start security auditing
            if self.config.security.enable_input_validation:
                logger.info("Security auditing enabled")

            # Log system health
            health_status = self.health_monitor.get_comprehensive_health_check()
            logger.info(f"System health score: {health_status.overall_health_score:.2f}")

        except Exception as e:
            logger.error(f"Failed to start background monitoring: {e}")

    def add_goal(
        self, description: str, priority: float = 0.5, constraints: Optional[Dict[str, Any]] = None
    ) -> Goal:
        """Add goal with security validation."""
        try:
            # Validate goal description
            if self.config.security.enable_input_validation:
                validation_result = input_validator.validate_code(description)
                if not validation_result.is_valid:
                    logger.warning(
                        f"Goal description validation failed: {validation_result.message}"
                    )
                    # Don't reject, but log the issue

            # Call parent method
            goal = super().add_goal(description, priority, constraints)

            # Audit the goal addition
            self.security_audit.audit_file_operations([description])

            return goal

        except Exception as e:
            logger.error(f"Error adding goal: {e}")
            raise

    async def run_cycle_async(self, concurrency_limit: Optional[int] = None) -> bool:
        """Enhanced run cycle with performance and security monitoring."""
        start_time = time.time()

        try:
            self.performance_optimizer.response_optimizer.record_operation("run_cycle", 0.0)

            result = await super().run_cycle_async(concurrency_limit=concurrency_limit)

            duration = time.time() - start_time
            self.performance_optimizer.response_optimizer.record_operation(
                "run_cycle", duration, result
            )

            if self.performance_optimizer.is_enabled:
                self.performance_optimizer.optimize_system()

            return result

        except Exception as e:
            duration = time.time() - start_time
            self.performance_optimizer.response_optimizer.record_operation(
                "run_cycle", duration, False
            )
            logger.error(f"Error in run cycle: {e}")
            raise

    def get_enhanced_status(self) -> Dict[str, Any]:
        """Get enhanced status including all new systems."""
        try:
            # Get original status
            original_status = self.get_status()

            # Get system health
            system_health = self.health_monitor.get_comprehensive_health_check()

            # Get performance stats
            performance_stats = self.performance_optimizer.get_comprehensive_stats()

            # Get security audit summary
            security_summary = self.security_audit.get_audit_summary()

            # Get configuration summary
            config_summary = {
                "configured_providers": self.config.get_configured_providers(),
                "security_features": {
                    "input_validation": self.config.security.enable_input_validation,
                    "resource_limits": self.config.security.enable_resource_limits,
                    "sandbox_mode": self.config.security.enable_sandbox,
                },
                "optimization_features": {
                    "performance_monitoring": self.config.agent.enable_performance_monitoring,
                    "memory_optimization": True,
                    "security_auditing": True,
                },
            }

            # Combine all status information
            enhanced_status = {
                **original_status,
                "enhanced_features": {
                    "system_health": {
                        "overall_score": system_health.overall_health_score,
                        "status": self.health_monitor._get_health_status(
                            system_health.overall_health_score
                        ),
                        "active_issues": system_health.active_issues,
                        "recommendations": system_health.recommendations,
                    },
                    "performance": performance_stats,
                    "security": security_summary,
                    "configuration": config_summary,
                    "optimization_enabled": self.performance_optimizer.is_enabled,
                },
            }

            return enhanced_status

        except Exception as e:
            logger.error(f"Error getting enhanced status: {e}")
            return self.get_status()

    def get_system_recommendations(self) -> List[str]:
        """Get system optimization recommendations."""
        try:
            recommendations = []

            # Get health-based recommendations
            health_status = self.health_monitor.get_comprehensive_health_check()
            recommendations.extend(health_status.recommendations)

            # Get performance-based recommendations
            perf_suggestions = self.performance_optimizer.create_optimization_suggestions()
            recommendations.extend(perf_suggestions)

            # Get security-based recommendations
            security_report = self.security_audit.generate_security_report()
            recommendations.extend(security_report.get("recommendations", []))

            # Configuration recommendations
            configured_providers = self.config.get_configured_providers()
            if not configured_providers:
                recommendations.append("Configure API providers for enhanced functionality")

            if self.config.security.secret_key == "change-this-in-production":
                recommendations.append("Change default secret key in production")

            return list(set(recommendations))  # Remove duplicates

        except Exception as e:
            logger.error(f"Error getting system recommendations: {e}")
            return ["Error generating recommendations - check system logs"]

    def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive system health check."""
        try:
            health_status = self.health_monitor.get_comprehensive_health_check()
            return health_status.to_dict()
        except Exception as e:
            logger.error(f"Error running health check: {e}")
            return {"error": str(e)}

    def enable_optimization(self):
        """Enable performance optimization."""
        self.performance_optimizer.enable_optimization()
        logger.info("Performance optimization enabled")

    def disable_optimization(self):
        """Disable performance optimization."""
        self.performance_optimizer.disable_optimization()
        logger.info("Performance optimization disabled")

    def export_comprehensive_report(self) -> str:
        """Export comprehensive system report."""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            report_file = f"agent_comprehensive_report_{timestamp}.json"

            report_data = {
                "export_timestamp": time.time(),
                "system_info": {
                    "agent_type": "Enhanced Autonomous Agent",
                    "version": "2.0.0",
                    "configuration": self.config._dataclass_to_dict(self.config.agent),
                },
                "current_status": self.get_enhanced_status(),
                "health_check": self.run_health_check(),
                "recommendations": self.get_system_recommendations(),
                "optimization_suggestions": self.performance_optimizer.create_optimization_suggestions(),
            }

            import json

            with open(report_file, "w") as f:
                json.dump(report_data, f, indent=2, default=str)

            logger.info(f"Comprehensive report exported to {report_file}")
            return report_file

        except Exception as e:
            logger.error(f"Error exporting comprehensive report: {e}")
            return ""

    def shutdown(self):
        """Enhanced shutdown with cleanup."""
        try:
            logger.info("Starting enhanced agent shutdown...")

            # Save configuration
            self.config.save_to_file()

            # Export final report
            final_report = self.export_comprehensive_report()
            if final_report:
                logger.info(f"Final report saved: {final_report}")

            # Shutdown performance optimizer
            if self.performance_optimizer.is_enabled:
                self.performance_optimizer.disable_optimization()

            # Call parent shutdown
            super().shutdown()

            logger.info("Enhanced agent shutdown completed")

        except Exception as e:
            logger.error(f"Error during enhanced shutdown: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with proper cleanup."""
        self.shutdown()


# Create a factory function for easy agent creation
def create_enhanced_agent(config_file: Optional[str] = None) -> EnhancedAutonomousAgent:
    """Create an enhanced agent with optional custom configuration."""
    if config_file:
        unified_config.config_file = config_file
        unified_config.load_from_file()

    return EnhancedAutonomousAgent()
