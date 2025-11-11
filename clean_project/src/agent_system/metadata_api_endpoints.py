"""
Metadata Provider API Endpoints
FastAPI endpoints for plugin metadata provider management
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Callable, Dict, Optional, ParamSpec, TypeVar, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .api_schemas_metadata import (
    EnhancedPluginMetadata,
    MetadataAPIResponse,
    MetadataProviderCreate,
    MetadataProviderInfo,
    MetadataProviderResponse,
    MetadataProviderType,
    MetadataProviderUpdate,
    PluginDiscoveryRequest,
    PluginInstallRequest,
    PluginInstallResponse,
)
from .api_security import require_permission
from .auth_models import SecurityContext
from .metadata_provider_manager import MetadataProviderManager, metadata_provider_manager
from .plugin_metadata_models import (
    MetadataProviderConfig as InternalProviderConfig,
)
from .plugin_metadata_models import (
    MetadataProviderError,
)
from .plugin_metadata_models import (
    MetadataProviderType as InternalProviderType,
)

logger = logging.getLogger(__name__)

# Create metadata provider API router
metadata_router = APIRouter(
    prefix="/api/v1/metadata",
    tags=["Plugin Metadata Management"],
)

# Typed decorator wrappers to satisfy mypy for FastAPI route decorators
P = ParamSpec("P")
R = TypeVar("R")

def _typed_route(
    decorator_factory: Callable[..., Callable[[Callable[P, R]], Callable[..., Any]]],
) -> Callable[..., Callable[[Callable[P, R]], Callable[P, R]]]:
    def wrapper(*args: Any, **kwargs: Any) -> Callable[[Callable[P, R]], Callable[P, R]]:
        def inner(func: Callable[P, R]) -> Callable[P, R]:
            return cast(Callable[P, R], decorator_factory(*args, **kwargs)(func))

        return inner

    return wrapper

class TypedRouter:
    def __init__(self, router: APIRouter) -> None:
        self._router = router
        self.get = _typed_route(router.get)
        self.post = _typed_route(router.post)
        self.put = _typed_route(router.put)
        self.delete = _typed_route(router.delete)
        self.patch = _typed_route(router.patch)

# Use typed wrappers for route decorators
typed_router = TypedRouter(metadata_router)


# Dependency to get metadata provider manager
async def get_metadata_manager() -> MetadataProviderManager:
    """Get the global metadata provider manager."""
    if not getattr(metadata_provider_manager, "_config_loaded", False):
        await metadata_provider_manager.initialize()
    return metadata_provider_manager


def _to_internal_config(payload: MetadataProviderCreate) -> InternalProviderConfig:
    data = payload.model_dump(exclude_none=True)
    data["provider_type"] = InternalProviderType(payload.provider_type.value)
    validated: InternalProviderConfig = InternalProviderConfig.model_validate(data)
    return validated


def _build_provider_response(
    config: InternalProviderConfig, stats: Dict[str, Any]
) -> MetadataProviderResponse:
    return MetadataProviderResponse(
        id=stats["id"],
        name=config.name,
        provider_type=MetadataProviderType(config.provider_type.value),
        description=getattr(config, "description", None),
        base_url=config.base_url,
        repository_url=config.repository_url,
        local_path=config.local_path,
        enabled=config.enabled,
        priority=config.priority,
        cache_enabled=config.cache_enabled,
        cache_ttl=config.cache_ttl,
        rate_limit=config.rate_limit,
        last_sync=config.last_sync,
        sync_errors=config.sync_errors or [],
        total_plugins=stats.get("total_plugins", 0),
        sync_success_count=stats.get("sync_success_count", 0),
        sync_error_count=stats.get("sync_error_count", 0),
        last_sync_duration=stats.get("last_sync_duration"),
        created_at=stats["created_at"],
        updated_at=stats["updated_at"],
    )


# Plugin Discovery Endpoints
@typed_router.get(
    "/plugins",
    response_model=MetadataAPIResponse,
    summary="Discover Plugins",
    description="Discover plugins from all configured metadata providers",
)
async def discover_plugins(
    query: Optional[str] = Query(None, description="Search query"),
    source_types: Optional[str] = Query(None, description="Comma-separated source types"),
    categories: Optional[str] = Query(None, description="Comma-separated categories"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    min_rating: Optional[float] = Query(None, ge=0.0, le=5.0, description="Minimum rating"),
    trusted_only: bool = Query(False, description="Only show trusted sources"),
    include_invalid: bool = Query(False, description="Include invalid metadata"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
manager: MetadataProviderManager = Depends(get_metadata_manager),
security_context: Optional[SecurityContext] = Depends(lambda: None),  # Optional security context
) -> MetadataAPIResponse:
    """Discover plugins with filtering and search capabilities."""
    try:
        # Set security context if available
        if security_context:
            manager.set_security_context(security_context)
        
        # Parse source types
        parsed_source_types = None
        if source_types:
            from .plugin_metadata_models import PluginMetadataSource
            parsed_source_types = [
                PluginMetadataSource(st.strip()) 
                for st in source_types.split(",")
                if st.strip()
            ]
        
        # Create discovery request
        discovery_request = PluginDiscoveryRequest(
            query=query,
            source_types=parsed_source_types,
            categories=categories.split(",") if categories else None,
            tags=tags.split(",") if tags else None,
            min_rating=min_rating,
            trusted_only=trusted_only,
            include_invalid=include_invalid,
            limit=limit,
        )
        
        # Discover plugins
        plugins = await manager.discover_plugins(query=query)
        
        # Apply filtering
        filtered_plugins = []
        for plugin in plugins:
            # Source type filter
            if parsed_source_types and plugin.source_type not in parsed_source_types:
                continue
            
            # Category filter
            if discovery_request.categories and plugin.category not in discovery_request.categories:
                continue
            
            # Tags filter
            if discovery_request.tags and not any(tag in plugin.tags for tag in discovery_request.tags):
                continue
            
            # Rating filter
            if discovery_request.min_rating and plugin.get_rating() < discovery_request.min_rating:
                continue
            
            # Trusted source filter
            if discovery_request.trusted_only and not plugin.trusted_source:
                continue
            
            # Validation status filter
            if not discovery_request.include_invalid and plugin.validation_status.value != "valid":
                continue
            
            filtered_plugins.append(plugin)
            
            if len(filtered_plugins) >= discovery_request.limit:
                break
        
        # Convert to response format
        plugin_responses = [
            EnhancedPluginMetadata(
                **plugin.model_dump(),
                download_url=plugin.get_download_url(),
                icon_url=plugin.get_icon_url(),
                rating=plugin.get_rating(),
                download_count=plugin.get_download_count(),
            )
            for plugin in filtered_plugins
        ]
        
        return MetadataAPIResponse(
            success=True,
            message=f"Found {len(plugin_responses)} plugins",
            data=plugin_responses,
            metadata={
                "query": query,
                "total_found": len(plugins),
                "filtered_count": len(plugin_responses),
                "filters_applied": {
                    "source_types": parsed_source_types,
                    "categories": discovery_request.categories,
                    "tags": discovery_request.tags,
                    "min_rating": discovery_request.min_rating,
                    "trusted_only": discovery_request.trusted_only,
                    "include_invalid": discovery_request.include_invalid,
                },
            },
        )
    
    except Exception as e:
        logger.error(f"Plugin discovery failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plugin discovery failed: {str(e)}"
        )


@typed_router.get(
    "/plugins/{plugin_name}",
    response_model=MetadataAPIResponse,
    summary="Get Plugin Metadata",
    description="Get detailed metadata for a specific plugin",
)
async def get_plugin_metadata(
    plugin_name: str,
    version: Optional[str] = Query(None, description="Plugin version"),
manager: MetadataProviderManager = Depends(get_metadata_manager),
security_context: Optional[SecurityContext] = Depends(lambda: None),
) -> MetadataAPIResponse:
    """Get metadata for a specific plugin."""
    try:
        if security_context:
            manager.set_security_context(security_context)
        
        metadata = await manager.get_plugin_metadata(plugin_name, version)
        
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plugin '{plugin_name}' not found"
            )
        
        return MetadataAPIResponse(
            success=True,
            message=f"Metadata retrieved for plugin '{plugin_name}'",
            data=EnhancedPluginMetadata(
                **metadata.model_dump(),
                download_url=metadata.get_download_url(),
                icon_url=metadata.get_icon_url(),
                rating=metadata.get_rating(),
                download_count=metadata.get_download_count(),
            ),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get plugin metadata for {plugin_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve plugin metadata: {str(e)}"
        )


@typed_router.post(
    "/plugins/install",
    response_model=MetadataAPIResponse,
    summary="Install Plugin",
    description="Install a plugin using metadata from providers",
)
async def install_plugin(
    install_request: PluginInstallRequest,
manager: MetadataProviderManager = Depends(get_metadata_manager),
security_context: SecurityContext = Depends(require_permission("plugins", "install")),
) -> MetadataAPIResponse:
    """Install a plugin using the metadata provider system."""
    try:
        success = await manager.install_plugin(
            install_request.name,
            install_request.version,
        )
        
        if success:
            return MetadataAPIResponse(
                success=True,
                message=f"Plugin '{install_request.name}' installed successfully",
                data=PluginInstallResponse(
                    success=True,
                    plugin_name=install_request.name,
                    version=install_request.version,
                    message="Plugin installed successfully",
                ),
            )
        else:
            return MetadataAPIResponse(
                success=False,
                message=f"Failed to install plugin '{install_request.name}'",
                data=PluginInstallResponse(
                    success=False,
                    plugin_name=install_request.name,
                    version=install_request.version,
                    message="Plugin installation failed",
                ),
            )
    
    except Exception as e:
        logger.error(f"Plugin installation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plugin installation failed: {str(e)}"
        )


# Metadata Provider Management Endpoints
@typed_router.get(
    "/providers",
    response_model=MetadataAPIResponse,
    summary="List Metadata Providers",
    description="Get information about all configured metadata providers",
)
async def list_metadata_providers(
    manager: MetadataProviderManager = Depends(get_metadata_manager),
security_context: SecurityContext = Depends(require_permission("plugins", "admin")),
) -> MetadataAPIResponse:
    """List all configured metadata providers."""
    try:
        provider_info = manager.get_provider_info()
        
        return MetadataAPIResponse(
            success=True,
            message=f"Retrieved information for {provider_info['total_providers']} providers",
            data=MetadataProviderInfo(
                **provider_info,
            ),
        )
    
    except Exception as e:
        logger.error(f"Failed to get provider information: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve provider information: {str(e)}"
        )


@typed_router.post(
    "/providers",
    response_model=MetadataAPIResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Metadata Provider",
    description="Create a new metadata provider",
)
async def create_metadata_provider(
    provider_config: MetadataProviderCreate,
manager: MetadataProviderManager = Depends(get_metadata_manager),
security_context: SecurityContext = Depends(require_permission("plugins", "admin")),
) -> MetadataAPIResponse:
    """Create a new metadata provider."""
    try:
        internal_config = _to_internal_config(provider_config)
        created_config = await manager.create_provider(internal_config)
        config_snapshot, stats = await manager.get_provider_details(created_config.name)
        response = _build_provider_response(config_snapshot, stats)

        return MetadataAPIResponse(
            success=True,
            message=f"Metadata provider '{response.name}' created successfully",
            data=response,
            metadata={"config": config_snapshot.model_dump()},
        )

    except MetadataProviderError as e:
        logger.error(f"Failed to create metadata provider {provider_config.name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create metadata provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create metadata provider: {str(e)}"
        )


@typed_router.put(
    "/providers/{provider_name}",
    response_model=MetadataAPIResponse,
    summary="Update Metadata Provider",
    description="Update an existing metadata provider",
)
async def update_metadata_provider(
    provider_name: str,
    provider_update: MetadataProviderUpdate,
manager: MetadataProviderManager = Depends(get_metadata_manager),
security_context: SecurityContext = Depends(require_permission("plugins", "admin")),
) -> MetadataAPIResponse:
    """Update an existing metadata provider."""
    try:
        update_payload = provider_update.model_dump(exclude_unset=True)
        updated_config = await manager.update_provider(provider_name, update_payload)
        config_snapshot, stats = await manager.get_provider_details(updated_config.name)
        response = _build_provider_response(config_snapshot, stats)

        return MetadataAPIResponse(
            success=True,
            message=f"Metadata provider '{response.name}' updated successfully",
            data=response,
            metadata={"config": config_snapshot.model_dump()},
        )

    except MetadataProviderError as e:
        logger.error(f"Failed to update metadata provider {provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update metadata provider {provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update metadata provider: {str(e)}"
        )


@typed_router.delete(
    "/providers/{provider_name}",
    response_model=MetadataAPIResponse,
    summary="Delete Metadata Provider",
    description="Delete a metadata provider",
)
async def delete_metadata_provider(
    provider_name: str,
manager: MetadataProviderManager = Depends(get_metadata_manager),
security_context: SecurityContext = Depends(require_permission("plugins", "admin")),
) -> MetadataAPIResponse:
    """Delete a metadata provider."""
    try:
        await manager.delete_provider(provider_name)

        return MetadataAPIResponse(
            success=True,
            message=f"Metadata provider '{provider_name}' deleted successfully",
        )
    except MetadataProviderError as e:
        logger.error(f"Failed to delete metadata provider {provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to delete metadata provider {provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete metadata provider: {str(e)}"
        )


@typed_router.post(
    "/providers/validate",
    response_model=MetadataAPIResponse,
    summary="Validate All Providers",
    description="Validate configuration of all metadata providers",
)
async def validate_all_providers(
manager: MetadataProviderManager = Depends(get_metadata_manager),
security_context: SecurityContext = Depends(require_permission("plugins", "admin")),
) -> MetadataAPIResponse:
    """Validate configuration of all metadata providers."""
    try:
        validation_results = await manager.validate_all_providers()
        
        valid_providers = sum(1 for is_valid in validation_results.values() if is_valid)
        total_providers = len(validation_results)
        
        return MetadataAPIResponse(
            success=True,
            message=f"Validated {total_providers} providers: {valid_providers} valid, {total_providers - valid_providers} invalid",
            data={
                "validation_results": validation_results,
                "summary": {
                    "total_providers": total_providers,
                    "valid_providers": valid_providers,
                    "invalid_providers": total_providers - valid_providers,
                },
            },
        )
    
    except Exception as e:
        logger.error(f"Provider validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Provider validation failed: {str(e)}"
        )


# Health Monitoring Endpoints
@typed_router.get(
    "/health",
    response_model=MetadataAPIResponse,
    summary="Health Check",
    description="Check health of metadata provider system",
)
async def metadata_health_check(
manager: MetadataProviderManager = Depends(get_metadata_manager),
security_context: Optional[SecurityContext] = Depends(lambda: None),
) -> MetadataAPIResponse:
    """Health check for metadata provider system."""
    try:
        # Check provider health
        validation_results = await manager.validate_all_providers()
        
        healthy_providers = sum(1 for is_valid in validation_results.values() if is_valid)
        total_providers = len(validation_results)
        
        overall_healthy = healthy_providers > 0 or total_providers == 0
        
        return MetadataAPIResponse(
            success=overall_healthy,
            message=f"Metadata system health: {healthy_providers}/{total_providers} providers healthy",
            data={
                "overall_healthy": overall_healthy,
                "provider_health": validation_results,
                "total_providers": total_providers,
                "healthy_providers": healthy_providers,
                "timestamp": datetime.now(UTC),
            },
        )
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return MetadataAPIResponse(
            success=False,
            message=f"Health check failed: {str(e)}",
            data={
                "overall_healthy": False,
                "error": str(e),
                "timestamp": datetime.now(UTC),
            },
        )