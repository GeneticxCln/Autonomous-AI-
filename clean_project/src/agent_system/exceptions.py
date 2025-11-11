"""
Standardized exception classes for the agent system.
Provides consistent error handling across all components.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class AgentError(Exception):
    """Base exception for all agent-related errors."""
    
    def __init__(
        self, 
        message: str, 
        code: str = "AGENT_ERROR", 
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.cause = cause
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
        }
    
    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ConfigurationError(AgentError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            details={"config_key": config_key} if config_key else {}
        )


class AuthenticationError(AgentError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, code="AUTHENTICATION_ERROR")


class AuthorizationError(AgentError):
    """Raised when user lacks required permissions."""
    
    def __init__(self, message: str, required_permission: Optional[str] = None):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            details={"required_permission": required_permission} if required_permission else {}
        )


class DatabaseError(AgentError):
    """Raised when database operations fail."""
    
    def __init__(
        self, 
        message: str, 
        operation: Optional[str] = None, 
        table: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            details={
                "operation": operation,
                "table": table
            },
            cause=cause
        )


class ToolExecutionError(AgentError):
    """Raised when tool execution fails."""
    
    def __init__(
        self, 
        message: str, 
        tool_name: Optional[str] = None, 
        parameters: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code="TOOL_EXECUTION_ERROR",
            details={
                "tool_name": tool_name,
                "parameters": parameters or {}
            }
        )


class PlanningError(AgentError):
    """Raised when planning operations fail."""
    
    def __init__(self, message: str, goal: Optional[str] = None):
        super().__init__(
            message=message,
            code="PLANNING_ERROR",
            details={"goal": goal} if goal else {}
        )


class LearningError(AgentError):
    """Raised when learning operations fail."""
    
    def __init__(self, message: str, learning_type: Optional[str] = None):
        super().__init__(
            message=message,
            code="LEARNING_ERROR",
            details={"learning_type": learning_type} if learning_type else {}
        )


class InfrastructureError(AgentError):
    """Raised when infrastructure operations fail."""
    
    def __init__(
        self, 
        message: str, 
        component: Optional[str] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code="INFRASTRUCTURE_ERROR",
            details={
                "component": component,
                "operation": operation
            }
        )


class MonitoringError(AgentError):
    """Raised when monitoring operations fail."""
    
    def __init__(
        self, 
        message: str, 
        metric_name: Optional[str] = None,
        monitoring_type: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code="MONITORING_ERROR",
            details={
                "metric_name": metric_name,
                "monitoring_type": monitoring_type
            }
        )


class SecurityError(AgentError):
    """Raised when security violations occur."""
    
    def __init__(
        self, 
        message: str, 
        security_level: str = "medium",
        violation_type: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code="SECURITY_ERROR",
            details={
                "security_level": security_level,
                "violation_type": violation_type
            }
        )


class ValidationError(AgentError):
    """Raised when input validation fails."""
    
    def __init__(
        self, 
        message: str, 
        field: Optional[str] = None,
        value: Any = None,
        validation_rule: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={
                "field": field,
                "value": str(value),
                "validation_rule": validation_rule
            }
        )


# Error recovery strategies
def handle_agent_error(error: Exception) -> Dict[str, Any]:
    """
    Handle agent errors with appropriate recovery strategies.
    
    Args:
        error: The exception to handle
        
    Returns:
        Dictionary with error information and recovery advice
    """
    if isinstance(error, AgentError):
        return {
            "error": error.to_dict(),
            "recovery_suggestion": _get_recovery_suggestion(error),
            "can_retry": _can_retry(error),
            "escalation_required": _requires_escalation(error)
        }
    else:
        return {
            "error": {
                "error": True,
                "code": "UNKNOWN_ERROR",
                "message": str(error),
                "type": type(error).__name__
            },
            "recovery_suggestion": "Contact support for unknown error",
            "can_retry": False,
            "escalation_required": True
        }


def _get_recovery_suggestion(error: AgentError) -> str:
    """Get recovery suggestion for specific error types."""
    suggestions = {
        "CONFIGURATION_ERROR": "Check environment variables and configuration files",
        "AUTHENTICATION_ERROR": "Verify credentials and authentication tokens",
        "AUTHORIZATION_ERROR": "Check user permissions and role assignments",
        "DATABASE_ERROR": "Verify database connectivity and schema",
        "TOOL_EXECUTION_ERROR": "Check tool parameters and external service availability",
        "PLANNING_ERROR": "Review goal definition and available actions",
        "INFRASTRUCTURE_ERROR": "Check infrastructure components and dependencies",
        "SECURITY_ERROR": "Review security settings and access controls"
    }
    return suggestions.get(error.code, "Review logs and system status for details")


def _can_retry(error: AgentError) -> bool:
    """Determine if operation can be retried."""
    no_retry_codes = {
        "CONFIGURATION_ERROR",
        "AUTHENTICATION_ERROR", 
        "AUTHORIZATION_ERROR",
        "VALIDATION_ERROR",
        "SECURITY_ERROR"
    }
    return error.code not in no_retry_codes


def _requires_escalation(error: AgentError) -> bool:
    """Determine if error requires escalation."""
    critical_codes = {
        "DATABASE_ERROR",
        "INFRASTRUCTURE_ERROR",
        "SECURITY_ERROR"
    }
    return error.code in critical_codes