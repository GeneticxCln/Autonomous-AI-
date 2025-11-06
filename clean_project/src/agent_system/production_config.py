"""
Production Configuration Management
Secure handling of environment variables and secrets
"""
from __future__ import annotations

import os
import secrets
import string
from pathlib import Path
from typing import Optional, List
from functools import lru_cache

# Try to import python-dotenv, fallback if not available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use os.environ directly


class ConfigError(Exception):
    """Configuration error."""
    pass


class ProductionConfig:
    """Production-ready configuration management."""

    def __init__(self):
        self.environment = self.get_env("ENVIRONMENT", "development")
        self.debug = self.get_env("API_DEBUG", "false").lower() == "true"

        # Database Configuration
        self.database_url = self.get_env("DATABASE_URL", "sqlite:///./agent_enterprise.db")

        # JWT Security (CRITICAL)
        self.jwt_secret_key = self._get_jwt_secret()
        self.jwt_algorithm = self.get_env("JWT_ALGORITHM", "HS256")
        self.jwt_access_token_expire_minutes = int(self.get_env("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        self.jwt_refresh_token_expire_days = int(self.get_env("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))

        # API Configuration
        self.api_host = self.get_env("API_HOST", "127.0.0.1")
        self.api_port = int(self.get_env("API_PORT", "8000"))
        self.api_workers = int(self.get_env("API_WORKERS", "1"))

        # Security Settings
        self.rate_limit_requests = int(self.get_env("RATE_LIMIT_REQUESTS", "100"))
        self.rate_limit_window = int(self.get_env("RATE_LIMIT_WINDOW", "60"))
        self.max_login_attempts = int(self.get_env("MAX_LOGIN_ATTEMPTS", "5"))
        self.account_lockout_duration = int(self.get_env("ACCOUNT_LOCKOUT_DURATION", "30"))

        # CORS Configuration
        cors_origins = self.get_env("CORS_ORIGINS", "*")
        if cors_origins == "*":
            self.cors_origins = ["*"]
        else:
            self.cors_origins = [origin.strip() for origin in cors_origins.split(",")]

        # Security Features
        self.secure_headers = self.get_env("SECURE_HEADERS", "true").lower() == "true"
        self.enable_https = self.get_env("ENABLE_HTTPS", "false").lower() == "true"

        # Logging
        self.log_level = self.get_env("LOG_LEVEL", "INFO")

        # Performance
        self.enable_rate_limiting = self.get_env("ENABLE_RATE_LIMITING", "true").lower() == "true"
        self.enable_caching = self.get_env("ENABLE_CACHING", "true").lower() == "true"

        # Audit & Monitoring
        self.enable_audit_logging = self.get_env("ENABLE_AUDIT_LOGGING", "true").lower() == "true"
        self.audit_log_retention_days = int(self.get_env("AUDIT_LOG_RETENTION_DAYS", "90"))

        # Email Configuration
        self.smtp_host = self.get_env("SMTP_HOST", "")
        self.smtp_port = int(self.get_env("SMTP_PORT", "587"))
        self.smtp_username = self.get_env("SMTP_USERNAME", "")
        self.smtp_password = self.get_env("SMTP_PASSWORD", "")
        self.smtp_use_tls = self.get_env("SMTP_USE_TLS", "true").lower() == "true"

        # Redis Configuration (for production)
        self.redis_url = self.get_env("REDIS_URL", "")

        # Monitoring
        self.enable_metrics = self.get_env("ENABLE_METRICS", "true").lower() == "true"
        self.metrics_port = int(self.get_env("METRICS_PORT", "9090"))

        # Backup Configuration
        self.backup_enabled = self.get_env("BACKUP_ENABLED", "false").lower() == "true"
        self.backup_schedule = self.get_env("BACKUP_SCHEDULE", "")
        self.backup_retention_days = int(self.get_env("BACKUP_RETENTION_DAYS", "30"))

        # Validate critical settings
        self._validate_config()

    def _get_env(self, key: str, default: str = None) -> str:
        """Get environment variable with validation."""
        value = os.getenv(key, default)
        if value is None:
            raise ConfigError(f"Required environment variable {key} is not set")
        return value

    def get_env(self, key: str, default: str = None) -> str:
        """Get environment variable safely."""
        return os.getenv(key, default)

    def _get_jwt_secret(self) -> str:
        """Get JWT secret with validation and generation fallback."""
        secret = os.getenv("JWT_SECRET_KEY")

        if not secret:
            # Generate a secure secret if not provided
            if self.environment == "production":
                raise ConfigError(
                    "JWT_SECRET_KEY must be set in production environment. "
                    "Generate a secure secret: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            else:
                # Generate for development
                secret = secrets.token_urlsafe(32)
                print(f"⚠️  Generated development JWT secret. Set JWT_SECRET_KEY for production.")

        # Validate secret strength
        if len(secret) < 32:
            raise ConfigError("JWT_SECRET_KEY must be at least 32 characters long")

        return secret

    def _validate_config(self):
        """Validate critical configuration settings."""
        errors = []

        # Production-specific validations
        if self.environment == "production":
            if self.debug:
                errors.append("API_DEBUG must be false in production")

            if self.jwt_secret_key == "your-super-secret-jwt-key-change-in-production":
                errors.append("Default JWT secret must be changed for production")

            if self.database_url.startswith("sqlite:///"):
                errors.append("Use PostgreSQL or another production database in production")

            if self.cors_origins == ["*"]:
                errors.append("CORS_ORIGINS must be configured for production")

            if not self.secure_headers:
                errors.append("SECURE_HEADERS must be enabled in production")

        # Critical validations for all environments
        if self.max_login_attempts < 3:
            errors.append("MAX_LOGIN_ATTEMPTS should be at least 3")

        if self.account_lockout_duration < 5:
            errors.append("ACCOUNT_LOCKOUT_DURATION should be at least 5 minutes")

        if self.rate_limit_requests < 10:
            errors.append("RATE_LIMIT_REQUESTS should be at least 10")

        if errors:
            raise ConfigError("Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors))

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment.lower() == "testing"

    def get_database_url(self) -> str:
        """Get database URL with environment-specific settings."""
        if self.database_url.startswith("postgresql://") or self.database_url.startswith("postgres://"):
            # Add connection pool settings for PostgreSQL
            url = self.database_url.rstrip("/")
            if "?" not in url:
                url += "?"
            else:
                url += "&"

            url += f"pool_size=20&max_overflow=30&pool_pre_ping=True&pool_recycle=3600"
            return url

        return self.database_url

    def get_cors_origins(self) -> List[str]:
        """Get CORS origins with security restrictions."""
        if self.is_production() and self.cors_origins == ["*"]:
            raise ConfigError("CORS_ORIGINS must be explicitly configured for production")

        return self.cors_origins

    def should_use_redis(self) -> bool:
        """Check if Redis should be used for session storage."""
        return bool(self.redis_url) and self.is_production()

    def __str__(self) -> str:
        """String representation (without sensitive data)."""
        return (
            f"ProductionConfig(environment={self.environment}, "
            f"debug={self.debug}, "
            f"database={'configured' if self.database_url else 'not configured'}, "
            f"jwt={'configured' if self.jwt_secret_key != 'default' else 'default'}, "
            f"cors_origins={len(self.cors_origins)} origins, "
            f"redis={'configured' if self.redis_url else 'not configured'})"
        )


@lru_cache()
def get_config() -> ProductionConfig:
    """Get cached configuration instance."""
    return ProductionConfig()


# Global configuration instance
config = get_config()


def validate_production_config():
    """Validate that production configuration is secure."""
    if config.is_production():
        print("🔐 Validating production configuration...")

        # Check critical security settings
        checks = [
            (not config.debug, "Debug mode is disabled"),
            (config.jwt_secret_key != "your-super-secret-jwt-key-change-in-production", "JWT secret is configured"),
            (config.secure_headers, "Security headers are enabled"),
            (config.enable_audit_logging, "Audit logging is enabled"),
            (config.max_login_attempts >= 3, "Login attempt limit is set"),
            (config.account_lockout_duration >= 5, "Account lockout duration is set"),
        ]

        for check, description in checks:
            if check:
                print(f"✅ {description}")
            else:
                print(f"❌ {description}")
                raise ConfigError(f"Production configuration validation failed: {description}")
    else:
        print(f"🌍 Running in {config.environment} mode - production validations skipped")


if __name__ == "__main__":
    # Example usage and validation
    try:
        config = get_config()
        print(f"✅ Configuration loaded successfully")
        print(f"   Environment: {config.environment}")
        print(f"   Database: {config.database_url}")
        print(f"   JWT Configured: {config.jwt_secret_key[:20]}...")
        print(f"   CORS Origins: {config.cors_origins}")

        # Validate for production
        validate_production_config()

    except ConfigError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)