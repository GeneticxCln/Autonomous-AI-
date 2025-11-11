"""
Metadata Provider Configuration Management
Unified management system for all plugin metadata providers
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .auth_models import SecurityContext
from .git_repository_provider import create_git_repository_provider
from .http_json_provider import create_http_json_provider
from .plugin_metadata_models import (
    EnhancedPluginMetadata,
    MetadataProvider,
    MetadataProviderConfig,
    MetadataProviderError,
    MetadataProviderModel,
    MetadataProviderType,
    PluginMetadataCache,
    PluginMetadataSource,
    create_metadata_id,
)

logger = logging.getLogger(__name__)


class MetadataProviderManager:
    """Manager for all plugin metadata providers."""
    
    def __init__(self, config_path: Optional[str] = None, database_url: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else Path("plugin_providers.json")
        self.database_url = database_url or "sqlite:///./plugin_metadata.db"
        
        # Provider registry
        self._providers: Dict[str, MetadataProvider] = {}
        self._provider_configs: Dict[str, MetadataProviderConfig] = {}
        
        # Database setup
        self._engine: Engine | None = None
        self._SessionLocal: sessionmaker[Session] | None = None
        
        # Caching
        self._metadata_cache: Dict[str, EnhancedPluginMetadata] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        
        # Configuration
        self._config_loaded = False
        self._enable_caching = True
        self._cache_ttl = 3600  # 1 hour default
        self._parallel_discovery = True
        self._max_workers = 5
        
        # RBAC integration
        self._user_permissions_cache: Dict[str, List[str]] = {}
        self._security_context: Optional[SecurityContext] = None
    
    async def initialize(self) -> None:
        """Initialize the metadata provider manager."""
        try:
            # Initialize database
            await self._initialize_database()
            
            # Load configuration
            await self._load_configuration()
            
            # Initialize providers
            await self._initialize_providers()
            
            logger.info("Metadata provider manager initialized successfully")
        
        except Exception as e:
            logger.error(f"Failed to initialize metadata provider manager: {e}")
            raise
    
    async def _initialize_database(self) -> None:
        """Initialize metadata database."""
        try:
            self._engine = create_engine(self.database_url, echo=False)
            
            # Create tables
            from .plugin_metadata_models import MetadataBase
            MetadataBase.metadata.create_all(bind=self._engine)
            
            self._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
            
            logger.debug("Metadata database initialized")
        
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    async def _load_configuration(self) -> None:
        """Load provider configuration from file and database."""
        try:
            # Load from file
            if self.config_path.exists():
                config_data = json.loads(self.config_path.read_text())
                await self._load_config_from_dict(config_data)
            
            # Load from database
            await self._load_config_from_database()
            
            # Apply global settings
            global_config = await self._get_global_config()
            if global_config:
                self._enable_caching = global_config.get("cache_enabled", True)
                self._cache_ttl = global_config.get("cache_ttl", 3600)
                self._parallel_discovery = global_config.get("parallel_discovery", True)
                self._max_workers = global_config.get("max_workers", 5)
            
            self._config_loaded = True
            logger.info(f"Loaded configuration for {len(self._provider_configs)} providers")
        
        except Exception as e:
            logger.error(f"Configuration loading failed: {e}")
            raise MetadataProviderError(f"Configuration loading failed: {e}")
    
    async def _load_config_from_dict(self, config_data: Dict[str, Any]) -> None:
        """Load configuration from dictionary."""
        # Load provider configurations
        providers_config = config_data.get("providers", [])
        
        for provider_data in providers_config:
            try:
                provider_config = MetadataProviderConfig.model_validate(provider_data)
                self._provider_configs[provider_config.name] = provider_config
            except Exception as e:
                logger.warning(f"Invalid provider config {provider_data.get('name', 'unknown')}: {e}")
        
        # Load global settings
        global_config = config_data.get("global_settings", {})
        if global_config:
            self._enable_caching = global_config.get("cache_enabled", self._enable_caching)
            self._cache_ttl = global_config.get("cache_ttl", self._cache_ttl)
            self._parallel_discovery = global_config.get("parallel_discovery", self._parallel_discovery)
            self._max_workers = global_config.get("max_workers", self._max_workers)
    
    async def _load_config_from_database(self) -> None:
        """Load provider configurations from database."""
        if not self._SessionLocal:
            return
        
        try:
            with self._SessionLocal() as session:
                # Load provider configurations
                db_providers = session.query(MetadataProviderModel).all()
                
                for provider_model in db_providers:
                    try:
                        provider_config: MetadataProviderConfig = MetadataProviderConfig.model_validate({
                            "name": provider_model.name,
                            "provider_type": provider_model.provider_type,
                            **provider_model.config,
                            "enabled": provider_model.enabled,
                            "priority": provider_model.priority,
                        })
                        
                        self._provider_configs[provider_config.name] = provider_config
                        
                        # Update cache timestamp
                        if provider_model.last_sync:
                            self._config_loaded = True
                    
                    except Exception as e:
                        logger.warning(f"Invalid database provider config {provider_model.name}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to load database configuration: {e}")

    def _require_session(self) -> None:
        if not self._SessionLocal:
            raise MetadataProviderError("Metadata provider manager has not been initialized")

    @staticmethod
    def _extract_config_payload(config_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            key: value
            for key, value in config_data.items()
            if key
            not in {
                "name",
                "provider_type",
                "enabled",
                "priority",
                "last_sync",
                "sync_errors",
            }
        }
        # Drop None values to keep JSON clean
        return {key: value for key, value in payload.items() if value is not None}

    def _build_config_from_model(self, model: MetadataProviderModel) -> MetadataProviderConfig:
        payload: Dict[str, Any] = dict(model.config or {})
        payload.update(
            {
                "name": model.name,
                "provider_type": model.provider_type,
                "enabled": model.enabled,
                "priority": model.priority,
                "last_sync": model.last_sync,
                "sync_errors": model.sync_errors or [],
                "description": payload.get("description"),
            }
        )
        validated: MetadataProviderConfig = MetadataProviderConfig.model_validate(payload)
        return validated

    async def create_provider(self, config: MetadataProviderConfig) -> MetadataProviderConfig:
        """Create a new metadata provider configuration."""
        self._require_session()

        if config.name in self._provider_configs:
            raise MetadataProviderError(f"Provider '{config.name}' already exists")

        provider_id = str(uuid4())
        config_data = config.model_dump()

        model = MetadataProviderModel(
            id=provider_id,
            name=config.name,
            provider_type=config.provider_type,
            config=self._extract_config_payload(config_data),
            enabled=config.enabled,
            priority=config.priority,
            last_sync=config.last_sync,
            sync_errors=config.sync_errors,
        )

        SessionLocal = self._SessionLocal
        assert SessionLocal is not None
        with SessionLocal() as session:
            session.add(model)
            session.commit()
            session.refresh(model)

        stored_config = self._build_config_from_model(model)
        self._provider_configs[stored_config.name] = stored_config

        if stored_config.enabled:
            provider = await self._create_provider(stored_config)
            if not provider:
                raise MetadataProviderError(
                    f"Provider '{stored_config.name}' could not be initialized with the supplied configuration"
                )
            self._providers[stored_config.name] = provider

        self._config_loaded = True
        return stored_config

    async def update_provider(self, provider_name: str, updates: Dict[str, Any]) -> MetadataProviderConfig:
        """Update an existing metadata provider configuration."""
        self._require_session()

        if provider_name not in self._provider_configs:
            raise MetadataProviderError(f"Provider '{provider_name}' does not exist")

        current_config = self._provider_configs[provider_name]
        updated_config = current_config.model_copy(update=updates)

        SessionLocal = self._SessionLocal
        assert SessionLocal is not None
        with SessionLocal() as session:
            model = (
                session.query(MetadataProviderModel)
                .filter(MetadataProviderModel.name == provider_name)
                .first()
            )
            if not model:
                raise MetadataProviderError(f"Provider '{provider_name}' not found in database")

            model.enabled = updated_config.enabled
            model.priority = updated_config.priority
            model.last_sync = updated_config.last_sync
            model.sync_errors = updated_config.sync_errors
            model.config = self._extract_config_payload(updated_config.model_dump())

            session.add(model)
            session.commit()
            session.refresh(model)

        stored_config = self._build_config_from_model(model)
        self._provider_configs[provider_name] = stored_config

        if stored_config.enabled:
            provider = await self._create_provider(stored_config)
            if not provider:
                raise MetadataProviderError(
                    f"Provider '{stored_config.name}' could not be initialized with the updated configuration"
                )
            self._providers[stored_config.name] = provider
        else:
            self._providers.pop(stored_config.name, None)

        return stored_config

    async def delete_provider(self, provider_name: str) -> None:
        """Delete a metadata provider."""
        self._require_session()

        if provider_name not in self._provider_configs:
            raise MetadataProviderError(f"Provider '{provider_name}' does not exist")

        SessionLocal = self._SessionLocal
        assert SessionLocal is not None
        with SessionLocal() as session:
            model = (
                session.query(MetadataProviderModel)
                .filter(MetadataProviderModel.name == provider_name)
                .first()
            )
            if not model:
                raise MetadataProviderError(f"Provider '{provider_name}' not found in database")

            session.query(PluginMetadataCache).filter(
                PluginMetadataCache.provider_id == model.id
            ).delete(synchronize_session=False)
            session.delete(model)
            session.commit()

        self._provider_configs.pop(provider_name, None)
        self._providers.pop(provider_name, None)

    async def get_provider_details(self, provider_name: str) -> Tuple[MetadataProviderConfig, Dict[str, Any]]:
        """Return provider configuration and statistics."""
        self._require_session()

        SessionLocal = self._SessionLocal
        assert SessionLocal is not None
        with SessionLocal() as session:
            model = (
                session.query(MetadataProviderModel)
                .filter(MetadataProviderModel.name == provider_name)
                .first()
            )
            if not model:
                raise MetadataProviderError(f"Provider '{provider_name}' not found")
            session.expunge(model)

        config = self._build_config_from_model(model)
        stats = {
            "id": model.id,
            "total_plugins": model.total_plugins or 0,
            "sync_success_count": model.sync_success_count or 0,
            "sync_error_count": model.sync_error_count or 0,
            "last_sync_duration": model.last_sync_duration,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }
        return config, stats
    
    async def _get_global_config(self) -> Optional[Dict[str, Any]]:
        """Get global configuration from database."""
        if not self._SessionLocal:
            return None
        
        try:
            SessionLocal = self._SessionLocal
            assert SessionLocal is not None
            with SessionLocal() as session:
                result = session.execute(text("SELECT config FROM global_metadata_config WHERE id = 'global'"))
                row = result.fetchone()
                return json.loads(row[0]) if row else None
        except Exception:
            return None
    
    async def _initialize_providers(self) -> None:
        """Initialize all enabled providers."""
        for name, config in self._provider_configs.items():
            if not config.enabled:
                continue
            
            try:
                provider = await self._create_provider(config)
                if provider:
                    self._providers[name] = provider
                    logger.info(f"Initialized provider: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize provider {name}: {e}")
                continue
    
    async def _create_provider(self, config: MetadataProviderConfig) -> Optional[MetadataProvider]:
        """Create provider instance from configuration."""
        try:
            if config.provider_type == MetadataProviderType.HTTP_JSON:
                return create_http_json_provider(config.model_dump())
            elif config.provider_type == MetadataProviderType.GIT_REPOSITORY:
                return create_git_repository_provider(config.model_dump())
            else:
                logger.warning(f"Unknown provider type: {config.provider_type}")
                return None
        
        except Exception as e:
            logger.error(f"Failed to create provider {config.name}: {e}")
            return None
    
    async def discover_plugins(self, query: Optional[str] = None, 
                             source_types: Optional[List[PluginMetadataSource]] = None) -> List[EnhancedPluginMetadata]:
        """Discover plugins from all enabled providers."""
        logger.info(f"Discovering plugins from all providers (query: {query})")
        
        if not self._config_loaded:
            await self._load_configuration()
        
        # Default to all source types if not specified
        if source_types is None:
            source_types = list(PluginMetadataSource)
        
        # Filter providers by source type and enabled status
        eligible_providers = []
        for name, provider in self._providers.items():
            config = self._provider_configs[name]
            if not config.enabled:
                continue
            # Map provider type to a logical source type
            if config.provider_type == MetadataProviderType.HTTP_JSON:
                provider_source = PluginMetadataSource.MARKETPLACE
            elif config.provider_type == MetadataProviderType.GIT_REPOSITORY:
                provider_source = PluginMetadataSource.LOCAL
            else:
                provider_source = PluginMetadataSource.CUSTOM
            if provider_source in source_types:
                eligible_providers.append((name, provider))
        
        if not eligible_providers:
            logger.warning("No eligible providers found for discovery")
            return []
        
        # Sort providers by priority (higher priority first)
        eligible_providers.sort(key=lambda x: self._provider_configs[x[0]].priority, reverse=True)
        
        try:
            if self._parallel_discovery:
                # Parallel discovery
                tasks = []
                for name, provider in eligible_providers:
                    task = self._discover_from_provider(name, provider, query)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Combine results
                all_plugins = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Provider {eligible_providers[i][0]} discovery failed: {result}")
                    elif isinstance(result, list):
                        all_plugins.extend(result)
                
                # Remove duplicates and sort
                unique_plugins = self._deduplicate_plugins(all_plugins)
                logger.info(f"Discovered {len(unique_plugins)} unique plugins from {len(eligible_providers)} providers")
                return unique_plugins
            
            else:
                # Sequential discovery
                all_plugins = []
                for name, provider in eligible_providers:
                    try:
                        plugins = await self._discover_from_provider(name, provider, query)
                        all_plugins.extend(plugins)
                    except Exception as e:
                        logger.error(f"Provider {name} discovery failed: {e}")
                        continue
                
                unique_plugins = self._deduplicate_plugins(all_plugins)
                logger.info(f"Discovered {len(unique_plugins)} unique plugins from {len(eligible_providers)} providers")
                return unique_plugins
        
        except Exception as e:
            logger.error(f"Plugin discovery failed: {e}")
            return []
    
    async def _discover_from_provider(self, provider_name: str, provider: MetadataProvider, query: Optional[str]) -> List[EnhancedPluginMetadata]:
        """Discover plugins from a single provider."""
        try:
            logger.debug(f"Discovering from provider: {provider_name}")
            
            # Get plugins from provider
            plugins = await provider.discover_plugins(query)
            
            # Filter plugins based on RBAC if security context is available
            if self._security_context:
                plugins = self._filter_plugins_by_permissions(plugins)
            
            # Cache plugins
            if self._enable_caching:
                await self._cache_plugins(plugins, provider_name)
            
            logger.debug(f"Provider {provider_name} returned {len(plugins)} plugins")
            return plugins
        
        except Exception as e:
            logger.error(f"Provider {provider_name} discovery error: {e}")
            return []
    
    def _deduplicate_plugins(self, plugins: List[EnhancedPluginMetadata]) -> List[EnhancedPluginMetadata]:
        """Remove duplicate plugins based on name and version."""
        seen = set()
        unique_plugins = []
        
        for plugin in plugins:
            key = (plugin.name, plugin.version)
            if key not in seen:
                seen.add(key)
                unique_plugins.append(plugin)
        
        # Sort by name and version
        unique_plugins.sort(key=lambda p: (p.name, p.version))
        return unique_plugins
    
    def _filter_plugins_by_permissions(self, plugins: List[EnhancedPluginMetadata]) -> List[EnhancedPluginMetadata]:
        """Filter plugins based on user permissions."""
        if not self._security_context:
            return plugins
        
        user_permissions = self._security_context.permissions
        filtered_plugins = []
        
        for plugin in plugins:
            # Check if user has permission to access this plugin
            if self._has_plugin_permission(plugin, user_permissions):
                filtered_plugins.append(plugin)
            else:
                logger.debug(f"User denied access to plugin {plugin.name}")
        
        return filtered_plugins
    
    def _has_plugin_permission(self, plugin: EnhancedPluginMetadata, user_permissions: List[str]) -> bool:
        """Check if user has permission to access a plugin."""
        # If plugin declares explicit permissions, require at least one match
        if plugin.permissions:
            return any(p in user_permissions for p in plugin.permissions)
        
        # Trusted sources require explicit trusted permission
        if plugin.trusted_source:
            return "plugins.trusted.read" in user_permissions
        
        # Enterprise plugins require enterprise read permission
        if plugin.source_type == PluginMetadataSource.ENTERPRISE:
            return "plugins.enterprise.read" in user_permissions
        
        # Default: allow only if user has generic plugins.read
        return "plugins.read" in user_permissions
    
    async def _cache_plugins(self, plugins: List[EnhancedPluginMetadata], provider_name: str) -> None:
        """Cache plugin metadata."""
        if not self._enable_caching or not self._SessionLocal:
            return
        
        try:
            SessionLocal = self._SessionLocal
            assert SessionLocal is not None
            with SessionLocal() as session:
                for plugin in plugins:
                    # Check if cached version exists and is still valid
                    metadata_id = create_metadata_id(plugin.name, plugin.version, provider_name)
                    
                    existing_cache = session.query(PluginMetadataCache).filter(
                        PluginMetadataCache.id == metadata_id
                    ).first()
                    
                    if existing_cache and datetime.now(UTC) < existing_cache.expires_at:
                        # Update access statistics
                        existing_cache.last_accessed = datetime.now(UTC)
                        existing_cache.access_count = (existing_cache.access_count or 0) + 1
                        session.commit()
                        continue
                    
                    # Create new cache entry and update in-memory cache
                    cache_entry = PluginMetadataCache(
                        id=metadata_id,
                        plugin_name=plugin.name,
                        version=plugin.version,
                        provider_id=provider_name,
                        metadata_json=plugin.model_dump_json(),
                        provider_type=plugin.provider_type or MetadataProviderType.PLUGIN_REGISTRY,
                        source_type=plugin.source_type or PluginMetadataSource.CUSTOM,
                        validation_status=plugin.validation_status,
                        validation_errors=plugin.validation_errors,
                        validation_warnings=plugin.validation_warnings,
                        expires_at=datetime.now(UTC) + timedelta(seconds=self._cache_ttl),
                    )
                    
                    session.merge(cache_entry)
                    # In-memory cache (latest per plugin)
                    cache_key = f"{plugin.name}:{plugin.version if plugin.version else 'latest'}"
                    self._metadata_cache[cache_key] = plugin
                    self._cache_timestamps[cache_key] = datetime.now(UTC)
                    # Maintain a 'latest' alias for convenience
                    latest_key = f"{plugin.name}:latest"
                    self._metadata_cache[latest_key] = plugin
                    self._cache_timestamps[latest_key] = datetime.now(UTC)
                
                session.commit()
        
        except Exception as e:
            logger.error(f"Failed to cache plugins: {e}")
    
    async def get_plugin_metadata(self, plugin_name: str, version: Optional[str] = None) -> Optional[EnhancedPluginMetadata]:
        """Get metadata for specific plugin."""
        logger.debug(f"Getting metadata for plugin: {plugin_name}:{version or 'latest'}")
        
        # Check cache first
        cache_key = f"{plugin_name}:{version or 'latest'}"
        if self._enable_caching and cache_key in self._metadata_cache:
            if datetime.now(UTC) - self._cache_timestamps[cache_key] < timedelta(seconds=self._cache_ttl):
                logger.debug("Using in-memory cached metadata")
                return self._metadata_cache[cache_key]
        
        # Check database cache
        if self._enable_caching and self._SessionLocal:
            cached_metadata = await self._get_cached_metadata(plugin_name, version)
            if cached_metadata:
                # Update in-memory cache
                self._metadata_cache[cache_key] = cached_metadata
                self._cache_timestamps[cache_key] = datetime.now(UTC)
                return cached_metadata
        
        # Get from providers
        try:
            # Search through all providers in priority order
            providers_sorted = sorted(
                self._providers.items(),
                key=lambda x: self._provider_configs[x[0]].priority,
                reverse=True
            )
            
            for provider_name, provider in providers_sorted:
                try:
                    metadata = await provider.get_plugin_metadata(plugin_name, version)
                    if metadata:
                        # Cache the result
                        if self._enable_caching:
                            await self._cache_plugins([metadata], provider_name)
                            self._metadata_cache[cache_key] = metadata
                            self._cache_timestamps[cache_key] = datetime.now(UTC)
                        
                        return metadata
                
                except Exception as e:
                    logger.debug(f"Provider {provider_name} failed to return metadata: {e}")
                    continue
            
            logger.warning(f"Plugin {plugin_name} not found in any provider")
            return None
        
        except Exception as e:
            logger.error(f"Failed to get plugin metadata for {plugin_name}:{e}")
            raise MetadataProviderError(f"Failed to get plugin metadata: {e}")
    
    async def _get_cached_metadata(self, plugin_name: str, version: Optional[str]) -> Optional[EnhancedPluginMetadata]:
        """Get metadata from database cache."""
        if not self._SessionLocal:
            return None
        
        try:
            SessionLocal = self._SessionLocal
            assert SessionLocal is not None
            with SessionLocal() as session:
                query = session.query(PluginMetadataCache).filter(
                    PluginMetadataCache.plugin_name == plugin_name
                )
                
                if version:
                    query = query.filter(PluginMetadataCache.version == version)
                
                cache_entry = query.order_by(PluginMetadataCache.cached_at.desc()).first()
                
                if cache_entry and datetime.now(UTC) < cache_entry.expires_at:
                    # Update access statistics
                    cache_entry.last_accessed = datetime.now(UTC)
                    cache_entry.access_count = (cache_entry.access_count or 0) + 1
                    session.commit()
                    
                    metadata_obj = cache_entry.get_metadata()
                    if isinstance(metadata_obj, EnhancedPluginMetadata):
                        return metadata_obj
                    return None
        
        except Exception as e:
            logger.error(f"Failed to get cached metadata: {e}")
        
        return None
    
    async def install_plugin(self, plugin_name: str, version: Optional[str] = None) -> bool:
        """Install a plugin using the plugin marketplace."""
        # Get plugin metadata first
        metadata = await self.get_plugin_metadata(plugin_name, version)
        if not metadata:
            logger.error(f"Plugin {plugin_name} metadata not found")
            return False
        
        # Check permissions
        if self._security_context and not self._has_plugin_permission(metadata, self._security_context.permissions):
            logger.error(f"User does not have permission to install plugin {plugin_name}")
            return False
        
        # Use the existing plugin marketplace for installation
        try:
            from .plugin_marketplace import plugin_marketplace
            
            # Get download URL
            download_url = metadata.get_download_url()
            if not download_url:
                logger.error(f"No download URL available for plugin {plugin_name}")
                return False
            
            success = await plugin_marketplace.install_plugin(
                name=plugin_name,
                version=version,
                source=download_url
            )
            
            if success:
                logger.info(f"Plugin {plugin_name}:{version or 'latest'} installed successfully")
            
            return success
        
        except Exception as e:
            logger.error(f"Failed to install plugin {plugin_name}:{e}")
            return False
    
    async def validate_all_providers(self) -> Dict[str, bool]:
        """Validate configuration of all providers."""
        results = {}
        
        for name, provider in self._providers.items():
            try:
                is_valid = await provider.validate_provider_config()
                results[name] = is_valid
                
                if is_valid:
                    logger.info(f"Provider {name} validation successful")
                else:
                    logger.warning(f"Provider {name} validation failed")
            
            except Exception as e:
                logger.error(f"Provider {name} validation error: {e}")
                results[name] = False
        
        return results
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about all configured providers."""
        info: Dict[str, Any] = {
            "total_providers": len(self._providers),
            "enabled_providers": len([p for p in self._providers.values()]),
            "providers": {},
            "global_settings": {
                "cache_enabled": self._enable_caching,
                "cache_ttl": self._cache_ttl,
                "parallel_discovery": self._parallel_discovery,
                "max_workers": self._max_workers,
            }
        }
        
        providers_info = cast(Dict[str, Any], info["providers"])  # narrow type for mypy
        for name, provider in self._providers.items():
            try:
                providers_info[name] = provider.get_provider_info()
            except Exception as e:
                providers_info[name] = {"error": str(e)}
        
        return info
    
    def set_security_context(self, security_context: SecurityContext) -> None:
        """Set security context for RBAC filtering."""
        self._security_context = security_context
    
    async def clear_cache(self) -> None:
        """Clear all metadata caches."""
        # Clear in-memory cache
        self._metadata_cache.clear()
        self._cache_timestamps.clear()
        
        # Clear database cache
        if self._SessionLocal:
            try:
                SessionLocal = self._SessionLocal
                assert SessionLocal is not None
                with SessionLocal() as session:
                    session.execute(text("DELETE FROM plugin_metadata_cache"))
                    session.commit()
                logger.info("Database cache cleared")
            except Exception as e:
                logger.error(f"Failed to clear database cache: {e}")
    
    async def save_configuration(self) -> None:
        """Save current configuration to file and database."""
        try:
            # Save to file
            config_data = {
                "providers": [config.model_dump(exclude={"auth_token", "api_key", "password"}) for config in self._provider_configs.values()],
                "global_settings": {
                    "cache_enabled": self._enable_caching,
                    "cache_ttl": self._cache_ttl,
                    "parallel_discovery": self._parallel_discovery,
                    "max_workers": self._max_workers,
                }
            }
            
            self.config_path.write_text(json.dumps(config_data, indent=2))
            
            # Save to database
            if self._SessionLocal:
                SessionLocal = self._SessionLocal
                assert SessionLocal is not None
                with SessionLocal() as session:
                    # Clear existing configurations
                    session.execute(text("DELETE FROM metadata_providers"))
                    
                    # Save provider configurations
                    for name, config in self._provider_configs.items():
                        provider_model = MetadataProviderModel(
                            id=name,
                            name=name,
                            provider_type=config.provider_type,
                            config=config.model_dump(exclude={"auth_token", "api_key", "password", "name", "provider_type"}),
                            enabled=config.enabled,
                            priority=config.priority,
                            last_sync=config.last_sync,
                            sync_errors=config.sync_errors,
                        )
                        session.add(provider_model)
                    
                    session.commit()
            
            logger.info("Configuration saved successfully")
        
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise MetadataProviderError(f"Failed to save configuration: {e}")
    
    async def close(self) -> None:
        """Close the metadata provider manager."""
        # Close database connections
        if self._engine:
            self._engine.dispose()
        
        logger.info("Metadata provider manager closed")


# Global instance
metadata_provider_manager = MetadataProviderManager()


# Configuration management functions
async def initialize_metadata_providers(config_path: Optional[str] = None) -> MetadataProviderManager:
    """Initialize global metadata provider manager."""
    global metadata_provider_manager
    
    if config_path:
        metadata_provider_manager = MetadataProviderManager(config_path)
    
    await metadata_provider_manager.initialize()
    return metadata_provider_manager


async def get_plugin_metadata(plugin_name: str, version: Optional[str] = None) -> Optional[EnhancedPluginMetadata]:
    """Get plugin metadata from the global manager."""
    return await metadata_provider_manager.get_plugin_metadata(plugin_name, version)


async def discover_plugins(query: Optional[str] = None) -> List[EnhancedPluginMetadata]:
    """Discover plugins from the global manager."""
    return await metadata_provider_manager.discover_plugins(query)


async def install_plugin(plugin_name: str, version: Optional[str] = None) -> bool:
    """Install a plugin using the global manager."""
    return await metadata_provider_manager.install_plugin(plugin_name, version)


# Default configuration template
DEFAULT_CONFIG_TEMPLATE = {
    "providers": [
        {
            "name": "NPM Registry",
            "provider_type": "http_json",
            "description": "Official NPM package registry",
            "base_url": "https://registry.npmjs.org",
            "enabled": True,
            "priority": 80,
            "cache_enabled": True,
            "cache_ttl": 3600,
        },
        {
            "name": "Agent System Repository", 
            "provider_type": "git_repository",
            "description": "Official Agent System plugin repository",
            "repository_url": "https://github.com/agent-system/plugins.git",
            "enabled": True,
            "priority": 90,
            "cache_enabled": True,
            "cache_ttl": 1800,
        },
    ],
    "global_settings": {
        "cache_enabled": True,
        "cache_ttl": 3600,
        "parallel_discovery": True,
        "max_workers": 5,
    }
}