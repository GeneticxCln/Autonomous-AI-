"""
Unified Configuration Management System
Consolidates all configuration into a single, well-structured system.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Core agent configuration."""
    max_cycles: int = 100
    default_goal_priority: float = 0.5
    working_memory_size: int = 10
    learning_rate: float = 0.1
    confidence_threshold: float = 0.6
    enable_cross_session_learning: bool = True
    enable_performance_monitoring: bool = True
    enable_debug_tracking: bool = True


@dataclass
class ToolConfig:
    """Tool execution configuration."""
    timeout_seconds: int = 30
    max_retries: int = 3
    code_execution_timeout: int = 10
    safe_file_paths: List[str] = field(default_factory=lambda: ["/tmp", ".", "./workspace"])
    blocked_file_paths: List[str] = field(default_factory=lambda: ["/etc", "/bin", "/usr", "/var/log"])
    max_file_size_mb: int = 100
    allow_shell_commands: bool = False
    allow_network_access: bool = True


@dataclass
class APIConfig:
    """API provider configuration."""
    # Web Search APIs
    serpapi_key: Optional[str] = None
    bing_search_key: Optional[str] = None
    google_search_key: Optional[str] = None

    # LLM APIs
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    default_llm_model: str = "gpt-3.5-turbo"
    llm_timeout: int = 60
    max_tokens: int = 2000

    # Rate limiting
    requests_per_minute: int = 60
    api_key_rotation_days: int = 30


@dataclass
class SecurityConfig:
    """Security configuration."""
    secret_key: str = "change-this-in-production"
    enable_input_validation: bool = True
    enable_resource_limits: bool = True
    max_memory_mb: int = 1024
    max_cpu_percent: int = 80
    enable_sandbox: bool = True
    allowed_file_extensions: List[str] = field(default_factory=lambda: [
        ".txt", ".json", ".csv", ".py", ".md", ".log"
    ])


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "agent.log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    enable_console: bool = True
    enable_file: bool = True


@dataclass
class DatabaseConfig:
    """Database configuration."""
    url: str = "sqlite:///agent.db"
    pool_size: int = 5
    pool_timeout: int = 30
    enable_migrations: bool = True
    backup_enabled: bool = True
    backup_interval_hours: int = 24


@dataclass
class AIConfig:
    """AI and ML configuration."""
    # Semantic Similarity
    enable_semantic_similarity: bool = True
    sentence_transformer_model: str = "all-MiniLM-L6-v2"
    similarity_threshold: float = 0.5

    # Learning
    enable_meta_learning: bool = True
    learning_decay_rate: float = 0.05
    max_patterns: int = 1000
    confidence_decay_days: int = 30

    # Performance Monitoring
    performance_alert_threshold: float = 0.7
    monitoring_interval_seconds: int = 60
    trend_analysis_hours: int = 24

    # Debug & Explainability
    max_decisions_tracked: int = 1000
    decision_explanation_enabled: bool = True
    reasoning_chain_depth: int = 5


class UnifiedConfig:
    """Unified configuration system for the entire agent."""

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or ".agent_config.json"

        # Initialize configuration sections
        self.agent = AgentConfig()
        self.tools = ToolConfig()
        self.api = APIConfig()
        self.security = SecurityConfig()
        self.logging = LoggingConfig()
        self.database = DatabaseConfig()
        self.ai = AIConfig()

        # Load configuration
        self.load_from_file()
        self.load_from_env()

        # Validate configuration
        self.validate()

    def load_from_file(self) -> None:
        """Load configuration from file."""
        config_path = Path(self.config_file)
        if not config_path.exists():
            logger.info(f"Configuration file {self.config_file} not found, using defaults")
            return

        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            # Load each section
            for section_name, section_data in config_data.items():
                if hasattr(self, section_name):
                    section = getattr(self, section_name)
                    for key, value in section_data.items():
                        if hasattr(section, key):
                            setattr(section, key, value)

            logger.info(f"Loaded configuration from {self.config_file}")

        except Exception as e:
            logger.error(f"Failed to load configuration from {self.config_file}: {e}")

    def load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # Agent settings
        if os.getenv("AGENT_MAX_CYCLES"):
            self.agent.max_cycles = int(os.getenv("AGENT_MAX_CYCLES"))
        if os.getenv("AGENT_ENABLE_LEARNING"):
            self.agent.enable_cross_session_learning = os.getenv("AGENT_ENABLE_LEARNING").lower() == "true"

        # Tool settings
        if os.getenv("TOOL_TIMEOUT"):
            self.tools.timeout_seconds = int(os.getenv("TOOL_TIMEOUT"))
        if os.getenv("TOOL_MAX_RETRIES"):
            self.tools.max_retries = int(os.getenv("TOOL_MAX_RETRIES"))

        # API settings
        self.api.serpapi_key = os.getenv("SERPAPI_KEY")
        self.api.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.api.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

        # Security settings
        if os.getenv("SECRET_KEY"):
            self.security.secret_key = os.getenv("SECRET_KEY")
        if os.getenv("ENABLE_SANDBOX"):
            self.security.enable_sandbox = os.getenv("ENABLE_SANDBOX").lower() == "true"

        # Logging settings
        if os.getenv("LOG_LEVEL"):
            self.logging.level = os.getenv("LOG_LEVEL")

        # AI settings
        if os.getenv("ENABLE_SEMANTIC_SIMILARITY"):
            self.ai.enable_semantic_similarity = os.getenv("ENABLE_SEMANTIC_SIMILARITY").lower() == "true"

    def save_to_file(self) -> None:
        """Save current configuration to file."""
        config_data = {
            "agent": self._dataclass_to_dict(self.agent),
            "tools": self._dataclass_to_dict(self.tools),
            "api": self._dataclass_to_dict(self.api),
            "security": self._dataclass_to_dict(self.security),
            "logging": self._dataclass_to_dict(self.logging),
            "database": self._dataclass_to_dict(self.database),
            "ai": self._dataclass_to_dict(self.ai),
        }

        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
            logger.info(f"Saved configuration to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

    def _dataclass_to_dict(self, obj) -> Dict[str, Any]:
        """Convert dataclass to dictionary."""
        result = {}
        for field_name, field_value in obj.__dataclass_fields__.items():
            value = getattr(obj, field_name)
            if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
                result[field_name] = value
            else:
                result[field_name] = str(value)
        return result

    def validate(self) -> None:
        """Validate configuration values."""
        # Validate agent config
        if self.agent.max_cycles <= 0:
            raise ValueError("max_cycles must be positive")
        if not 0 <= self.agent.default_goal_priority <= 1:
            raise ValueError("default_goal_priority must be between 0 and 1")

        # Validate tool config
        if self.tools.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.tools.max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        # Validate security config
        if self.security.max_memory_mb <= 0:
            raise ValueError("max_memory_mb must be positive")

        # Validate AI config
        if not 0 <= self.ai.similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a specific provider."""
        provider_map = {
            "serpapi": self.api.serpapi_key,
            "bing": self.api.bing_search_key,
            "google": self.api.google_search_key,
            "openai": self.api.openai_api_key,
            "anthropic": self.api.anthropic_api_key,
        }
        return provider_map.get(provider.lower())

    def is_api_configured(self, provider: str) -> bool:
        """Check if API provider is configured."""
        return self.get_api_key(provider) is not None

    def get_configured_providers(self) -> List[str]:
        """Get list of configured API providers."""
        providers = []
        if self.api.serpapi_key:
            providers.append("serpapi")
        if self.api.bing_search_key:
            providers.append("bing")
        if self.api.google_search_key:
            providers.append("google")
        if self.api.openai_api_key:
            providers.append("openai")
        if self.api.anthropic_api_key:
            providers.append("anthropic")
        return providers

    def create_config_template(self) -> None:
        """Create a configuration template file."""
        template = {
            "agent": {
                "max_cycles": 100,
                "default_goal_priority": 0.5,
                "working_memory_size": 10,
                "enable_cross_session_learning": True,
                "enable_performance_monitoring": True
            },
            "tools": {
                "timeout_seconds": 30,
                "max_retries": 3,
                "allow_shell_commands": False,
                "safe_file_paths": ["/tmp", ".", "./workspace"]
            },
            "api": {
                "serpapi_key": "your_serpapi_key_here",
                "openai_api_key": "your_openai_key_here",
                "default_llm_model": "gpt-3.5-turbo"
            },
            "security": {
                "secret_key": "change-this-in-production",
                "enable_input_validation": True,
                "enable_sandbox": True
            },
            "logging": {
                "level": "INFO",
                "file_path": "agent.log"
            },
            "ai": {
                "enable_semantic_similarity": True,
                "similarity_threshold": 0.5,
                "max_patterns": 1000
            }
        }

        try:
            with open(self.config_file, 'w') as f:
                json.dump(template, f, indent=2)
            logger.info(f"Created configuration template: {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to create configuration template: {e}")


# Global configuration instance
unified_config = UnifiedConfig()