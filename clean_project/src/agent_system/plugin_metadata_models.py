"""
Plugin Metadata Provider Architecture
Enhanced plugin metadata models with support for multiple provider types
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, cast, runtime_checkable
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .plugin_marketplace import PluginMetadata, PluginStatus

logger = logging.getLogger(__name__)


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


# Enhanced plugin metadata models using Pydantic
class EnhancedPluginMetadata(BaseModel):
    """Enhanced plugin metadata with extended schema."""
    
    # Core identification
    name: str = Field(..., max_length=100)
    version: str = Field(..., max_length=50)
    unique_id: Optional[str] = Field(None, max_length=200)
    
    # Basic information
    display_name: Optional[str] = Field(None, max_length=100)
    description: str = Field(..., min_length=1, max_length=2000)
    short_description: Optional[str] = Field(None, max_length=500)
    author: str = Field(..., min_length=1, max_length=100)
    maintainer: Optional[str] = Field(None, max_length=100)
    homepage: Optional[str] = Field(None, max_length=500)
    repository_url: Optional[str] = Field(None, max_length=500)
    documentation_url: Optional[str] = Field(None, max_length=500)
    
    # Classification and tags
    category: Optional[str] = Field(None, max_length=50)
    tags: List[str] = Field(default_factory=list, max_length=20)
    keywords: List[str] = Field(default_factory=list, max_length=20)
    license: Optional[str] = Field(None, max_length=50)
    
    # Version and compatibility
    compatibility: Dict[str, Any] = Field(default_factory=dict)
    requirements: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    peer_dependencies: List[str] = Field(default_factory=list)
    
    # Entry points and configuration
    entry_point: str = Field(..., min_length=1, max_length=200)
    configuration_schema: Optional[Dict[str, Any]] = None
    api_schema: Optional[Dict[str, Any]] = None
    
    # Security and permissions
    permissions: List[str] = Field(default_factory=list)
    security_requirements: List[str] = Field(default_factory=list)
    trusted_source: bool = Field(default=False)
    
    # Metadata source information
    source_type: PluginMetadataSource = Field(default=PluginMetadataSource.MARKETPLACE)
    provider_type: Optional[MetadataProviderType] = None
    provider_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Status and lifecycle
    status: PluginStatus = Field(default=PluginStatus.AVAILABLE)
    stability: str = Field(default="stable", max_length=20)
    maturity_level: str = Field(default="production", max_length=20)
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_validated: Optional[datetime] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    
    # Validation
    validation_status: MetadataValidationStatus = Field(default=MetadataValidationStatus.UNKNOWN)
    validation_errors: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    
    # Note: Do not enforce strict constraints at model construction time; validation occurs in validate_metadata()
    
    def to_legacy_metadata(self) -> PluginMetadata:
        """Convert to legacy PluginMetadata format."""
        return PluginMetadata(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            dependencies=self.dependencies,
            entry_point=self.entry_point,
            repository_url=self.repository_url,
            status=self.status,
            installed_at=None,
            metadata=self.metadata,
        )
    
    def get_download_url(self) -> Optional[str]:
        """Get download URL for the plugin."""
        raw = self.metadata.get("download_url")
        if isinstance(raw, str):
            return raw
        if self.repository_url:
            # Generate GitHub/GitLab download URL
            if "github.com" in self.repository_url:
                repo_path = self.repository_url.split("github.com/")[-1]
                return f"https://github.com/{repo_path}/archive/refs/heads/main.zip"
            elif "gitlab.com" in self.repository_url:
                repo_path = self.repository_url.split("gitlab.com/")[-1]
                return f"https://gitlab.com/{repo_path}/-/archive/main/archive.zip"
        return None
    
    def get_icon_url(self) -> Optional[str]:
        """Get plugin icon URL."""
        raw = self.metadata.get("icon_url") or self.metadata.get("logo_url")
        return raw if isinstance(raw, str) else None
    
    def get_rating(self) -> float:
        """Get plugin rating (0.0 to 5.0)."""
        return float(self.metadata.get("rating", 0.0))
    
    def get_download_count(self) -> int:
        """Get download count."""
        return int(self.metadata.get("download_count", 0))
    
    def is_compatible_with(self, system_info: Dict[str, Any]) -> bool:
        """Check if plugin is compatible with system."""
        compatibility = self.compatibility
        
        # Check Python version compatibility (require current >= required)
        if "python_version" in compatibility:
            required_version = str(compatibility["python_version"]).strip()
            current_version = str(system_info.get("python_version", "")).strip()

            def _parse(v: str) -> tuple[int, int, int]:
                parts = []
                num = ""
                for ch in v:
                    if ch.isdigit() or ch == ".":
                        num += ch
                    else:
                        break
                for p in (num.split(".") if num else []):
                    if p.isdigit():
                        parts.append(int(p))
                while len(parts) < 3:
                    parts.append(0)
                return parts[0], parts[1], parts[2]

            if _parse(current_version) < _parse(required_version):
                return False
        
        # Check OS compatibility
        if "os" in compatibility:
            required_os = compatibility["os"]
            current_os = system_info.get("os", "")
            if current_os not in required_os:
                return False
        
        return True
    
    def validate_metadata(self) -> MetadataValidationStatus:
        """Validate plugin metadata completeness and correctness."""
        errors = []
        warnings = []
        
        # Required fields validation
        required_fields = ["name", "version", "description", "author", "entry_point"]
        for field in required_fields:
            if not getattr(self, field):
                errors.append(f"Required field '{field}' is missing or empty")
        
        # Name format validation
        if self.name:
            simplified = self.name.replace("-", "").replace("_", "")
            if not simplified.isalnum():
                warnings.append(
                    "Plugin name should contain only alphanumeric characters, hyphens, and underscores"
                )
        
        # Version format validation
        try:
            import re
            if not re.match(r"^\d+\.\d+\.\d+(-[\w\.-]+)?$", self.version or ""):
                raise ValueError(
                    "Version must follow semantic versioning (e.g., 1.2.3 or 1.2.3-beta.1)"
                )
        except ValueError as e:
            errors.append(f"Version format invalid: {e}")
        
        # Entry point validation
        if self.entry_point and ":" not in self.entry_point:
            warnings.append("Entry point should be in format 'module:ClassName'")
        
        # URL validation
        url_fields = ["homepage", "repository_url", "documentation_url"]
        for field in url_fields:
            url = getattr(self, field)
            if url:
                try:
                    result = urlparse(url)
                    if not result.scheme or not result.netloc:
                        warnings.append(f"Invalid URL format for {field}: {url}")
                except Exception:
                    warnings.append(f"Could not parse URL for {field}: {url}")
        
        # Dependencies validation
        for dep in self.dependencies:
            if dep.count(">") > 1 or dep.count("<") > 1:
                warnings.append(f"Complex dependency version specifier: {dep}")
        
        self.validation_errors = errors
        self.validation_warnings = warnings
        
        if errors:
            self.validation_status = MetadataValidationStatus.INVALID
        elif warnings:
            self.validation_status = MetadataValidationStatus.WARNING
        else:
            self.validation_status = MetadataValidationStatus.VALID
        
        self.last_validated = datetime.now(UTC)
        return self.validation_status


class MetadataProviderConfig(BaseModel):
    """Configuration for metadata providers."""
    
    model_config = ConfigDict(extra="allow")
    provider_type: MetadataProviderType
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    
    # Provider-specific configuration
    base_url: Optional[str] = Field(None, max_length=500)
    repository_url: Optional[str] = Field(None, max_length=500)
    local_path: Optional[str] = Field(None, max_length=500)
    
    # Authentication and access
    auth_token: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = Field(None, max_length=500)
    username: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, max_length=100)
    
    # Caching and performance
    cache_enabled: bool = Field(default=True)
    cache_ttl: int = Field(default=3600, ge=0)  # Cache TTL in seconds
    rate_limit: Optional[int] = Field(None, ge=1)  # Requests per minute
    
    # Filtering and search
    filters: Dict[str, Any] = Field(default_factory=dict)
    search_terms: List[str] = Field(default_factory=list)
    
    # Metadata processing
    custom_parser: Optional[str] = Field(None, max_length=200)
    schema_validation: bool = Field(default=True)
    
    # Status
    enabled: bool = Field(default=True)
    priority: int = Field(default=50, ge=1, le=100)
    last_sync: Optional[datetime] = None
    sync_errors: List[str] = Field(default_factory=list)
    


# Protocol for metadata providers
@runtime_checkable
class MetadataProvider(Protocol):
    """Protocol for metadata providers."""
    
    async def discover_plugins(self, query: Optional[str] = None) -> List[EnhancedPluginMetadata]:
        """Discover plugins from provider."""
        ...
    
    async def get_plugin_metadata(self, plugin_name: str, version: Optional[str] = None) -> Optional[EnhancedPluginMetadata]:
        """Get metadata for specific plugin."""
        ...
    
    async def validate_provider_config(self) -> bool:
        """Validate provider configuration."""
        ...
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information."""
        ...


# SQLAlchemy models for metadata storage
class MetadataBase(DeclarativeBase):
    pass


class MetadataProviderModel(MetadataBase):
    """Database model for metadata providers."""
    
    __tablename__ = "metadata_providers"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    provider_type: Mapped[MetadataProviderType] = mapped_column(SQLEnum(MetadataProviderType), nullable=False)
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    last_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    # Sync statistics
    total_plugins: Mapped[int] = mapped_column(Integer, default=0)
    sync_success_count: Mapped[int] = mapped_column(Integer, default=0)
    sync_error_count: Mapped[int] = mapped_column(Integer, default=0)
    last_sync_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Duration in seconds
    sync_errors: Mapped[List[str]] = mapped_column(JSON, default=list)


class PluginMetadataCache(MetadataBase):
    """Database model for plugin metadata cache."""
    
    __tablename__ = "plugin_metadata_cache"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plugin_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(36), nullable=False)
    
    # Cached metadata
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    provider_type: Mapped[MetadataProviderType] = mapped_column(SQLEnum(MetadataProviderType), nullable=False)
    source_type: Mapped[PluginMetadataSource] = mapped_column(SQLEnum(PluginMetadataSource), nullable=False)
    
    # Validation and status
    validation_status: Mapped[MetadataValidationStatus] = mapped_column(
        SQLEnum(MetadataValidationStatus), default=MetadataValidationStatus.UNKNOWN
    )
    validation_errors: Mapped[List[str]] = mapped_column(JSON, default=list)
    validation_warnings: Mapped[List[str]] = mapped_column(JSON, default=list)
    
    # Timestamps
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_accessed: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Indexes
    __table_args__ = (
        {"extend_existing": True},
    )
    
    def get_metadata(self) -> EnhancedPluginMetadata:
        """Get parsed metadata from cache."""
        try:
            return cast(EnhancedPluginMetadata, EnhancedPluginMetadata.model_validate_json(self.metadata_json))
        except Exception as e:
            logger.error(f"Failed to parse cached metadata for {self.plugin_name}:{self.version}: {e}")
            raise
    
    def update_access(self) -> None:
        """Update access statistics."""
        self.last_accessed = datetime.now(UTC)
        self.access_count += 1


# Exception classes for metadata providers
class MetadataProviderError(Exception):
    """Base exception for metadata provider errors."""
    pass


class MetadataProviderConfigError(MetadataProviderError):
    """Exception for invalid provider configuration."""
    pass


class MetadataProviderNetworkError(MetadataProviderError):
    """Exception for network-related provider errors."""
    pass


class MetadataProviderAuthError(MetadataProviderError):
    """Exception for authentication errors."""
    pass


class MetadataProviderValidationError(MetadataProviderError):
    """Exception for metadata validation errors."""
    pass


# Utility functions
def create_metadata_id(plugin_name: str, version: str, provider_id: str) -> str:
    """Create a unique metadata ID."""
    import hashlib
    content = f"{plugin_name}:{version}:{provider_id}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def parse_metadata_from_dict(data: Dict[str, Any], source_type: PluginMetadataSource = PluginMetadataSource.CUSTOM) -> EnhancedPluginMetadata:
    """Parse metadata from dictionary format."""
    # Handle legacy metadata format
    if "entry_point" not in data and "class" in data:
        data["entry_point"] = data["class"]
    
    # Set default values
    data.setdefault("source_type", source_type)
    data.setdefault("status", PluginStatus.AVAILABLE)
    data.setdefault("validation_status", MetadataValidationStatus.UNKNOWN)
    
    try:
        return cast(EnhancedPluginMetadata, EnhancedPluginMetadata.model_validate(data))
    except Exception as e:
        raise MetadataProviderValidationError(f"Failed to parse metadata: {e}")


def validate_metadata_schema(metadata: EnhancedPluginMetadata, schema: Dict[str, Any]) -> List[str]:
    """Validate metadata against a schema."""
    # This is a basic implementation - can be enhanced with JSON Schema validation
    errors = []
    
    required_fields = schema.get("required", [])
    for field in required_fields:
        if not hasattr(metadata, field) or not getattr(metadata, field):
            errors.append(f"Required field '{field}' is missing")
    
    return errors


# Default schemas for different plugin types
DEFAULT_PLUGIN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["name", "version", "description", "author", "entry_point"],
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 100},
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+(-[\\w\\.-]+)?$"},
        "description": {"type": "string", "minLength": 1, "maxLength": 2000},
        "author": {"type": "string", "minLength": 1, "maxLength": 100},
        "entry_point": {"type": "string", "minLength": 1, "maxLength": 200},
    }
}

ENTERPRISE_PLUGIN_SCHEMA: Dict[str, Any] = {
    **DEFAULT_PLUGIN_SCHEMA,
    "required": list(DEFAULT_PLUGIN_SCHEMA["required"]) + ["security_requirements", "trusted_source"],
    "properties": {
        **DEFAULT_PLUGIN_SCHEMA["properties"],
        "security_requirements": {"type": "array", "items": {"type": "string"}},
        "trusted_source": {"type": "boolean"},
    }
}
