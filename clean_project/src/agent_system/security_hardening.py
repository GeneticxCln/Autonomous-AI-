"""
Security Hardening for Enterprise Authentication
Additional security features and protections
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import re
import secrets
import time
from typing import Any, Dict
from urllib.parse import urlparse

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class SecurityHardening:
    """Advanced security hardening features."""

    def __init__(self):
        # Rate limiting with sliding window
        self.rate_limit_storage = {}
        self.failed_attempts = {}
        self.blocked_ips = {}

        # Suspicious activity detection
        self.suspicious_patterns = [
            r"(?i)(union\s+select|select\s+.*\s+from|drop\s+table|insert\s+into)",
            r"(?i)(script|javascript:|vbscript:|onload=|onerror=)",
            r"(?i)(<iframe|<object|<embed|<applet)",
            r"(?i)(../|\.\./|%2e%2e%2f)",
            r"(?i)(cmd\.exe|powershell|bash|sh)",
        ]

        # SQL injection patterns
        self.sql_injection_patterns = [
            r"(?i)('|(\\x27|\\')\\s*(or|and)\\s*('|\\x27|\\')\\s*\\d+\\s*=\\s*\\d+)",
            r"(?i)union\\s+select",
            r"(?i)drop\\s+(table|database)",
            r"(?i)insert\\s+into",
            r"(?i)update\\s+\\w+\\s+set",
            r"(?i)delete\\s+from",
        ]

        # XSS patterns
        self.xss_patterns = [
            r"(?i)<script[^>]*>.*?</script>",
            r"(?i)javascript:",
            r"(?i)on\\w+\\s*=",
            r"(?i)<iframe[^>]*>",
            r"(?i)<object[^>]*>",
        ]

        # Malicious file extensions
        self.malicious_extensions = [".exe", ".bat", ".cmd", ".com", ".pif", ".scr", ".vbs", ".js"]

    def validate_input(self, input_data: str, input_type: str = "general") -> bool:
        """Validate input for common security threats."""
        if not input_data or not isinstance(input_data, str):
            return True  # Allow empty inputs for optional fields

        # Check length limits
        if len(input_data) > 10000:  # 10KB limit
            logger.warning(f"Input too long: {len(input_data)} characters")
            return False

        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                logger.warning(f"Suspicious pattern detected: {pattern}")
                return False

        # Type-specific validation
        if input_type == "username":
            return self._validate_username(input_data)
        elif input_type == "password":
            return self._validate_password(input_data)
        elif input_type == "email":
            return self._validate_email(input_data)
        elif input_type == "url":
            return self._validate_url(input_data)

        return True

    def _validate_username(self, username: str) -> bool:
        """Validate username for security."""
        # Check length
        if len(username) < 3 or len(username) > 50:
            return False

        # Check for allowed characters (alphanumeric, underscore, hyphen)
        if not re.match(r"^[a-zA-Z0-9_-]+$", username):
            return False

        # Check for reserved names
        reserved_names = ["admin", "root", "system", "api", "test"]
        if username.lower() in reserved_names:
            return False

        return True

    def _validate_password(self, password: str) -> bool:
        """Validate password strength."""
        if len(password) < 8:
            return False

        # Check for at least one of each: uppercase, lowercase, digit, special char
        if not re.search(r"[A-Z]", password):
            return False
        if not re.search(r"[a-z]", password):
            return False
        if not re.search(r"\d", password):
            return False
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False

        # Check for common weak patterns
        weak_patterns = [
            r"^(.)\1{7,}$",  # All same character
            r"^[a-z]+$",  # Only lowercase
            r"^[A-Z]+$",  # Only uppercase
            r"^\d+$",  # Only digits
        ]

        for pattern in weak_patterns:
            if re.match(pattern, password):
                return False

        return True

    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            return False

        # Check domain validity
        domain = email.split("@")[1]
        if not self._is_valid_domain(domain):
            return False

        return True

    def _validate_url(self, url: str) -> bool:
        """Validate URL for security."""
        try:
            parsed = urlparse(url)

            # Only allow http and https
            if parsed.scheme not in ["http", "https"]:
                return False

            # Check for localhost/private IPs
            if self._is_private_ip(parsed.hostname):
                return False

            # Check for suspicious domains
            suspicious_domains = ["localhost", "127.0.0.1", "0.0.0.0"]
            if parsed.hostname in suspicious_domains:
                return False

            return True
        except Exception:
            return False

    def _is_valid_domain(self, domain: str) -> bool:
        """Check if domain is valid."""
        # Basic domain validation
        domain_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
        return bool(re.match(domain_pattern, domain))

    def _is_private_ip(self, hostname: str) -> bool:
        """Check if hostname is a private IP."""
        if not hostname:
            return False

        try:
            # Try to parse as IP address
            ip = ipaddress.ip_address(hostname)
            return ip.is_private
        except ValueError:
            # Not an IP address, check for localhost
            return hostname.lower() in ["localhost", "127.0.0.1", "0.0.0.0"]

    def check_rate_limit(self, identifier: str, limit: int, window: int) -> bool:
        """Check rate limit with sliding window algorithm."""
        current_time = time.time()

        if identifier not in self.rate_limit_storage:
            self.rate_limit_storage[identifier] = []

        # Clean old entries
        cutoff = current_time - window
        self.rate_limit_storage[identifier] = [
            timestamp for timestamp in self.rate_limit_storage[identifier] if timestamp > cutoff
        ]

        # Check limit
        if len(self.rate_limit_storage[identifier]) >= limit:
            return False

        # Add current request
        self.rate_limit_storage[identifier].append(current_time)
        return True

    def track_failed_attempt(self, identifier: str) -> int:
        """Track failed attempts for rate limiting."""
        current_time = time.time()

        if identifier not in self.failed_attempts:
            self.failed_attempts[identifier] = []

        # Clean old attempts (older than 1 hour)
        cutoff = current_time - 3600
        self.failed_attempts[identifier] = [
            timestamp for timestamp in self.failed_attempts[identifier] if timestamp > cutoff
        ]

        # Add current failed attempt
        self.failed_attempts[identifier].append(current_time)
        return len(self.failed_attempts[identifier])

    def should_block_ip(
        self, identifier: str, max_attempts: int = 5, block_duration: int = 3600
    ) -> bool:
        """Check if IP should be blocked."""
        current_time = time.time()

        if identifier in self.blocked_ips:
            block_time = self.blocked_ips[identifier]
            if current_time - block_time < block_duration:
                return True
            else:
                # Unblock IP
                del self.blocked_ips[identifier]

        # Check if should be blocked
        if identifier in self.failed_attempts:
            recent_attempts = [
                timestamp
                for timestamp in self.failed_attempts[identifier]
                if current_time - timestamp < 3600  # Last hour
            ]
            if len(recent_attempts) >= max_attempts:
                self.blocked_ips[identifier] = current_time
                logger.warning(f"Blocked IP {identifier} due to excessive failed attempts")
                return True

        return False

    def detect_suspicious_activity(self, request: Request) -> Dict[str, Any]:
        """Detect suspicious activity in request."""
        suspicious_indicators = []

        # Check User-Agent
        user_agent = request.headers.get("user-agent", "")
        if not user_agent or len(user_agent) < 10:
            suspicious_indicators.append("missing_or_short_user_agent")

        # Check for common bot patterns
        bot_indicators = ["bot", "crawler", "spider", "scraper"]
        if any(indicator in user_agent.lower() for indicator in bot_indicators):
            suspicious_indicators.append("bot_user_agent")

        # Check request frequency
        client_ip = self._get_client_ip(request)
        if not self.check_rate_limit(f"freq_{client_ip}", 100, 60):
            suspicious_indicators.append("high_request_frequency")

        # Check for unusual headers
        suspicious_headers = ["x-forwarded-for", "x-real-ip", "x-originating-ip"]
        for header in suspicious_headers:
            if header in request.headers:
                suspicious_indicators.append(f"suspicious_header_{header}")

        # Check request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 1000000:  # 1MB
            suspicious_indicators.append("large_request_body")

        return {
            "suspicious": len(suspicious_indicators) > 0,
            "indicators": suspicious_indicators,
            "risk_level": (
                "high"
                if len(suspicious_indicators) >= 3
                else "medium" if len(suspicious_indicators) >= 1 else "low"
            ),
        }

    def _get_client_ip(self, request: Request) -> str:
        """Get real client IP address."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fallback to client.host
        return request.client.host if request.client else "unknown"

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure token."""
        return secrets.token_urlsafe(length)

    def hash_sensitive_data(self, data: str, salt: str = None) -> tuple[str, str]:
        """Hash sensitive data with salt."""
        if salt is None:
            salt = secrets.token_hex(16)

        # Use PBKDF2 with HMAC-SHA256
        hashed = hashlib.pbkdf2_hmac("sha256", data.encode(), salt.encode(), 100000)
        return hashed.hex(), salt

    def verify_hmac(self, data: str, signature: str, secret: str) -> bool:
        """Verify HMAC signature."""
        expected_signature = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_signature, signature)

    def create_csrf_token(self) -> str:
        """Create CSRF token."""
        return secrets.token_urlsafe(32)

    def validate_csrf_token(self, token: str, session_token: str) -> bool:
        """Validate CSRF token."""
        # In production, store CSRF tokens in secure session storage
        # This is a simplified implementation
        return len(token) > 0 and len(token) < 100


# Global security hardening instance
security_hardening = SecurityHardening()


def security_middleware(request: Request, call_next):
    """Security middleware for FastAPI."""
    try:
        # Detect suspicious activity
        suspicious = security_hardening.detect_suspicious_activity(request)

        if suspicious["suspicious"]:
            logger.warning(
                f"Suspicious activity detected from {security_hardening._get_client_ip(request)}: "
                f"{suspicious['indicators']}"
            )

            # Block high-risk requests
            if suspicious["risk_level"] == "high":
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"error": "Request blocked due to suspicious activity"},
                )

        # Check if IP is blocked
        client_ip = security_hardening._get_client_ip(request)
        if security_hardening.should_block_ip(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"error": "IP temporarily blocked due to excessive failed attempts"},
            )

        # Process request
        response = call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response

    except Exception as e:
        logger.error(f"Security middleware error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Security check failed"},
        )


def require_input_validation(**field_validators):
    """Decorator for input validation."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Apply validation to function arguments
            for field, validator in field_validators.items():
                if field in kwargs:
                    value = kwargs[field]
                    if not validator(value):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid input for field: {field}",
                        )
            return func(*args, **kwargs)

        return wrapper

    return decorator
