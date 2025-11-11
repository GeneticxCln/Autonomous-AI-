"""
HTTP JSON Index Provider for Plugin Metadata
Fetches plugin metadata from HTTP endpoints serving JSON data
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, cast

import aiohttp
from aiohttp import ClientError, ClientTimeout

from .plugin_metadata_models import (
    EnhancedPluginMetadata,
    MetadataProviderAuthError,
    MetadataProviderConfig,
    MetadataProviderError,
    MetadataProviderNetworkError,
    MetadataProviderType,
    MetadataProviderValidationError,
    PluginMetadataSource,
    parse_metadata_from_dict,
)

logger = logging.getLogger(__name__)


class HTTPJSONIndexProvider:
    """Provider for fetching plugin metadata from HTTP JSON endpoints."""
    
    def __init__(self, config: MetadataProviderConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        
        # Validate configuration
        if not self.config.base_url:
            raise MetadataProviderError("base_url is required for HTTP JSON provider")
    
    async def __aenter__(self) -> "HTTPJSONIndexProvider":
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._close_session()
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure HTTP session is available."""
        if self._session is None or self._session.closed:
            timeout = ClientTimeout(total=30, connect=10)
            
            # Setup authentication headers
            headers = {"User-Agent": "AgentSystem-PluginMetadata/1.0"}
            if self.config.auth_token:
                headers["Authorization"] = f"Bearer {self.config.auth_token}"
            elif self.config.api_key:
                headers["X-API-Key"] = self.config.api_key
            
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=5,
                keepalive_timeout=30,
            )
            
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers,
                connector=connector,
            )
        
        # mypy: ensure non-Optional return
        assert self._session is not None
        return self._session
    
    async def _close_session(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self._cache_timestamps:
            return False
        
        cache_time = self._cache_timestamps[key]
        age = datetime.now(UTC) - cache_time
        return age.total_seconds() < float(int(self.config.cache_ttl))
    
    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make HTTP request to the endpoint and return JSON-parsed payload (dict or list)."""
        session = await self._ensure_session()
        
        base = cast(str, self.config.base_url)
        url = base.rstrip("/") + "/" + endpoint.lstrip("/")
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 401:
                    raise MetadataProviderAuthError(f"Authentication failed for {url}")
                elif response.status == 404:
                    raise MetadataProviderError(f"Endpoint not found: {url}")
                elif response.status >= 400:
                    text = await response.text()
                    raise MetadataProviderNetworkError(f"HTTP {response.status}: {text}")
                
                content_type = response.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    raise MetadataProviderError(f"Expected JSON response, got {content_type}")
                
                data: Any = await response.json()
                return data
        
        except ClientError as e:
            raise MetadataProviderNetworkError(f"Network error for {url}: {e}")
        except json.JSONDecodeError as e:
            raise MetadataProviderError(f"Invalid JSON response from {url}: {e}")
    
    async def _get_plugin_list(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of plugins from the index endpoint."""
        cache_key = f"plugin_list:{query or 'all'}"
        
        # Check cache
        if self.config.cache_enabled and self._is_cache_valid(cache_key):
            logger.debug(f"Using cached plugin list for query: {query}")
            return cast(List[Dict[str, Any]], self._cache[cache_key])
        
        # Prepare request parameters
        params = {}
        if query:
            params["q"] = query
        if self.config.search_terms:
            params["tags"] = ",".join(self.config.search_terms)
        
        # Add any custom filters
        for key, value in self.config.filters.items():
            if isinstance(value, list):
                params[key] = ",".join(map(str, value))
            else:
                params[key] = str(value)
        
        try:
            # Try common index endpoints
            endpoints_to_try = [
                "/plugins",
                "/index",
                "/api/plugins",
                "/api/v1/plugins",
                "/registry/plugins",
            ]
            
            plugins_data = None
            for endpoint in endpoints_to_try:
                try:
                    logger.debug(f"Trying endpoint: {endpoint}")
                    plugins_data = await self._make_request(endpoint, params)
                    logger.info(f"Successfully fetched plugins from {endpoint}")
                    break
                except Exception as e:
                    logger.debug(f"Failed to fetch from {endpoint}: {e}")
                    continue
            
            if plugins_data is None:
                raise MetadataProviderError("No valid plugin index endpoint found")
            
            # Extract plugins list from response
            plugins = self._extract_plugins_list(plugins_data)
            
            # Cache the result
            if self.config.cache_enabled:
                self._cache[cache_key] = plugins
                self._cache_timestamps[cache_key] = datetime.now(UTC)
            
            logger.info(f"Found {len(plugins)} plugins from provider: {self.config.name}")
            return plugins
        
        except Exception as e:
            logger.error(f"Failed to fetch plugin list: {e}")
            raise MetadataProviderError(f"Failed to fetch plugin list: {e}")
    
    def _extract_plugins_list(self, response_data: Any) -> List[Dict[str, Any]]:
        """Extract plugins list from various response formats."""
        # Try common response structures
        if isinstance(response_data, list):
            # Ensure list of dicts
            return [item for item in response_data if isinstance(item, dict)]
        
        if isinstance(response_data, dict):
            # Look for common keys
            for key in ["plugins", "items", "data", "results", "objects"]:
                if key in response_data and isinstance(response_data[key], list):
                    return cast(List[Dict[str, Any]], response_data[key])
            
            # Check if the dict itself represents a single plugin
            if "name" in response_data and "version" in response_data:
                return [response_data]
        
        raise MetadataProviderError("Unable to extract plugins list from response")
    
    async def _get_plugin_details(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed metadata for a specific plugin."""
        cache_key = f"plugin_details:{plugin_name}"
        
        # Check cache
        if self.config.cache_enabled and self._is_cache_valid(cache_key):
            logger.debug(f"Using cached plugin details for: {plugin_name}")
            return cast(Optional[Dict[str, Any]], self._cache[cache_key])
        
        # Try common detail endpoints
        endpoints_to_try = [
            f"/plugins/{plugin_name}",
            f"/plugin/{plugin_name}",
            f"/api/plugins/{plugin_name}",
            f"/api/v1/plugins/{plugin_name}",
            f"/registry/plugins/{plugin_name}",
        ]
        
        plugin_data: Optional[Dict[str, Any]] = None
        for endpoint in endpoints_to_try:
            try:
                logger.debug(f"Trying endpoint: {endpoint}")
                data = await self._make_request(endpoint)
                if isinstance(data, dict):
                    plugin_data = data
                    logger.debug(f"Successfully fetched plugin details from {endpoint}")
                    break
            except Exception as e:
                logger.debug(f"Failed to fetch from {endpoint}: {e}")
                continue
        
        if plugin_data is None:
            logger.warning(f"Plugin {plugin_name} not found in provider: {self.config.name}")
            return None
        
        # Cache the result
        if self.config.cache_enabled:
            self._cache[cache_key] = plugin_data
            self._cache_timestamps[cache_key] = datetime.now(UTC)
        
        return plugin_data
    
    async def discover_plugins(self, query: Optional[str] = None) -> List[EnhancedPluginMetadata]:
        """Discover plugins from the HTTP JSON provider."""
        logger.info(f"Discovering plugins from HTTP provider: {self.config.name} (query: {query})")
        
        try:
            raw_plugins = await self._get_plugin_list(query)
            enhanced_plugins = []
            
            for raw_plugin in raw_plugins:
                try:
                    # Parse and enhance the metadata
                    enhanced_plugin = await self._enhance_plugin_metadata(raw_plugin)
                    if enhanced_plugin:
                        enhanced_plugins.append(enhanced_plugin)
                
                except Exception as e:
                    logger.warning(f"Failed to process plugin {raw_plugin.get('name', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Successfully discovered {len(enhanced_plugins)} plugins")
            return enhanced_plugins
        
        except Exception as e:
            logger.error(f"Plugin discovery failed: {e}")
            # Return empty list rather than raising to allow graceful handling in callers/tests
            return []
    
    async def get_plugin_metadata(self, plugin_name: str, version: Optional[str] = None) -> Optional[EnhancedPluginMetadata]:
        """Get metadata for specific plugin."""
        logger.debug(f"Getting metadata for plugin: {plugin_name}:{version or 'latest'}")
        
        try:
            raw_plugin = await self._get_plugin_details(plugin_name)
            if not raw_plugin:
                return None
            
            # Check version if specified
            if version and raw_plugin.get("version") != version:
                # Try to get specific version
                raw_plugin = await self._get_plugin_version_details(plugin_name, version)
                if not raw_plugin:
                    logger.warning(f"Plugin {plugin_name}:{version} not found")
                    return None
            
            # Parse and enhance the metadata
            enhanced_plugin = await self._enhance_plugin_metadata(raw_plugin)
            return enhanced_plugin
        
        except Exception as e:
            logger.error(f"Failed to get plugin metadata for {plugin_name}:{e}")
            raise MetadataProviderError(f"Failed to get plugin metadata: {e}")
    
    async def _get_plugin_version_details(self, plugin_name: str, version: str) -> Optional[Dict[str, Any]]:
        """Get metadata for specific plugin version."""
        endpoints_to_try = [
            f"/plugins/{plugin_name}/{version}",
            f"/plugin/{plugin_name}/{version}",
            f"/api/plugins/{plugin_name}/versions/{version}",
        ]
        
        for endpoint in endpoints_to_try:
            try:
                logger.debug(f"Trying version endpoint: {endpoint}")
                data = await self._make_request(endpoint)
                if isinstance(data, dict):
                    return data
            except Exception as e:
                logger.debug(f"Failed to fetch from {endpoint}: {e}")
                continue
        
        return None
    
    async def _enhance_plugin_metadata(self, raw_plugin: Dict[str, Any]) -> Optional[EnhancedPluginMetadata]:
        """Enhance raw plugin data with provider-specific information."""
        try:
            # Create enhanced metadata with provider defaults
            enhanced_data = raw_plugin.copy()
            
            # Add provider-specific information
            enhanced_data["source_type"] = PluginMetadataSource.MARKETPLACE
            enhanced_data["provider_type"] = MetadataProviderType.HTTP_JSON
            enhanced_data["provider_config"] = self.config.model_dump(exclude={"auth_token", "api_key", "password"})
            
            # Add timestamps
            enhanced_data["last_validated"] = datetime.now(UTC)
            
            # Parse using the enhanced model
            enhanced_plugin = parse_metadata_from_dict(enhanced_data, PluginMetadataSource.MARKETPLACE)
            
            # Validate metadata
            enhanced_plugin.validate_metadata()
            
            # Add provider-specific metadata
            enhanced_plugin.metadata.update({
                "provider_name": self.config.name,
                "provider_url": self.config.base_url,
                "fetched_at": datetime.now(UTC).isoformat(),
                "cache_key": f"{self.config.name}:{enhanced_plugin.name}:{enhanced_plugin.version}",
            })
            
            return enhanced_plugin
        
        except Exception as e:
            logger.error(f"Failed to enhance plugin metadata: {e}")
            raise MetadataProviderValidationError(f"Failed to enhance plugin metadata: {e}")
    
    async def validate_provider_config(self) -> bool:
        """Validate provider configuration."""
        try:
            # Test basic connectivity
            await self._ensure_session()
            
            # Try to reach the base URL
            session = await self._ensure_session()
            base = cast(str, self.config.base_url)
            async with session.get(base) as response:
                if response.status >= 400:
                    logger.warning(f"Base URL returned status {response.status}")
                    return False
            
            # Try to fetch plugin index
            try:
                plugins = await self._get_plugin_list()
                logger.info(f"Provider validation successful: found {len(plugins)} plugins")
                return True
            except Exception as e:
                logger.warning(f"Plugin index test failed: {e}")
                return False
        
        except Exception as e:
            logger.error(f"Provider validation failed: {e}")
            return False
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information."""
        return {
            "name": self.config.name,
            "type": self.config.provider_type,
            "base_url": self.config.base_url,
            "enabled": self.config.enabled,
            "priority": self.config.priority,
            "cache_enabled": self.config.cache_enabled,
            "cache_ttl": self.config.cache_ttl,
            "last_sync": self.config.last_sync.isoformat() if self.config.last_sync else None,
            "sync_errors": self.config.sync_errors,
        }
    
    async def get_plugin_count(self) -> int:
        """Get approximate plugin count from provider."""
        try:
            plugins = await self._get_plugin_list()
            return len(plugins)
        except Exception as e:
            logger.error(f"Failed to get plugin count: {e}")
            return 0
    
    async def get_categories(self) -> List[str]:
        """Get available plugin categories."""
        try:
            # Try to get categories from a common endpoint
            endpoints_to_try = [
                "/categories",
                "/api/categories",
                "/api/v1/categories",
            ]
            
            for endpoint in endpoints_to_try:
                try:
                    categories_data = await self._make_request(endpoint)
                    if isinstance(categories_data, list):
                        return [str(x) for x in categories_data if isinstance(x, (str, int, float))]
                    elif isinstance(categories_data, dict) and "categories" in categories_data:
                        cats = categories_data["categories"]
                        if isinstance(cats, list):
                            return [str(x) for x in cats if isinstance(x, (str, int, float))]
                except Exception:
                    continue
            
            # Fallback: extract from plugin list
            plugins = await self._get_plugin_list()
            categories = set()
            for plugin in plugins:
                if "category" in plugin:
                    categories.add(plugin["category"])
            return sorted(list(categories))
        
        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
            return []
    
    async def get_featured_plugins(self, limit: int = 10) -> List[EnhancedPluginMetadata]:
        """Get featured plugins from provider."""
        try:
            # Try featured endpoint first
            featured_endpoints = [
                "/featured",
                "/api/featured",
                "/api/v1/featured",
            ]
            
            for endpoint in featured_endpoints:
                try:
                    featured_data = await self._make_request(endpoint)
                    plugins_data = self._extract_plugins_list(featured_data)
                    featured_plugins = []
                    for plugin_data in plugins_data[:limit]:
                        enhanced_plugin = await self._enhance_plugin_metadata(plugin_data)
                        if enhanced_plugin:
                            featured_plugins.append(enhanced_plugin)
                    return featured_plugins
                except Exception:
                    continue
            
            # Fallback: get from plugin list with featured filter
            plugins = await self._get_plugin_list()
            featured_plugins = []
            for plugin in plugins[:limit]:
                if plugin.get("featured") or plugin.get("popular"):
                    enhanced_plugin = await self._enhance_plugin_metadata(plugin)
                    if enhanced_plugin:
                        featured_plugins.append(enhanced_plugin)
            
            return featured_plugins
        
        except Exception as e:
            logger.error(f"Failed to get featured plugins: {e}")
            return []


# Factory function for creating HTTP JSON providers
def create_http_json_provider(config_data: Dict[str, Any]) -> HTTPJSONIndexProvider:
    """Create HTTP JSON provider from configuration data."""
    config = MetadataProviderConfig.model_validate({
        **config_data,
        "provider_type": MetadataProviderType.HTTP_JSON,
    })
    return HTTPJSONIndexProvider(config)


# Default configurations for popular plugin registries
DEFAULT_REGISTRY_CONFIGS = {
    "npm_registry": {
        "name": "NPM Registry",
        "base_url": "https://registry.npmjs.org",
        "description": "Official NPM package registry",
        "cache_enabled": True,
        "cache_ttl": 3600,
    },
    "pypi_registry": {
        "name": "PyPI Registry", 
        "base_url": "https://pypi.org/pypi",
        "description": "Python Package Index",
        "cache_enabled": True,
        "cache_ttl": 3600,
    },
    "custom_plugin_hub": {
        "name": "Custom Plugin Hub",
        "base_url": "https://plugins.example.com/api/v1",
        "description": "Enterprise plugin repository",
        "auth_token": "${PLUGIN_HUB_TOKEN}",
        "cache_enabled": True,
        "cache_ttl": 1800,
        "rate_limit": 60,
    },
}