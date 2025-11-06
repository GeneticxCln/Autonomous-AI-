"""
Security Validation System
Addresses input validation, resource bounds, and security concerns.
"""
from __future__ import annotations

import os
import re
import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import logging

from .unified_config import unified_config

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """Security level definitions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ValidationResult:
    """Result of security validation."""

    def __init__(self, is_valid: bool, level: SecurityLevel, message: str, suggestions: List[str] = None):
        self.is_valid = is_valid
        self.level = level
        self.message = message
        self.suggestions = suggestions or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'level': self.level.value,
            'message': self.message,
            'suggestions': self.suggestions
        }


@dataclass
class SecurityConfig:
    """Enhanced security configuration."""
    max_file_size_mb: int = 100
    allowed_file_extensions: Set[str] = None
    blocked_file_patterns: Set[str] = None
    max_path_depth: int = 10
    max_execution_time_seconds: int = 30
    allow_network_access: bool = True
    allowed_domains: Set[str] = None
    blocked_domains: Set[str] = None
    max_memory_mb: int = 1024
    max_cpu_percent: int = 80

    def __post_init__(self):
        if self.allowed_file_extensions is None:
            self.allowed_file_extensions = {
                '.txt', '.json', '.csv', '.py', '.md', '.log', '.yaml', '.yml', '.xml', '.html'
            }
        if self.blocked_file_patterns is None:
            self.blocked_file_patterns = {
                r'\.exe$', r'\.bat$', r'\.cmd$', r'\.sh$', r'\.ps1$', r'\.dll$', r'\.so$', r'\.dylib$'
            }
        if self.allowed_domains is None:
            self.allowed_domains = set()
        if self.blocked_domains is None:
            self.blocked_domains = set()


class InputValidator:
    """Validates user inputs for security."""

    def __init__(self):
        self.config = SecurityConfig()
        self.validation_rules = self._load_validation_rules()

    def _load_validation_rules(self) -> Dict[str, Any]:
        """Load input validation rules."""
        return {
            'file_path': {
                'max_length': 500,
                'forbidden_patterns': [r'\.\.', r'[/\\]\.\.[/\\]', r'[\x00-\x1f]'],
                'required_extensions': self.config.allowed_file_extensions
            },
            'code': {
                'max_length': 10000,
                'forbidden_patterns': [
                    r'import\s+os', r'import\s+subprocess', r'import\s+sys',
                    r'exec\s*\(', r'eval\s*\(', r'__import__', r'open\s*\(',
                    r'file\s*\.', r'input\s*\(', r'raw_input\s*\('
                ]
            },
            'shell_command': {
                'max_length': 200,
                'forbidden_patterns': [r'[;&|`$()]'],
                'allowed_commands': {'ls', 'cat', 'head', 'tail', 'wc', 'grep', 'pwd', 'echo'}
            },
            'url': {
                'max_length': 2000,
                'schemes': {'http', 'https'},
                'forbidden_patterns': [r'javascript:', r'data:', r'file:']
            }
        }

    def validate_file_path(self, file_path: str) -> ValidationResult:
        """Validate file path for security."""
        try:
            # Check length
            if len(file_path) > self.validation_rules['file_path']['max_length']:
                return ValidationResult(
                    False, SecurityLevel.HIGH,
                    f"File path too long: {len(file_path)} characters",
                    ["Use shorter file paths", "Consider using relative paths"]
                )

            # Check for forbidden patterns
            for pattern in self.validation_rules['file_path']['forbidden_patterns']:
                if re.search(pattern, file_path, re.IGNORECASE):
                    return ValidationResult(
                        False, SecurityLevel.CRITICAL,
                        f"File path contains forbidden pattern: {pattern}",
                        ["Remove forbidden characters", "Use safe file operations"]
                    )

            # Check file extension
            path_obj = Path(file_path)
            if path_obj.suffix and path_obj.suffix.lower() not in self.config.allowed_file_extensions:
                return ValidationResult(
                    False, SecurityLevel.HIGH,
                    f"File extension not allowed: {path_obj.suffix}",
                    [f"Use allowed extensions: {', '.join(self.config.allowed_file_extensions)}"]
                )

            # Check path depth
            if len(path_obj.parts) > self.config.max_path_depth:
                return ValidationResult(
                    False, SecurityLevel.MEDIUM,
                    f"File path too deep: {len(path_obj.parts)} levels",
                    ["Use shallower directory structures"]
                )

            return ValidationResult(True, SecurityLevel.LOW, "File path validation passed")

        except Exception as e:
            return ValidationResult(
                False, SecurityLevel.CRITICAL,
                f"Error validating file path: {str(e)}",
                ["Check file path format", "Ensure proper file path structure"]
            )

    def validate_code(self, code: str) -> ValidationResult:
        """Validate code for security."""
        try:
            # Check length
            if len(code) > self.validation_rules['code']['max_length']:
                return ValidationResult(
                    False, SecurityLevel.MEDIUM,
                    f"Code too long: {len(code)} characters",
                    ["Break code into smaller functions", "Use external files for large code"]
                )

            # Check for forbidden patterns
            for pattern in self.validation_rules['code']['forbidden_patterns']:
                if re.search(pattern, code, re.IGNORECASE):
                    return ValidationResult(
                        False, SecurityLevel.CRITICAL,
                        f"Code contains forbidden pattern: {pattern}",
                        ["Remove dangerous operations", "Use safe API alternatives"]
                    )

            return ValidationResult(True, SecurityLevel.LOW, "Code validation passed")

        except Exception as e:
            return ValidationResult(
                False, SecurityLevel.CRITICAL,
                f"Error validating code: {str(e)}",
                ["Check code syntax", "Ensure proper code structure"]
            )

    def validate_shell_command(self, command: str) -> ValidationResult:
        """Validate shell command for security."""
        try:
            # Check length
            if len(command) > self.validation_rules['shell_command']['max_length']:
                return ValidationResult(
                    False, SecurityLevel.HIGH,
                    f"Shell command too long: {len(command)} characters",
                    ["Use shorter commands", "Break complex commands into parts"]
                )

            # Check for forbidden patterns
            for pattern in self.validation_rules['shell_command']['forbidden_patterns']:
                if re.search(pattern, command):
                    return ValidationResult(
                        False, SecurityLevel.CRITICAL,
                        f"Shell command contains forbidden characters: {pattern}",
                        ["Remove special characters", "Use safe command alternatives"]
                    )

            # Check if it's an allowed command
            command_parts = command.split()
            if command_parts and command_parts[0] not in self.validation_rules['shell_command']['allowed_commands']:
                return ValidationResult(
                    False, SecurityLevel.HIGH,
                    f"Shell command not allowed: {command_parts[0]}",
                    [f"Use allowed commands: {', '.join(self.validation_rules['shell_command']['allowed_commands'])}"]
                )

            return ValidationResult(True, SecurityLevel.LOW, "Shell command validation passed")

        except Exception as e:
            return ValidationResult(
                False, SecurityLevel.CRITICAL,
                f"Error validating shell command: {str(e)}",
                ["Check command syntax", "Ensure proper command format"]
            )

    def validate_url(self, url: str) -> ValidationResult:
        """Validate URL for security."""
        try:
            # Check length
            if len(url) > self.validation_rules['url']['max_length']:
                return ValidationResult(
                    False, SecurityLevel.MEDIUM,
                    f"URL too long: {len(url)} characters",
                    ["Use shorter URLs", "Use URL shorteners if needed"]
                )

            # Parse URL
            from urllib.parse import urlparse
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme not in self.validation_rules['url']['schemes']:
                return ValidationResult(
                    False, SecurityLevel.HIGH,
                    f"URL scheme not allowed: {parsed.scheme}",
                    [f"Use allowed schemes: {', '.join(self.validation_rules['url']['schemes'])}"]
                )

            # Check for forbidden patterns
            for pattern in self.validation_rules['url']['forbidden_patterns']:
                if re.search(pattern, url, re.IGNORECASE):
                    return ValidationResult(
                        False, SecurityLevel.CRITICAL,
                        f"URL contains forbidden pattern: {pattern}",
                        ["Remove dangerous URL patterns", "Use safe URLs only"]
                    )

            # Check domain allowlist/blocklist
            if self.config.allowed_domains and parsed.netloc not in self.config.allowed_domains:
                return ValidationResult(
                    False, SecurityLevel.HIGH,
                    f"Domain not in allowlist: {parsed.netloc}",
                    ["Use allowed domains only", "Configure domain allowlist"]
                )

            if self.config.blocked_domains and parsed.netloc in self.config.blocked_domains:
                return ValidationResult(
                    False, SecurityLevel.CRITICAL,
                    f"Domain in blocklist: {parsed.netloc}",
                    ["Use different domain", "Remove from blocklist if legitimate"]
                )

            return ValidationResult(True, SecurityLevel.LOW, "URL validation passed")

        except Exception as e:
            return ValidationResult(
                False, SecurityLevel.HIGH,
                f"Error validating URL: {str(e)}",
                ["Check URL format", "Ensure proper URL structure"]
            )


class ResourceValidator:
    """Validates resource usage against limits."""

    def __init__(self):
        self.config = SecurityConfig()
        self.current_usage = {
            'memory_mb': 0,
            'cpu_percent': 0,
            'file_size_mb': 0,
            'execution_time': 0
        }

    def validate_memory_usage(self, memory_mb: float) -> ValidationResult:
        """Validate memory usage against limits."""
        if memory_mb > self.config.max_memory_mb:
            return ValidationResult(
                False, SecurityLevel.HIGH,
                f"Memory usage ({memory_mb}MB) exceeds limit ({self.config.max_memory_mb}MB)",
                ["Optimize memory usage", "Increase memory limits if appropriate", "Use streaming for large data"]
            )

        self.current_usage['memory_mb'] = memory_mb
        return ValidationResult(True, SecurityLevel.LOW, f"Memory usage ({memory_mb}MB) within limits")

    def validate_file_size(self, file_size_mb: float) -> ValidationResult:
        """Validate file size against limits."""
        if file_size_mb > self.config.max_file_size_mb:
            return ValidationResult(
                False, SecurityLevel.HIGH,
                f"File size ({file_size_mb}MB) exceeds limit ({self.config.max_file_size_mb}MB)",
                ["Use smaller files", "Compress files", "Stream large files"]
            )

        self.current_usage['file_size_mb'] = file_size_mb
        return ValidationResult(True, SecurityLevel.LOW, f"File size ({file_size_mb}MB) within limits")

    def validate_execution_time(self, execution_time: float) -> ValidationResult:
        """Validate execution time against limits."""
        if execution_time > self.config.max_execution_time_seconds:
            return ValidationResult(
                False, SecurityLevel.HIGH,
                f"Execution time ({execution_time}s) exceeds limit ({self.config.max_execution_time_seconds}s)",
                ["Optimize execution time", "Use asynchronous operations", "Break into smaller tasks"]
            )

        self.current_usage['execution_time'] = execution_time
        return ValidationResult(True, SecurityLevel.LOW, f"Execution time ({execution_time}s) within limits")

    def get_current_usage(self) -> Dict[str, Any]:
        """Get current resource usage."""
        return self.current_usage.copy()


class SecurityAudit:
    """Performs security audits of the system."""

    def __init__(self):
        self.input_validator = InputValidator()
        self.resource_validator = ResourceValidator()
        self.audit_log = []

    def audit_file_operations(self, file_paths: List[str]) -> List[ValidationResult]:
        """Audit file operations for security."""
        results = []
        for file_path in file_paths:
            result = self.input_validator.validate_file_path(file_path)
            results.append(result)
            self._log_audit_result("file_operation", file_path, result)

        return results

    def audit_code_execution(self, code_blocks: List[str]) -> List[ValidationResult]:
        """Audit code blocks for security."""
        results = []
        for code in code_blocks:
            result = self.input_validator.validate_code(code)
            results.append(result)
            self._log_audit_result("code_execution", "code_block", result)

        return results

    def audit_network_access(self, urls: List[str]) -> List[ValidationResult]:
        """Audit network access for security."""
        results = []
        for url in urls:
            result = self.input_validator.validate_url(url)
            results.append(result)
            self._log_audit_result("network_access", url, result)

        return results

    def audit_resource_usage(self, usage_data: Dict[str, float]) -> List[ValidationResult]:
        """Audit resource usage for compliance."""
        results = []

        if 'memory_mb' in usage_data:
            result = self.resource_validator.validate_memory_usage(usage_data['memory_mb'])
            results.append(result)

        if 'file_size_mb' in usage_data:
            result = self.resource_validator.validate_file_size(usage_data['file_size_mb'])
            results.append(result)

        if 'execution_time' in usage_data:
            result = self.resource_validator.validate_execution_time(usage_data['execution_time'])
            results.append(result)

        return results

    def _log_audit_result(self, operation_type: str, target: str, result: ValidationResult):
        """Log audit result."""
        import time
        self.audit_log.append({
            'timestamp': time.time(),
            'operation_type': operation_type,
            'target': target,
            'is_valid': result.is_valid,
            'level': result.level.value,
            'message': result.message
        })

    def get_audit_summary(self) -> Dict[str, Any]:
        """Get audit summary."""
        if not self.audit_log:
            return {'message': 'No audit data available'}

        total_audits = len(self.audit_log)
        failed_audits = sum(1 for audit in self.audit_log if not audit['is_valid'])
        success_rate = (total_audits - failed_audits) / total_audits if total_audits > 0 else 0

        # Group by level
        level_counts = {}
        for audit in self.audit_log:
            level = audit['level']
            level_counts[level] = level_counts.get(level, 0) + 1

        # Group by operation type
        operation_counts = {}
        for audit in self.audit_log:
            op_type = audit['operation_type']
            operation_counts[op_type] = operation_counts.get(op_type, 0) + 1

        return {
            'total_audits': total_audits,
            'failed_audits': failed_audits,
            'success_rate': success_rate,
            'level_distribution': level_counts,
            'operation_distribution': operation_counts,
            'recent_audits': self.audit_log[-10:]  # Last 10 audits
        }

    def generate_security_report(self) -> Dict[str, Any]:
        """Generate comprehensive security report."""
        summary = self.get_audit_summary()

        # Identify security concerns
        concerns = []
        if summary.get('failed_audits', 0) > 0:
            concerns.append("Security violations detected")
        if summary.get('success_rate', 1.0) < 0.95:
            concerns.append("Low security validation success rate")

        # Get recent critical issues
        critical_issues = [
            audit for audit in self.audit_log
            if not audit['is_valid'] and audit['level'] == 'critical'
        ]

        return {
            'summary': summary,
            'security_concerns': concerns,
            'critical_issues': len(critical_issues),
            'recent_critical_issues': critical_issues[-5:] if critical_issues else [],
            'recommendations': self._generate_security_recommendations()
        }

    def _generate_security_recommendations(self) -> List[str]:
        """Generate security recommendations based on audit results."""
        recommendations = []

        if not self.audit_log:
            return ["No audit data available. Start using security validation."]

        failed_count = sum(1 for audit in self.audit_log if not audit['is_valid'])
        total_count = len(self.audit_log)

        if failed_count / total_count > 0.1:
            recommendations.append("High failure rate detected. Review and improve input validation.")

        # Check for patterns
        operation_types = [audit['operation_type'] for audit in self.audit_log if not audit['is_valid']]
        if operation_types:
            most_problematic = max(set(operation_types), key=operation_types.count)
            recommendations.append(f"Focus on improving {most_problematic} security validations.")

        if not recommendations:
            recommendations.append("Good security posture. Continue regular security audits.")

        return recommendations


# Global security instances
input_validator = InputValidator()
resource_validator = ResourceValidator()
security_audit = SecurityAudit()