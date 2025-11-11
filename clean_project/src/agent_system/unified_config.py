"""
Unified Configuration Management System
Consolidates all configuration into a single, well-structured system.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Core agent configuration."""

    max_cycles: int = 100
    max_concurrent_goals: int = 2
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
    blocked_file_paths: List[str] = field(
        default_factory=lambda: ["/etc", "/bin", "/usr", "/var/log"]
    )
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

    # Web search provider selection
    search_provider_order: List[str] = field(
        default_factory=lambda: ["serpapi", "bing", "google"]
    )
    disabled_search_providers: List[str] = field(default_factory=list)


@dataclass
class SecurityConfig:
    """Security configuration."""

    secret_key: str = "change-this-in-production"
    enable_input_validation: bool = True
    enable_resource_limits: bool = True
    max_memory_mb: int = 1024
    max_cpu_percent: int = 80
    enable_sandbox: bool = True
    allowed_file_extensions: List[str] = field(
        default_factory=lambda: [".txt", ".json", ".csv", ".py", ".md", ".log"]
    )


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


@dataclass
class DistributedConfig:
    """Distributed architecture configuration."""

    enabled: bool = False
    cluster_name: str = "agent-cluster"
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    service_namespace: str = "agent:services"
    message_namespace: str = "agent:queues"
    state_namespace: str = "agent:state"
    heartbeat_interval_seconds: int = 15
    service_ttl_seconds: int = 45
    visibility_timeout_seconds: int = 30
    queue_poll_interval_seconds: int = 1
    message_backend: str = "redis"
    discovery_backend: str = "redis"


@dataclass
class ProjectAnalysisConfig:
    """Configuration for large-project analysis subsystems."""

    ast_cache_entries: int = 2048
    ast_cache_max_mb: int = 512
    ast_cache_ttl_seconds: int = 3600
    memory_soft_limit_mb: int = 4096
    memory_hard_limit_mb: int = 6144
    memory_pressure_threshold: float = 0.85
    profiler_enabled: bool = True
    default_language: str = "python"
    max_parallel_parse_tasks: int = 8
    diff_sample_window: int = 200
    delta_change_ratio_threshold: float = 0.05


class UnifiedConfig:
    """Unified configuration system for the entire agent."""

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or ".agent_config.json"
        # Global strict mode toggle
        self.strict_mode: bool = os.getenv("STRICT_MODE", "false").lower() == "true"

        # Initialize configuration sections
        self.agent = AgentConfig()
        self.tools = ToolConfig()
        self.api = APIConfig()
        self.security = SecurityConfig()
        self.logging = LoggingConfig()
        self.database = DatabaseConfig()
        self.ai = AIConfig()
        self.distributed = DistributedConfig()
        self.project_analysis = ProjectAnalysisConfig()

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
            with open(config_path) as f:
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
        v = os.getenv("AGENT_MAX_CYCLES")
        if v is not None:
            self.agent.max_cycles = int(v)
        v = os.getenv("AGENT_MAX_CONCURRENT_GOALS")
        if v is not None:
            self.agent.max_concurrent_goals = int(v)
        v = os.getenv("AGENT_ENABLE_LEARNING")
        if v is not None:
            self.agent.enable_cross_session_learning = v.lower() == "true"

        # Tool settings
        v = os.getenv("TOOL_TIMEOUT")
        if v is not None:
            self.tools.timeout_seconds = int(v)
        v = os.getenv("TOOL_MAX_RETRIES")
        if v is not None:
            self.tools.max_retries = int(v)

        # API settings
        self.api.serpapi_key = os.getenv("SERPAPI_KEY")
        self.api.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.api.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.api.bing_search_key = os.getenv("BING_SEARCH_KEY")
        self.api.google_search_key = os.getenv("GOOGLE_SEARCH_KEY")
        v = os.getenv("SEARCH_PROVIDER_ORDER")
        if v is not None:
            self.api.search_provider_order = [p.strip().lower() for p in v.split(",") if p.strip()]
        v = os.getenv("DISABLED_SEARCH_PROVIDERS")
        if v is not None:
            self.api.disabled_search_providers = [p.strip().lower() for p in v.split(",") if p.strip()]

        # Security settings
        v = os.getenv("SECRET_KEY")
        if v is not None:
            self.security.secret_key = v
        v = os.getenv("ENABLE_SANDBOX")
        if v is not None:
            self.security.enable_sandbox = v.lower() == "true"

        # Logging settings
        v = os.getenv("LOG_LEVEL")
        if v is not None:
            self.logging.level = v

        # AI settings
        v = os.getenv("ENABLE_SEMANTIC_SIMILARITY")
        if v is not None:
            self.ai.enable_semantic_similarity = v.lower() == "true"

        # Distributed settings
        v = os.getenv("DISTRIBUTED_ENABLED")
        if v is not None:
            self.distributed.enabled = v.lower() == "true"
        v = os.getenv("STRICT_MODE")
        if v is not None:
            self.strict_mode = v.lower() == "true"
        v = os.getenv("DISTRIBUTED_CLUSTER_NAME")
        if v is not None:
            self.distributed.cluster_name = v
        v = os.getenv("DISTRIBUTED_NODE_ID")
        if v is not None:
            self.distributed.node_id = v
        v = os.getenv("DISTRIBUTED_SERVICE_NAMESPACE")
        if v is not None:
            self.distributed.service_namespace = v
        v = os.getenv("DISTRIBUTED_MESSAGE_NAMESPACE")
        if v is not None:
            self.distributed.message_namespace = v
        v = os.getenv("DISTRIBUTED_STATE_NAMESPACE")
        if v is not None:
            self.distributed.state_namespace = v
        v = os.getenv("DISTRIBUTED_HEARTBEAT_INTERVAL")
        if v is not None:
            self.distributed.heartbeat_interval_seconds = int(v)
        v = os.getenv("DISTRIBUTED_SERVICE_TTL")
        if v is not None:
            self.distributed.service_ttl_seconds = int(v)
        v = os.getenv("DISTRIBUTED_VISIBILITY_TIMEOUT")
        if v is not None:
            self.distributed.visibility_timeout_seconds = int(v)
        v = os.getenv("DISTRIBUTED_QUEUE_POLL_INTERVAL")
        if v is not None:
            self.distributed.queue_poll_interval_seconds = int(v)
        v = os.getenv("DISTRIBUTED_MESSAGE_BACKEND")
        if v is not None:
            self.distributed.message_backend = v
        v = os.getenv("DISTRIBUTED_DISCOVERY_BACKEND")
        if v is not None:
            self.distributed.discovery_backend = v

        # Project analysis settings
        v = os.getenv("PROJECT_ANALYSIS_AST_CACHE_ENTRIES")
        if v is not None:
            self.project_analysis.ast_cache_entries = int(v)
        v = os.getenv("PROJECT_ANALYSIS_AST_CACHE_MAX_MB")
        if v is not None:
            self.project_analysis.ast_cache_max_mb = int(v)
        v = os.getenv("PROJECT_ANALYSIS_AST_CACHE_TTL_SECONDS")
        if v is not None:
            self.project_analysis.ast_cache_ttl_seconds = int(v)
        v = os.getenv("PROJECT_ANALYSIS_MEMORY_SOFT_LIMIT_MB")
        if v is not None:
            self.project_analysis.memory_soft_limit_mb = int(v)
        v = os.getenv("PROJECT_ANALYSIS_MEMORY_HARD_LIMIT_MB")
        if v is not None:
            self.project_analysis.memory_hard_limit_mb = int(v)
        v = os.getenv("PROJECT_ANALYSIS_MEMORY_PRESSURE_THRESHOLD")
        if v is not None:
            self.project_analysis.memory_pressure_threshold = float(v)
        v = os.getenv("PROJECT_ANALYSIS_PROFILER_ENABLED")
        if v is not None:
            self.project_analysis.profiler_enabled = v.lower() == "true"
        v = os.getenv("PROJECT_ANALYSIS_DEFAULT_LANGUAGE")
        if v is not None:
            self.project_analysis.default_language = v
        v = os.getenv("PROJECT_ANALYSIS_MAX_PARALLEL_PARSE_TASKS")
        if v is not None:
            self.project_analysis.max_parallel_parse_tasks = int(v)
        v = os.getenv("PROJECT_ANALYSIS_DIFF_SAMPLE_WINDOW")
        if v is not None:
            self.project_analysis.diff_sample_window = int(v)
        v = os.getenv("PROJECT_ANALYSIS_DELTA_CHANGE_RATIO_THRESHOLD")
        if v is not None:
            self.project_analysis.delta_change_ratio_threshold = float(v)

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
            "distributed": self._dataclass_to_dict(self.distributed),
            "project_analysis": self._dataclass_to_dict(self.project_analysis),
        }

        try:
            with open(self.config_file, "w") as f:
                json.dump(config_data, f, indent=2, default=str)
            logger.info(f"Saved configuration to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

    def _dataclass_to_dict(self, obj: Any) -> Dict[str, Any]:
        """Convert dataclass to dictionary."""
        result: Dict[str, Any] = {}
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
        environment = os.getenv("ENVIRONMENT", "development").lower()
        if environment == "production":
            if self.security.secret_key == "change-this-in-production":
                raise ValueError("SECRET_KEY must be set via environment for production deployments")
            if len(self.security.secret_key) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters long in production")
        elif self.security.secret_key == "change-this-in-production":
            logger.warning("Using default SECRET_KEY outside production; set SECRET_KEY to avoid reuse.")

        # Validate AI config
        if not 0 <= self.ai.similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")

        # Validate distributed config
        if self.distributed.heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")
        if self.distributed.service_ttl_seconds <= 0:
            raise ValueError("service_ttl_seconds must be positive")
        if self.distributed.visibility_timeout_seconds <= 0:
            raise ValueError("visibility_timeout_seconds must be positive")
        if self.distributed.queue_poll_interval_seconds <= 0:
            raise ValueError("queue_poll_interval_seconds must be positive")

        # Validate project analysis config
        if self.project_analysis.ast_cache_entries <= 0:
            raise ValueError("ast_cache_entries must be positive")
        if self.project_analysis.ast_cache_max_mb <= 0:
            raise ValueError("ast_cache_max_mb must be positive")
        if self.project_analysis.memory_soft_limit_mb <= 0:
            raise ValueError("memory_soft_limit_mb must be positive")
        if self.project_analysis.memory_hard_limit_mb <= 0:
            raise ValueError("memory_hard_limit_mb must be positive")
        if (
            self.project_analysis.memory_pressure_threshold <= 0
            or self.project_analysis.memory_pressure_threshold >= 1
        ):
            raise ValueError("memory_pressure_threshold must be between 0 and 1")
        if self.project_analysis.max_parallel_parse_tasks <= 0:
            raise ValueError("max_parallel_parse_tasks must be positive")
        if self.project_analysis.diff_sample_window <= 0:
            raise ValueError("diff_sample_window must be positive")
        if not 0 < self.project_analysis.delta_change_ratio_threshold < 1:
            raise ValueError("delta_change_ratio_threshold must be between 0 and 1")

        # Critical environment validations
        if os.getenv("DISTRIBUTED_ENABLED", "false").lower() == "true":
            if not os.getenv("REDIS_URL") and not os.getenv("REDIS_HOST"):
                raise ValueError(
                    "Distributed mode requires Redis configuration (set REDIS_URL or REDIS_HOST/PORT)"
                )

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
                "enable_performance_monitoring": True,
            },
            "tools": {
                "timeout_seconds": 30,
                "max_retries": 3,
                "allow_shell_commands": False,
                "safe_file_paths": ["/tmp", ".", "./workspace"],
            },
            "api": {
                "serpapi_key": "your_serpapi_key_here",
                "bing_search_key": "your_bing_key_here",
                "google_search_key": "your_google_key_here",
                "openai_api_key": "your_openai_key_here",
                "default_llm_model": "gpt-3.5-turbo",
                "search_provider_order": ["serpapi", "bing", "google"],
                "disabled_search_providers": [],
            },
            "security": {
                "secret_key": "change-this-in-production",
                "enable_input_validation": True,
                "enable_sandbox": True,
            },
            "logging": {"level": "INFO", "file_path": "agent.log"},
            "ai": {
                "enable_semantic_similarity": True,
                "similarity_threshold": 0.5,
                "max_patterns": 1000,
            },
            "distributed": {
                "enabled": False,
                "cluster_name": "agent-cluster",
                "service_namespace": "agent:services",
                "message_namespace": "agent:queues",
                "state_namespace": "agent:state",
                "heartbeat_interval_seconds": 15,
                "service_ttl_seconds": 45,
                "visibility_timeout_seconds": 30,
                "queue_poll_interval_seconds": 1,
            },
            "project_analysis": {
                "ast_cache_entries": 2048,
                "ast_cache_max_mb": 512,
                "ast_cache_ttl_seconds": 3600,
                "memory_soft_limit_mb": 4096,
                "memory_hard_limit_mb": 6144,
                "memory_pressure_threshold": 0.85,
                "profiler_enabled": True,
                "default_language": "python",
                "max_parallel_parse_tasks": 8,
                "diff_sample_window": 200,
                "delta_change_ratio_threshold": 0.05,
            },
        }

        try:
            with open(self.config_file, "w") as f:
                json.dump(template, f, indent=2)
            logger.info(f"Created configuration template: {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to create configuration template: {e}")


# Global configuration instance
unified_config = UnifiedConfig()
