"""
Configuration management for the autonomous agent.
"""
from __future__ import annotations

import os
from typing import Optional
try:
    from pydantic import BaseSettings, Field
except ImportError:
    from pydantic_settings import BaseSettings
    from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Core agent settings
    MAX_CYCLES: int = Field(default=100, description="Maximum number of agent cycles")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    DEFAULT_GOAL_PRIORITY: float = Field(default=0.5, description="Default goal priority")
    
    # Tool execution settings
    TOOL_TIMEOUT: int = Field(default=30, description="Tool execution timeout in seconds")
    MAX_RETRIES: int = Field(default=3, description="Maximum retry attempts for failed tools")
    CODE_EXECUTION_TIMEOUT: int = Field(default=10, description="Code execution timeout")
    
    # File system settings
    ALLOWED_FILE_PATHS: list[str] = Field(
        default_factory=lambda: ["/tmp", ".", "./workspace"],
        description="Allowed file system paths for file operations"
    )
    BLOCKED_FILE_PATHS: list[str] = Field(
        default_factory=lambda: ["/etc", "/bin", "/usr", "/var/log"],
        description="Blocked file system paths for security"
    )
    
    # Web search API settings
    SERPAPI_KEY: Optional[str] = Field(default=None, description="SerpAPI key for web search")
    BING_SEARCH_KEY: Optional[str] = Field(default=None, description="Bing Search API key")
    GOOGLE_SEARCH_KEY: Optional[str] = Field(default=None, description="Google Search API key")
    
    # LLM API settings
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API key")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API key")
    DEFAULT_LLM_MODEL: str = Field(default="gpt-3.5-turbo", description="Default LLM model")
    
    # Database settings
    DATABASE_URL: str = Field(default="sqlite:///agent.db", description="Database connection string")
    DATABASE_POOL_SIZE: int = Field(default=5, description="Database connection pool size")
    
    # Vector database for memory
    VECTOR_DB_PATH: str = Field(default="./vector_db", description="Vector database path")
    
    # Security settings
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production", description="Secret key for encryption")
    API_KEY_ROTATION_DAYS: int = Field(default=30, description="API key rotation period in days")
    
    # Rate limiting
    REQUESTS_PER_MINUTE: int = Field(default=60, description="Rate limit for API requests per minute")
    
    # Sandboxing for code execution
    USE_DOCKER_SANDBOX: bool = Field(default=False, description="Use Docker for code execution sandbox")
    DOCKER_IMAGE: str = Field(default="python:3.9-slim", description="Docker image for sandbox")
    MEMORY_LIMIT: str = Field(default="512m", description="Memory limit for sandbox")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_api_key(service: str) -> Optional[str]:
    """Get API key for a specific service."""
    key_mapping = {
        "serpapi": settings.SERPAPI_KEY,
        "bing": settings.BING_SEARCH_KEY,
        "google": settings.GOOGLE_SEARCH_KEY,
        "openai": settings.OPENAI_API_KEY,
        "anthropic": settings.ANTHROPIC_API_KEY,
    }
    return key_mapping.get(service.lower())


def validate_file_path(filepath: str) -> bool:
    """Validate that a file path is allowed."""
    import os.path
    
    # Convert to absolute path
    abs_path = os.path.abspath(filepath)
    
    # Check against blocked paths
    for blocked in settings.BLOCKED_FILE_PATHS:
        if abs_path.startswith(os.path.abspath(blocked)):
            return False
    
    # Check against allowed paths (if specified)
    if settings.ALLOWED_FILE_PATHS:
        for allowed in settings.ALLOWED_FILE_PATHS:
            if abs_path.startswith(os.path.abspath(allowed)):
                return True
        return False
    
    return True  # If no restrictions specified, allow