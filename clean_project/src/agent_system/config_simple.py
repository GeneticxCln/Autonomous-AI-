"""
Configuration management for the autonomous agent.

This module now proxies to unified_config while preserving the legacy
`settings` interface used across the codebase.
"""

from __future__ import annotations

import os
from typing import Optional

from .unified_config import unified_config


class Settings:
    """Application settings proxying to unified_config."""

    def __init__(self):
        # Core agent settings
        self.MAX_CYCLES = unified_config.agent.max_cycles
        self.LOG_LEVEL = unified_config.logging.level
        self.DEFAULT_GOAL_PRIORITY = unified_config.agent.default_goal_priority

        # Tool execution settings
        self.TOOL_TIMEOUT = unified_config.tools.timeout_seconds
        self.MAX_RETRIES = unified_config.tools.max_retries
        self.CODE_EXECUTION_TIMEOUT = unified_config.tools.code_execution_timeout

        # File system settings
        self.ALLOWED_FILE_PATHS = unified_config.tools.safe_file_paths
        self.BLOCKED_FILE_PATHS = unified_config.tools.blocked_file_paths

        # Web search API settings
        self.SERPAPI_KEY = unified_config.api.serpapi_key
        self.BING_SEARCH_KEY = unified_config.api.bing_search_key
        self.GOOGLE_SEARCH_KEY = unified_config.api.google_search_key

        # LLM API settings
        self.OPENAI_API_KEY = unified_config.api.openai_api_key
        self.ANTHROPIC_API_KEY = unified_config.api.anthropic_api_key
        self.DEFAULT_LLM_MODEL = unified_config.api.default_llm_model

        # Database settings
        self.DATABASE_URL = unified_config.database.url
        self.DATABASE_POOL_SIZE = unified_config.database.pool_size

        # Vector database for memory
        self.VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")

        # Security settings
        self.SECRET_KEY = unified_config.security.secret_key
        self.API_KEY_ROTATION_DAYS = unified_config.api.api_key_rotation_days

        # Rate limiting
        self.REQUESTS_PER_MINUTE = unified_config.api.requests_per_minute

        # Sandboxing for code execution
        self.USE_DOCKER_SANDBOX = os.getenv("USE_DOCKER_SANDBOX", "false").lower() == "true"
        self.DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", "python:3.9-slim")
        self.MEMORY_LIMIT = os.getenv("MEMORY_LIMIT", "512m")

        # Tool selection
        self.USE_REAL_TOOLS = os.getenv("USE_REAL_TOOLS", "true").lower() == "true"

        # Terminal-only mode (no web search/network tools)
        self.TERMINAL_ONLY = os.getenv("TERMINAL_ONLY", "true").lower() == "true"


# Global settings instance
settings = Settings()


def get_api_key(service: str) -> Optional[str]:
    """Get API key for a specific service."""
    return unified_config.get_api_key(service)


def validate_file_path(filepath: str) -> bool:
    """Validate that a file path is allowed."""
    import os.path

    abs_path = os.path.abspath(filepath)

    # Check against blocked paths
    for blocked in unified_config.tools.blocked_file_paths:
        if abs_path.startswith(os.path.abspath(blocked)):
            return False

    # Check against allowed paths (if specified)
    if unified_config.tools.safe_file_paths:
        for allowed in unified_config.tools.safe_file_paths:
            if abs_path.startswith(os.path.abspath(allowed)):
                return True
        return False

    return True  # If no restrictions specified, allow
