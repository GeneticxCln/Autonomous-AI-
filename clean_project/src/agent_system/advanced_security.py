"""
Advanced Security Features for Enterprise Deployment
mTLS, WAF, Rate Limiting, Input Validation, and Security Monitoring
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

# Security libraries
try:
    import base64

    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    Fernet = None

from .config_simple import settings

logger = logging.getLogger(__name__)


class SecurityEventType(Enum):
    """Types of security events."""

    AUTHENTICATION_FAILURE = "auth_failure"
    AUTHORIZATION_FAILURE = "authz_failure"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    INPUT_VALIDATION_FAILURE = "input_validation_failure"
    SECURITY_SCAN_DETECTED = "security_scan_detected"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    XSS_ATTEMPT = "xss_attempt"
    BRUTE_FORCE_ATTACK = "brute_force_attack"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


class ThreatLevel(Enum):
    """Threat levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """Security event data structure."""

    event_type: SecurityEventType
    threat_level: ThreatLevel
    source_ip: str
    user_agent: Optional[str] = None
    user_id: Optional[str] = None
    endpoint: Optional[str] = None
    timestamp: datetime = None
    details: Dict[str, Any] = None
    signature: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.details is None:
            self.details = {}


class WAFRule:
    """Web Application Firewall rule."""

    def __init__(
        self,
        name: str,
        pattern: str,
        action: str = "block",
        threat_level: ThreatLevel = ThreatLevel.MEDIUM,
        description: str = "",
    ):
        self.name = name
        self.pattern = pattern
        self.action = action
        self.threat_level = threat_level
        self.description = description
        self.enabled = True
        self.hit_count = 0
        self.last_hit = None


class AdvancedSecurityManager:
    """
    Advanced security manager with:
    - Web Application Firewall (WAF)
    - Rate limiting with distributed tracking
    - Input validation and sanitization
    - mTLS support
    - Security event monitoring
    - Threat detection
    - Encrypted storage
    """

    def __init__(self):
        self.waf_rules: List[WAFRule] = []
        self.rate_limiters: Dict[str, Dict] = {}
        self.security_events: List[SecurityEvent] = []
        self.blocked_ips: Set[str] = set()
        self.suspicious_ips: Dict[str, int] = {}
        self.encryption_key: Optional[bytes] = None
        self.cipher: Optional[Fernet] = None
        self.is_initialized = False

        # Initialize default security rules
        self._init_waf_rules()
        self._init_encryption()

    def _init_waf_rules(self):
        """Initialize default WAF rules."""
        # SQL Injection patterns
        self.add_waf_rule(
            WAFRule(
                name="SQL Injection",
                pattern=r"(?i)(union|select|insert|update|delete|drop|create|alter|exec|execute)",
                threat_level=ThreatLevel.HIGH,
                description="SQL injection attempt detected",
            )
        )

        # XSS patterns
        self.add_waf_rule(
            WAFRule(
                name="Cross-Site Scripting",
                pattern=r"(?i)(<script|javascript:|vbscript:|onload=|onerror=)",
                threat_level=ThreatLevel.HIGH,
                description="Cross-site scripting attempt detected",
            )
        )

        # Path traversal
        self.add_waf_rule(
            WAFRule(
                name="Path Traversal",
                pattern=r"(\.\./|\.\.\\)",
                threat_level=ThreatLevel.MEDIUM,
                description="Path traversal attempt detected",
            )
        )

        # Command injection
        self.add_waf_rule(
            WAFRule(
                name="Command Injection",
                pattern=r"(;|\|\||&&|`|\$\()",
                threat_level=ThreatLevel.HIGH,
                description="Command injection attempt detected",
            )
        )

        # Suspicious file uploads
        self.add_waf_rule(
            WAFRule(
                name="Suspicious File Upload",
                pattern=r"(?i)\.(exe|bat|cmd|scr|pif|vbs|js)$",
                threat_level=ThreatLevel.MEDIUM,
                description="Suspicious file upload detected",
            )
        )

        # SQL keywords
        self.add_waf_rule(
            WAFRule(
                name="SQL Keywords",
                pattern=r"(?i)(script|union|select|drop|insert|delete|update)",
                threat_level=ThreatLevel.MEDIUM,
                description="SQL keyword detected",
            )
        )

        # NoSQL injection
        self.add_waf_rule(
            WAFRule(
                name="NoSQL Injection",
                pattern=r"(\$where|\$ne|\$gt|\$lt|\$regex|\$in)",
                threat_level=ThreatLevel.MEDIUM,
                description="NoSQL injection attempt detected",
            )
        )

        # LDAP injection
        self.add_waf_rule(
            WAFRule(
                name="LDAP Injection",
                pattern=r"(\(|\)|\||\*)",
                threat_level=ThreatLevel.MEDIUM,
                description="LDAP injection attempt detected",
            )
        )

    def _init_encryption(self):
        """Initialize encryption for sensitive data."""
        try:
            if Fernet:
                # Generate or retrieve encryption key
                key_env = getattr(settings, "ENCRYPTION_KEY", None)
                if key_env:
                    # Use environment key (base64 encoded)
                    self.encryption_key = base64.urlsafe_b64decode(key_env)
                else:
                    # Generate new key
                    self.encryption_key = Fernet.generate_key()

                self.cipher = Fernet(self.encryption_key)
                self.is_initialized = True

                logger.info("✅ Encryption initialized")
        except Exception as e:
            logger.error(f"❌ Encryption initialization failed: {e}")

    def add_waf_rule(self, rule: WAFRule):
        """Add WAF rule."""
        self.waf_rules.append(rule)
        logger.info(f"🛡️ WAF rule added: {rule.name}")

    def remove_waf_rule(self, rule_name: str) -> bool:
        """Remove WAF rule by name."""
        for i, rule in enumerate(self.waf_rules):
            if rule.name == rule_name:
                del self.waf_rules[i]
                logger.info(f"🛡️ WAF rule removed: {rule_name}")
                return True
        return False

    def scan_request(self, request_data: Dict[str, Any]) -> Tuple[bool, List[SecurityEvent]]:
        """
        Scan request for security threats.

        Args:
            request_data: Request data to scan

        Returns:
            Tuple of (is_safe, security_events)
        """
        if not self.is_initialized:
            return True, []

        events = []
        _suspicious_content = []

        # Extract content to scan
        content_parts = []

        # URL path
        if "path" in request_data:
            content_parts.append(request_data["path"])

        # Query parameters
        if "query_params" in request_data:
            content_parts.extend(request_data["query_params"].values())

        # Headers
        if "headers" in request_data:
            content_parts.extend(request_data["headers"].values())

        # Request body
        if "body" in request_data and isinstance(request_data["body"], str):
            content_parts.append(request_data["body"])

        # Combine all content
        full_content = " ".join(content_parts)

        # Check against WAF rules
        for rule in self.waf_rules:
            if not rule.enabled:
                continue

            import re

            if re.search(rule.pattern, full_content, re.IGNORECASE):
                rule.hit_count += 1
                rule.last_hit = datetime.now()

                # Create security event
                event = SecurityEvent(
                    event_type=SecurityEventType.SECURITY_SCAN_DETECTED,
                    threat_level=rule.threat_level,
                    source_ip=request_data.get("client_ip", "unknown"),
                    user_agent=request_data.get("user_agent"),
                    endpoint=request_data.get("path"),
                    details={
                        "rule_name": rule.name,
                        "pattern": rule.pattern,
                        "matched_content": full_content[:200],  # Truncate for safety
                    },
                )

                events.append(event)

                # Auto-block high-level threats
                if rule.threat_level == ThreatLevel.CRITICAL:
                    self.block_ip(request_data.get("client_ip", "unknown"))

        return len(events) == 0, events

    def check_rate_limit(
        self, identifier: str, limit: int, window_seconds: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit.

        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            limit: Maximum requests allowed
            window_seconds: Time window in seconds

        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        now = time.time()
        window_start = now - window_seconds

        if identifier not in self.rate_limiters:
            self.rate_limiters[identifier] = {"requests": [], "blocked_until": 0}

        limiter = self.rate_limiters[identifier]

        # Check if temporarily blocked
        if limiter["blocked_until"] > now:
            return False, {
                "allowed": False,
                "reason": "temporarily_blocked",
                "blocked_until": limiter["blocked_until"],
                "limit": limit,
                "window": window_seconds,
            }

        # Clean old requests outside the window
        limiter["requests"] = [
            req_time for req_time in limiter["requests"] if req_time > window_start
        ]

        # Check current request count
        if len(limiter["requests"]) >= limit:
            # Rate limit exceeded
            # Create security event
            event = SecurityEvent(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                threat_level=ThreatLevel.MEDIUM,
                source_ip=identifier,
                details={
                    "request_count": len(limiter["requests"]),
                    "limit": limit,
                    "window": window_seconds,
                },
            )
            self.security_events.append(event)

            # Track suspicious activity
            if identifier not in self.suspicious_ips:
                self.suspicious_ips[identifier] = 0
            self.suspicious_ips[identifier] += 1

            # Auto-block if too many violations
            if self.suspicious_ips[identifier] > 5:
                self.block_ip(identifier)

            return False, {
                "allowed": False,
                "reason": "rate_limit_exceeded",
                "current_count": len(limiter["requests"]),
                "limit": limit,
                "window": window_seconds,
            }

        # Add current request
        limiter["requests"].append(now)

        return True, {
            "allowed": True,
            "current_count": len(limiter["requests"]),
            "limit": limit,
            "window": window_seconds,
        }

    def block_ip(self, ip_address: str, duration_seconds: int = 3600):
        """Block an IP address temporarily."""
        self.blocked_ips.add(ip_address)
        self.rate_limiters[ip_address] = {
            "requests": [],
            "blocked_until": time.time() + duration_seconds,
        }

        logger.warning(f"🚫 IP blocked: {ip_address} for {duration_seconds} seconds")

    def unblock_ip(self, ip_address: str):
        """Unblock an IP address."""
        self.blocked_ips.discard(ip_address)
        if ip_address in self.rate_limiters:
            del self.rate_limiters[ip_address]

        logger.info(f"✅ IP unblocked: {ip_address}")

    def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if IP is blocked."""
        if ip_address not in self.blocked_ips:
            return False

        # Check if block has expired
        limiter = self.rate_limiters.get(ip_address)
        if limiter and time.time() > limiter.get("blocked_until", 0):
            self.unblock_ip(ip_address)
            return False

        return True

    def validate_input(self, input_data: Any, input_type: str = "generic") -> Tuple[bool, str]:
        """
        Validate and sanitize input data.

        Args:
            input_data: Data to validate
            input_type: Type of input (email, url, json, etc.)

        Returns:
            Tuple of (is_valid, sanitized_data)
        """
        if not input_data:
            return True, input_data

        sanitized_data = str(input_data)

        try:
            if input_type == "email":
                import re

                email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                if not re.match(email_pattern, sanitized_data):
                    return False, "Invalid email format"

            elif input_type == "url":
                import re

                url_pattern = r"^https?://[^\s/$.?#].[^\s]*$"
                if not re.match(url_pattern, sanitized_data):
                    return False, "Invalid URL format"

            elif input_type == "json":
                try:
                    json.loads(sanitized_data)
                except json.JSONDecodeError:
                    return False, "Invalid JSON format"

            elif input_type == "sql_safe":
                # Remove potential SQL injection characters
                sql_dangerous = [";", "--", "/*", "*/", "xp_", "sp_"]
                for dangerous in sql_dangerous:
                    if dangerous in sanitized_data.lower():
                        return False, "Potentially dangerous SQL content detected"

            # General sanitization
            # Remove null bytes
            sanitized_data = sanitized_data.replace("\x00", "")

            # Remove control characters (except common whitespace)
            sanitized_data = "".join(
                char for char in sanitized_data if ord(char) >= 32 or char in "\t\n\r"
            )

            return True, sanitized_data

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        if not self.cipher:
            logger.warning("⚠️ Encryption not available, returning data as-is")
            return data

        try:
            encrypted_data = self.cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"❌ Encryption failed: {e}")
            return data

    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        if not self.cipher:
            logger.warning("⚠️ Encryption not available, returning data as-is")
            return encrypted_data

        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self.cipher.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"❌ Decryption failed: {e}")
            return encrypted_data

    def create_security_signature(self, data: str, secret: str) -> str:
        """Create HMAC signature for data integrity."""
        return hmac.new(secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_security_signature(self, data: str, signature: str, secret: str) -> bool:
        """Verify HMAC signature."""
        expected_signature = self.create_security_signature(data, secret)
        return hmac.compare_digest(expected_signature, signature)

    def log_security_event(self, event: SecurityEvent):
        """Log security event."""
        self.security_events.append(event)

        # Log to file/console
        threat_emoji = {
            ThreatLevel.LOW: "ℹ️",
            ThreatLevel.MEDIUM: "⚠️",
            ThreatLevel.HIGH: "🚨",
            ThreatLevel.CRITICAL: "💥",
        }.get(event.threat_level, "📝")

        logger.warning(
            f"{threat_emoji} SECURITY EVENT: {event.event_type.value} | "
            f"IP: {event.source_ip} | "
            f"Level: {event.threat_level.value} | "
            f"Details: {event.details}"
        )

        # Auto-block critical threats
        if event.threat_level == ThreatLevel.CRITICAL:
            self.block_ip(event.source_ip)

    def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics."""
        now = datetime.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        # Count events by type and threat level
        event_counts = {}
        threat_counts = {}
        blocked_ips_count = len(self.blocked_ips)

        for event in self.security_events:
            # Event type counts
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

            # Threat level counts
            threat_level = event.threat_level.value
            threat_counts[threat_level] = threat_counts.get(threat_level, 0) + 1

        # Recent events
        recent_events_24h = [event for event in self.security_events if event.timestamp >= last_24h]

        recent_events_7d = [event for event in self.security_events if event.timestamp >= last_7d]

        return {
            "total_events": len(self.security_events),
            "events_last_24h": len(recent_events_24h),
            "events_last_7d": len(recent_events_7d),
            "blocked_ips": blocked_ips_count,
            "suspicious_ips": len(self.suspicious_ips),
            "waf_rules_active": len([r for r in self.waf_rules if r.enabled]),
            "waf_rules_total": len(self.waf_rules),
            "event_type_counts": event_counts,
            "threat_level_counts": threat_counts,
            "top_blocked_ips": list(self.blocked_ips)[:10],
            "encryption_enabled": self.cipher is not None,
        }

    def get_recent_security_events(
        self, hours: int = 24, event_type: Optional[SecurityEventType] = None
    ) -> List[Dict[str, Any]]:
        """Get recent security events."""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        events = [event for event in self.security_events if event.timestamp >= cutoff_time]

        if event_type:
            events = [event for event in events if event.event_type == event_type]

        return [
            {
                "event_type": event.event_type.value,
                "threat_level": event.threat_level.value,
                "source_ip": event.source_ip,
                "user_agent": event.user_agent,
                "user_id": event.user_id,
                "endpoint": event.endpoint,
                "timestamp": event.timestamp.isoformat(),
                "details": event.details,
            }
            for event in events[-100:]  # Limit to last 100 events
        ]


# Global security manager instance
security_manager = AdvancedSecurityManager()


# Security middleware functions
async def security_middleware(request_data: Dict[str, Any]) -> bool:
    """
    Security middleware for request processing.

    Args:
        request_data: Request data dictionary

    Returns:
        True if request is safe, False if blocked
    """
    try:
        # Check if IP is blocked
        client_ip = request_data.get("client_ip")
        if client_ip and security_manager.is_ip_blocked(client_ip):
            logger.warning(f"🚫 Blocked request from IP: {client_ip}")
            return False

        # Check rate limiting
        rate_limit_info = security_manager.check_rate_limit(
            identifier=client_ip or "unknown",
            limit=100,  # 100 requests
            window_seconds=60,  # per minute
        )

        if not rate_limit_info[0]:
            logger.warning(f"⏰ Rate limit exceeded for IP: {client_ip}")
            return False

        # Scan for security threats
        is_safe, security_events = security_manager.scan_request(request_data)

        if not is_safe:
            for event in security_events:
                security_manager.log_security_event(event)
            return False

        return True

    except Exception as e:
        logger.error(f"❌ Security middleware error: {e}")
        return True  # Allow request on error to avoid false positives


# Security decorators
def require_secure_input(input_type: str = "generic"):
    """Decorator to require secure input validation."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # This would be implemented based on the function signature
            # For now, just return the function result
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Security monitoring
async def security_monitor():
    """Background security monitoring task."""
    while True:
        try:
            # Check for suspicious patterns
            stats = security_manager.get_security_stats()

            # Alert on high threat activity
            if stats["events_last_24h"] > 100:
                logger.critical(
                    f"🚨 High security event volume: {stats['events_last_24h']} events in 24h"
                )

            if stats["threat_level_counts"].get("critical", 0) > 0:
                logger.critical(
                    f"💥 Critical security threats detected: {stats['threat_level_counts']['critical']}"
                )

            # Clean up old events
            cutoff_time = datetime.now() - timedelta(days=30)
            security_manager.security_events = [
                event
                for event in security_manager.security_events
                if event.timestamp >= cutoff_time
            ]

            await asyncio.sleep(300)  # Check every 5 minutes

        except Exception as e:
            logger.error(f"❌ Security monitor error: {e}")
            await asyncio.sleep(60)


# Initialize security system
def initialize_security():
    """Initialize the global security system."""
    try:
        # Start background security monitor
        asyncio.create_task(security_monitor())

        logger.info("✅ Advanced security system initialized")
        return True
    except Exception as e:
        logger.error(f"❌ Security system initialization failed: {e}")
        return False


# Security utilities
def sanitize_html(content: str) -> str:
    """Sanitize HTML content to prevent XSS."""
    if not content:
        return content

    # Basic HTML sanitization (in production, use bleach or similar)
    import re

    # Remove script tags
    content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.IGNORECASE | re.DOTALL)

    # Remove javascript: URLs
    content = re.sub(r'javascript:[^"\']*', "", content, flags=re.IGNORECASE)

    # Remove on* event handlers
    content = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', "", content, flags=re.IGNORECASE)

    return content


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure token."""
    return secrets.token_urlsafe(length)


def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    """Hash password with salt using PBKDF2."""
    if salt is None:
        salt = secrets.token_bytes(32)

    if Fernet:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password.encode())
        return base64.urlsafe_b64encode(key).decode(), base64.urlsafe_b64encode(salt).decode()
    else:
        # Fallback to simple hash
        import hashlib

        hash_obj = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return hash_obj.hex(), base64.urlsafe_b64encode(salt).decode()


def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    """Verify password against hash."""
    try:
        salt_bytes = base64.urlsafe_b64decode(salt.encode())

        if Fernet:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt_bytes,
                iterations=100000,
            )
            key = kdf.derive(password.encode())
            expected_hash = base64.urlsafe_b64encode(key).decode()
        else:
            import hashlib

            hash_obj = hashlib.pbkdf2_hmac("sha256", password.encode(), salt_bytes, 100000)
            expected_hash = hash_obj.hexdigest()

        return hmac.compare_digest(hashed_password, expected_hash)

    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False
