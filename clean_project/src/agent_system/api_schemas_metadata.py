"""
API Schemas for Plugin Metadata Provider System
Extended schemas for metadata provider endpoints
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MetadataProviderType(str, Enum):
    """Types of metadata providers."""
    HTTP_JSON = "http_json"
    GIT_REPOSITORY = "git_repository"
    LOCAL_DIRECTORY = "local_directory"
    PLUGIN_REGISTRY = "plugin_registry"


class PluginMetadataSource(str, Enum):
    """Source of plugin metadata."""
    MARKETPLACE = "marketplace"
    LOCAL = "local"
    CUSTOM = "custom"
    ENTERPRISE = "enterprise"


class MetadataValidationStatus(str, Enum):
    """Status of metadata validation."""
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    UNKNOWN = "unknown"


class PluginMetadataRequest(BaseModel):
    """Request model for plugin metadata operations."""
    
    name: str = Field(..., min_length=1, max_length=100, description="Plugin name")
    version: Optional[str] = Field(None, max_length=50, description="Plugin version")
    source_types: Optional[List[PluginMetadataSource]] = Field(None, description="Filter by source types")


class PluginDiscoveryRequest(BaseModel):
    """Request model for plugin discovery."""
    
    query: Optional[str] = Field(None, max_length=200, description="Search query")
    source_types: Optional[List[PluginMetadataSource]] = Field(None, description="Filter by source types")
    categories: Optional[List[str]] = Field(None, max_length=50, description="Filter by categories")
    tags: Optional[List[str]] = Field(None, max_length=20, description="Filter by tags")
    min_rating: Optional[float] = Field(None, ge=0.0, le=5.0, description="Minimum rating")
    trusted_only: bool = Field(False, description="Only show trusted sources")
    include_invalid: bool = Field(False, description="Include invalid metadata")
    limit: int = Field(100, ge=1, le=1000, description="Maximum results to return")


class MetadataProviderCreate(BaseModel):
    """Request model for creating metadata provider."""
    
    name: str = Field(..., min_length=1, max_length=100, description="Provider name")
    provider_type: MetadataProviderType = Field(..., description="Provider type")
    description: Optional[str] = Field(None, max_length=500, description="Provider description")
    base_url: Optional[str] = Field(None, max_length=500, description="Base URL for HTTP providers")
    repository_url: Optional[str] = Field(None, max_length=500, description="Repository URL for Git providers")
    local_path: Optional[str] = Field(None, max_length=500, description="Local path for directory providers")
    
    # Authentication
    auth_token: Optional[str] = Field(None, max_length=500, description="Authentication token")
    api_key: Optional[str] = Field(None, max_length=500, description="API key")
    username: Optional[str] = Field(None, max_length=100, description="Username")
    password: Optional[str] = Field(None, max_length=100, description="Password")
    
    # Performance settings
    cache_enabled: bool = Field(True, description="Enable caching")
    cache_ttl: int = Field(3600, ge=0, description="Cache TTL in seconds")
    rate_limit: Optional[int] = Field(None, ge=1, description="Rate limit per minute")
    
    # Filtering
    filters: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific filters")
    search_terms: List[str] = Field(default_factory=list, description="Default search terms")
    
    # Metadata processing
    custom_parser: Optional[str] = Field(None, max_length=200, description="Custom parser class")
    schema_validation: bool = Field(True, description="Enable schema validation")
    
    # Behavior
    enabled: bool = Field(True, description="Enable provider")
    priority: int = Field(50, ge=1, le=100, description="Provider priority")


class MetadataProviderUpdate(BaseModel):
    """Request model for updating metadata provider."""
    
    description: Optional[str] = Field(None, max_length=500, description="Provider description")
    
    # Authentication
    auth_token: Optional[str] = Field(None, max_length=500, description="Authentication token")
    api_key: Optional[str] = Field(None, max_length=500, description="API key")
    username: Optional[str] = Field(None, max_length=100, description="Username")
    password: Optional[str] = Field(None, max_length=100, description="Password")
    
    # Performance settings
    cache_enabled: Optional[bool] = Field(None, description="Enable caching")
    cache_ttl: Optional[int] = Field(None, ge=0, description="Cache TTL in seconds")
    rate_limit: Optional[int] = Field(None, ge=1, description="Rate limit per minute")
    
    # Filtering
    filters: Optional[Dict[str, Any]] = Field(None, description="Provider-specific filters")
    search_terms: Optional[List[str]] = Field(None, description="Default search terms")
    
    # Metadata processing
    custom_parser: Optional[str] = Field(None, max_length=200, description="Custom parser class")
    schema_validation: Optional[bool] = Field(None, description="Enable schema validation")
    
    # Behavior
    enabled: Optional[bool] = Field(None, description="Enable provider")
    priority: Optional[int] = Field(None, ge=1, le=100, description="Provider priority")


class EnhancedPluginMetadata(BaseModel):
    """Enhanced plugin metadata response model."""
    
    # Core identification
    name: str
    version: str
    unique_id: Optional[str] = None
    
    # Basic information
    display_name: Optional[str] = None
    description: str
    short_description: Optional[str] = None
    author: str
    maintainer: Optional[str] = None
    homepage: Optional[str] = None
    repository_url: Optional[str] = None
    documentation_url: Optional[str] = None
    
    # Classification and tags
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    license: Optional[str] = None
    
    # Version and compatibility
    compatibility: Dict[str, Any] = Field(default_factory=dict)
    requirements: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    peer_dependencies: List[str] = Field(default_factory=list)
    
    # Entry points and configuration
    entry_point: str
    configuration_schema: Optional[Dict[str, Any]] = None
    api_schema: Optional[Dict[str, Any]] = None
    
    # Security and permissions
    permissions: List[str] = Field(default_factory=list)
    security_requirements: List[str] = Field(default_factory=list)
    trusted_source: bool = False
    
    # Metadata source information
    source_type: PluginMetadataSource
    provider_type: Optional[MetadataProviderType] = None
    provider_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Status and lifecycle
    status: str = "available"
    stability: str = "stable"
    maturity_level: str = "production"
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_validated: Optional[datetime] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    
    # Validation
    validation_status: MetadataValidationStatus = MetadataValidationStatus.UNKNOWN
    validation_errors: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    
    # Computed fields
    download_url: Optional[str] = None
    icon_url: Optional[str] = None
    rating: float = 0.0
    download_count: int = 0
    
    class Config:
        use_enum_values = True


class MetadataProviderResponse(BaseModel):
    """Response model for metadata provider information."""
    
    id: str
    name: str
    provider_type: MetadataProviderType
    description: Optional[str] = None
    
    # Configuration
    base_url: Optional[str] = None
    repository_url: Optional[str] = None
    local_path: Optional[str] = None
    
    # Status
    enabled: bool
    priority: int
    
    # Performance and caching
    cache_enabled: bool
    cache_ttl: int
    rate_limit: Optional[int] = None
    
    # Sync information
    last_sync: Optional[datetime] = None
    sync_errors: List[str] = Field(default_factory=list)
    
    # Statistics
    total_plugins: int = 0
    sync_success_count: int = 0
    sync_error_count: int = 0
    last_sync_duration: Optional[int] = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    class Config:
        use_enum_values = True


class MetadataProviderInfo(BaseModel):
    """Information about metadata providers."""
    
    total_providers: int
    enabled_providers: int
    providers: Dict[str, Any]
    global_settings: Dict[str, Any]


class PluginInstallRequest(BaseModel):
    """Request model for plugin installation."""
    
    name: str = Field(..., min_length=1, max_length=100, description="Plugin name")
    version: Optional[str] = Field(None, max_length=50, description="Plugin version")
    source: Optional[str] = Field(None, max_length=500, description="Custom source URL")
    force: bool = Field(False, description="Force installation even if already installed")
    validate_dependencies: bool = Field(True, description="Validate dependencies before installation")


class PluginInstallResponse(BaseModel):
    """Response model for plugin installation."""
    
    success: bool
    plugin_name: str
    version: Optional[str] = None
    message: str
    download_url: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    installation_id: Optional[str] = None


class CacheManagementRequest(BaseModel):
    """Request model for cache management."""
    
    action: str = Field(..., regex="^(clear|prune|refresh)$", description="Cache action")
    provider_name: Optional[str] = Field(None, description="Specific provider to target")
    plugin_name: Optional[str] = Field(None, description="Specific plugin to target")
    older_than_hours: Optional[int] = Field(None, ge=1, description="Age threshold for pruning")


class CacheStatistics(BaseModel):
    """Cache statistics response."""
    
    total_entries: int
    memory_entries: int
    database_entries: int
    average_age_hours: float
    hit_rate: float
    cache_size_mb: float
    oldest_entry: Optional[datetime] = None
    newest_entry: Optional[datetime] = None
    provider_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    """Validation report for plugins."""
    
    plugin_name: str
    version: str
    validation_status: MetadataValidationStatus
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    compatibility_score: Optional[float] = None
    security_score: Optional[float] = None
    last_validated: datetime


class BulkOperationRequest(BaseModel):
    """Request model for bulk operations."""
    
    operation: str = Field(..., regex="^(validate|refresh|install)$", description="Operation type")
    plugin_names: List[str] = Field(..., min_items=1, max_items=100, description="Plugin names")
    options: Dict[str, Any] = Field(default_factory=dict, description="Operation options")


class BulkOperationResponse(BaseModel):
    """Response model for bulk operations."""
    
    operation: str
    total_plugins: int
    successful: int
    failed: int
    results: Dict[str, Any]
    errors: Dict[str, List[str]]
    duration_seconds: float


class SystemCompatibilityCheck(BaseModel):
    """Request model for system compatibility check."""
    
    python_version: Optional[str] = Field(None, description="Python version")
    os: Optional[str] = Field(None, description="Operating system")
    architecture: Optional[str] = Field(None, description="System architecture")
    available_memory_mb: Optional[int] = Field(None, description="Available memory in MB")
    disk_space_mb: Optional[int] = Field(None, description="Available disk space in MB")


class CompatibilityReport(BaseModel):
    """Response model for compatibility report."""
    
    overall_score: float
    compatible_plugins: List[str]
    incompatible_plugins: List[str]
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=dict)
    system_requirements: Dict[str, Any] = Field(default_factory=dict)
    missing_dependencies: Dict[str, List[str]] = Field(default_factory=dict)


# Request/Response models for health monitoring
class ProviderHealthStatus(BaseModel):
    """Health status for metadata provider."""
    
    provider_name: str
    healthy: bool
    response_time_ms: Optional[float] = None
    last_success: Optional[datetime] = None
    error_message: Optional[str] = None
    consecutive_failures: int = 0


class HealthCheckResponse(BaseModel):
    """Response model for health checks."""
    
    overall_healthy: bool
    timestamp: datetime
    providers: List[ProviderHealthStatus]
    total_response_time_ms: float
    cache_effectiveness: float
    system_load: float


# Extended API response models
class MetadataAPIResponse(BaseModel):
    """Extended API response with metadata provider information."""
    
    success: bool
    message: str
    timestamp: float
    data: Optional[Any] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    provider_info: Optional[Dict[str, Any]] = None