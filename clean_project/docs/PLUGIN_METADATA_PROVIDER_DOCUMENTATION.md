# Plugin Metadata Provider System Documentation

## Overview

The Plugin Metadata Provider System is a comprehensive solution for managing plugin metadata from multiple sources with built-in support for RBAC (Role-Based Access Control), caching, and enterprise-grade features. This system enables flexible plugin discovery, validation, and installation across various metadata sources including HTTP APIs, Git repositories, and local directories.

## Architecture

### Core Components

1. **EnhancedPluginMetadata**: Core data model with extended schema for plugin metadata
2. **Metadata Providers**: Pluggable components for fetching metadata from different sources
3. **MetadataProviderManager**: Central coordination and management system
4. **Database Layer**: Persistent storage and caching of metadata and provider configurations
5. **RBAC Integration**: Security and permission filtering based on user roles

### Provider Types

#### HTTP JSON Index Provider
- Fetches plugin metadata from HTTP endpoints serving JSON data
- Supports authentication via API keys, tokens, or credentials
- Automatic caching and rate limiting
- Compatible with NPM, PyPI, and custom registries

#### Git Repository Provider
- Discovers plugins from Git repositories
- Supports multiple package formats (JSON, TOML, Python setup files)
- Handles public and private repositories with authentication
- Automatic metadata extraction from standard package files

#### Local Directory Provider (planned)
- Scans local directories for plugin metadata
- Supports enterprise and internal plugin collections

## Installation and Setup

### Dependencies

The metadata provider system requires the following dependencies:

```bash
# Core dependencies
pip install aiohttp sqlalchemy pydantic

# Optional dependencies for enhanced features
pip install tomli  # For TOML parsing (Python < 3.11)
pip install passlib  # For enhanced security features
```

### Basic Setup

```python
import asyncio
from agent_system.metadata_provider_manager import initialize_metadata_providers

# Initialize the system
async def setup_plugin_metadata():
    manager = await initialize_metadata_providers("plugin_providers.json")
    return manager

# Usage
manager = asyncio.run(setup_plugin_metadata())
plugins = await manager.discover_plugins()
```

### Database Configuration

The system uses SQLite by default, but supports any SQLAlchemy-compatible database:

```python
# Custom database configuration
manager = MetadataProviderManager(
    config_path="plugin_providers.json",
    database_url="postgresql://user:pass@localhost/plugin_metadata"
)
```

## Configuration

### Configuration File Format

Create a `plugin_providers.json` file to configure metadata providers:

```json
{
  "providers": [
    {
      "name": "NPM Registry",
      "provider_type": "http_json",
      "description": "Official NPM package registry",
      "base_url": "https://registry.npmjs.org",
      "enabled": true,
      "priority": 80,
      "cache_enabled": true,
      "cache_ttl": 3600,
      "filters": {
        "keywords": ["agent-system", "plugin"]
      }
    },
    {
      "name": "Agent System Repository",
      "provider_type": "git_repository", 
      "description": "Official plugin repository",
      "repository_url": "https://github.com/agent-system/plugins.git",
      "enabled": true,
      "priority": 90,
      "cache_enabled": true,
      "cache_ttl": 1800
    },
    {
      "name": "Enterprise Repository",
      "provider_type": "git_repository",
      "description": "Internal enterprise plugins",
      "repository_url": "https://gitlab.company.com/internal/plugins.git",
      "auth_token": "${GITLAB_TOKEN}",
      "enabled": true,
      "priority": 95,
      "cache_enabled": true,
      "cache_ttl": 3600
    }
  ],
  "global_settings": {
    "cache_enabled": true,
    "cache_ttl": 3600,
    "parallel_discovery": true,
    "max_workers": 5
  }
}
```

### Provider Configuration

#### HTTP JSON Provider Configuration

```python
from agent_system.plugin_metadata_models import MetadataProviderConfig, MetadataProviderType

config = MetadataProviderConfig(
    provider_type=MetadataProviderType.HTTP_JSON,
    name="Custom Registry",
    description="Custom plugin registry",
    base_url="https://api.example.com/v1",
    
    # Authentication (optional)
    auth_token="Bearer token",
    api_key="api-key-here",
    username="username",
    password="password",
    
    # Performance settings
    cache_enabled=True,
    cache_ttl=3600,  # 1 hour
    rate_limit=60,   # 60 requests per minute
    
    # Filtering
    filters={
        "category": ["development", "productivity"],
        "min_rating": 4.0
    },
    
    # Search terms
    search_terms=["agent", "automation"],
    
    # Provider behavior
    enabled=True,
    priority=80
)
```

#### Git Repository Provider Configuration

```python
config = MetadataProviderConfig(
    provider_type=MetadataProviderType.GIT_REPOSITORY,
    name="Company Plugins",
    description="Internal company plugin repository",
    repository_url="https://github.com/company/plugins.git",
    
    # Authentication
    auth_token="${GITHUB_TOKEN}",
    username="username",
    password="password",
    
    # Caching
    cache_enabled=True,
    cache_ttl=7200,  # 2 hours
    
    # Behavior
    enabled=True,
    priority=90
)
```

### Environment Variables

Use environment variables for sensitive configuration:

```bash
# Set authentication tokens
export GITHUB_TOKEN="ghp_..."
export GITLAB_TOKEN="glpat-..."
export PLUGIN_HUB_TOKEN="custom-token"

# Set database configuration
export PLUGIN_METADATA_DB_URL="postgresql://user:pass@localhost/plugin_metadata"
```

## Usage Examples

### Basic Plugin Discovery

```python
import asyncio
from agent_system.metadata_provider_manager import MetadataProviderManager

async def discover_plugins():
    manager = MetadataProviderManager()
    await manager.initialize()
    
    # Discover all plugins
    all_plugins = await manager.discover_plugins()
    print(f"Found {len(all_plugins)} plugins")
    
    # Search for specific plugins
    search_results = await manager.discover_plugins("web scraping")
    print(f"Found {len(search_results)} matching plugins")
    
    # Get specific plugin metadata
    metadata = await manager.get_plugin_metadata("web-scraper")
    if metadata:
        print(f"Plugin: {metadata.name} v{metadata.version}")
        print(f"Description: {metadata.description}")
        print(f"Author: {metadata.author}")

asyncio.run(discover_plugins())
```

### Plugin Installation

```python
async def install_plugin_example():
    manager = MetadataProviderManager()
    await manager.initialize()
    
    # Install a plugin
    success = await manager.install_plugin("web-scraper", "1.2.0")
    if success:
        print("Plugin installed successfully!")
    else:
        print("Plugin installation failed!")
```

### Provider Management

```python
async def manage_providers():
    manager = MetadataProviderManager()
    await manager.initialize()
    
    # Get provider information
    info = manager.get_provider_info()
    print(f"Total providers: {info['total_providers']}")
    print(f"Enabled providers: {info['enabled_providers']}")
    
    # Validate provider configurations
    validation_results = await manager.validate_all_providers()
    for provider, is_valid in validation_results.items():
        status = "✓ Valid" if is_valid else "✗ Invalid"
        print(f"{provider}: {status}")
    
    # Clear cache if needed
    await manager.clear_cache()
```

### Working with Enhanced Metadata

```python
async def work_with_metadata():
    manager = MetadataProviderManager()
    await manager.initialize()
    
    metadata = await manager.get_plugin_metadata("advanced-web-scraper")
    
    if metadata:
        # Access enhanced metadata fields
        print(f"Name: {metadata.name}")
        print(f"Version: {metadata.version}")
        print(f"Display Name: {metadata.display_name}")
        print(f"Category: {metadata.category}")
        print(f"Tags: {', '.join(metadata.tags)}")
        print(f"License: {metadata.license}")
        print(f"Dependencies: {', '.join(metadata.dependencies)}")
        
        # Check compatibility
        system_info = {
            "python_version": "3.9.0",
            "os": "linux"
        }
        compatible = metadata.is_compatible_with(system_info)
        print(f"Compatible: {compatible}")
        
        # Get download information
        download_url = metadata.get_download_url()
        print(f"Download URL: {download_url}")
        
        # Check validation status
        status = metadata.validation_status
        if status.value != "valid":
            print(f"Validation warnings: {metadata.validation_warnings}")
            print(f"Validation errors: {metadata.validation_errors}")
```

### RBAC Integration

```python
from agent_system.auth_models import SecurityContext

async def secure_plugin_discovery():
    manager = MetadataProviderManager()
    await manager.initialize()
    
    # Set security context (e.g., from authenticated user)
    # This would typically come from your authentication system
    class MockUser:
        def __init__(self, permissions):
            self.permissions = permissions
    
    user = MockUser([
        "plugins.read",
        "plugins.trusted.read"
    ])
    
    # Create security context
    security_context = SecurityContext(user, user.permissions)
    manager.set_security_context(security_context)
    
    # Now discovery will only return plugins the user has access to
    plugins = await manager.discover_plugins()
    print(f"User can access {len(plugins)} plugins")
```

## API Reference

### EnhancedPluginMetadata

The core data model for plugin metadata:

```python
class EnhancedPluginMetadata(BaseModel):
    # Core identification
    name: str
    version: str
    unique_id: Optional[str]
    
    # Basic information
    display_name: Optional[str]
    description: str
    short_description: Optional[str]
    author: str
    maintainer: Optional[str]
    homepage: Optional[str]
    repository_url: Optional[str]
    documentation_url: Optional[str]
    
    # Classification
    category: Optional[str]
    tags: List[str]
    keywords: List[str]
    license: Optional[str]
    
    # Version and compatibility
    compatibility: Dict[str, Any]
    requirements: Dict[str, Any]
    dependencies: List[str]
    peer_dependencies: List[str]
    
    # Entry points and configuration
    entry_point: str
    configuration_schema: Optional[Dict[str, Any]]
    api_schema: Optional[Dict[str, Any]]
    
    # Security and permissions
    permissions: List[str]
    security_requirements: List[str]
    trusted_source: bool
    
    # Status and metadata
    metadata: Dict[str, Any]
    custom_fields: Dict[str, Any]
    
    # Validation
    validation_status: MetadataValidationStatus
    validation_errors: List[str]
    validation_warnings: List[str]
```

### MetadataProviderConfig

Configuration for metadata providers:

```python
class MetadataProviderConfig(BaseModel):
    provider_type: MetadataProviderType
    name: str
    description: Optional[str]
    
    # Provider-specific configuration
    base_url: Optional[str]
    repository_url: Optional[str]
    local_path: Optional[str]
    
    # Authentication
    auth_token: Optional[str]
    api_key: Optional[str]
    username: Optional[str]
    password: Optional[str]
    
    # Performance and caching
    cache_enabled: bool
    cache_ttl: int
    rate_limit: Optional[int]
    
    # Filtering and search
    filters: Dict[str, Any]
    search_terms: List[str]
    
    # Status and behavior
    enabled: bool
    priority: int
```

### MetadataProviderManager

Main manager class:

```python
class MetadataProviderManager:
    async def initialize() -> None
    async def discover_plugins(self, query: Optional[str] = None) -> List[EnhancedPluginMetadata]
    async def get_plugin_metadata(self, plugin_name: str, version: Optional[str] = None) -> Optional[EnhancedPluginMetadata]
    async def install_plugin(self, plugin_name: str, version: Optional[str] = None) -> bool
    async def validate_all_providers(self) -> Dict[str, bool]
    def get_provider_info(self) -> Dict[str, Any]
    def set_security_context(self, security_context) -> None
    async def clear_cache() -> None
    async def save_configuration() -> None
    async def close() -> None
```

### Global Functions

Convenience functions for common operations:

```python
from agent_system.metadata_provider_manager import (
    initialize_metadata_providers,
    get_plugin_metadata,
    discover_plugins,
    install_plugin
)

# Quick start functions
manager = await initialize_metadata_providers()
plugins = await discover_plugins("search term")
metadata = await get_plugin_metadata("plugin-name")
success = await install_plugin("plugin-name", "1.0.0")
```

## Provider Development

### Creating Custom Providers

To create a custom metadata provider, implement the `MetadataProvider` protocol:

```python
from agent_system.plugin_metadata_models import MetadataProvider, EnhancedPluginMetadata

class CustomMetadataProvider(MetadataProvider):
    def __init__(self, config: MetadataProviderConfig):
        self.config = config
    
    async def discover_plugins(self, query: Optional[str] = None) -> List[EnhancedPluginMetadata]:
        # Implementation for discovering plugins
        # Return list of EnhancedPluginMetadata objects
        pass
    
    async def get_plugin_metadata(self, plugin_name: str, version: Optional[str] = None) -> Optional[EnhancedPluginMetadata]:
        # Implementation for getting specific plugin metadata
        # Return EnhancedPluginMetadata object or None
        pass
    
    async def validate_provider_config(self) -> bool:
        # Implementation for validating provider configuration
        # Return True if configuration is valid
        pass
    
    def get_provider_info(self) -> Dict[str, Any]:
        # Return provider information
        return {
            "name": self.config.name,
            "type": self.config.provider_type,
            # ... other info
        }

# Factory function
def create_custom_provider(config_data: Dict[str, Any]) -> CustomMetadataProvider:
    config = MetadataProviderConfig.parse_obj({
        **config_data,
        "provider_type": MetadataProviderType.CUSTOM,
    })
    return CustomMetadataProvider(config)
```

### Provider Integration

To integrate a custom provider:

```python
# Add to configuration
config_data = {
    "providers": [
        {
            "name": "My Custom Provider",
            "provider_type": "custom",
            "description": "My custom metadata provider",
            "base_url": "https://my-api.com",
            "enabled": True,
            "priority": 70
        }
    ]
}

# Register with manager
manager = MetadataProviderManager()
manager._provider_type_mapping["custom"] = create_custom_provider
```

## Best Practices

### Performance Optimization

1. **Enable Caching**: Always enable caching for production use
   ```python
   "cache_enabled": true,
   "cache_ttl": 3600  # 1 hour
   ```

2. **Use Parallel Discovery**: Enable parallel discovery for better performance
   ```python
   "parallel_discovery": true,
   "max_workers": 5
   ```

3. **Set Appropriate Priorities**: Higher priority providers are searched first
   ```python
   "priority": 90  # High priority
   ```

4. **Rate Limiting**: Configure rate limits to avoid overwhelming providers
   ```python
   "rate_limit": 60  # 60 requests per minute
   ```

### Security Considerations

1. **Use Environment Variables**: Never hardcode credentials
   ```bash
   export GITHUB_TOKEN="ghp_..."
   ```

2. **RBAC Integration**: Always set security context for multi-user environments
   ```python
   manager.set_security_context(security_context)
   ```

3. **Validate Providers**: Regularly validate provider configurations
   ```python
   results = await manager.validate_all_providers()
   ```

4. **Trusted Sources**: Mark trusted sources appropriately
   ```python
   metadata = EnhancedPluginMetadata(
       trusted_source=True,
       # ...
   )
   ```

### Error Handling

1. **Graceful Degradation**: Handle provider failures gracefully
   ```python
   try:
       plugins = await provider.discover_plugins()
   except MetadataProviderError as e:
       logger.error(f"Provider failed: {e}")
       plugins = []  # Continue with other providers
   ```

2. **Retry Logic**: Implement retry logic for transient failures
   ```python
   for attempt in range(3):
       try:
           return await provider.discover_plugins()
       except MetadataProviderNetworkError:
           if attempt == 2:
               raise
           await asyncio.sleep(2 ** attempt)
   ```

3. **Validation**: Validate metadata before caching
   ```python
   metadata.validate_metadata()
   if metadata.validation_status == MetadataValidationStatus.INVALID:
       raise MetadataProviderValidationError(f"Invalid metadata: {metadata.validation_errors}")
   ```

### Monitoring and Debugging

1. **Logging**: Enable appropriate logging levels
   ```python
   import logging
   logging.getLogger("agent_system.metadata").setLevel(logging.DEBUG)
   ```

2. **Provider Information**: Monitor provider status
   ```python
   info = manager.get_provider_info()
   for name, provider_info in info["providers"].items():
       print(f"{name}: {provider_info.get('status', 'unknown')}")
   ```

3. **Cache Monitoring**: Monitor cache effectiveness
   ```python
   # Check cache hit rates
   cache_info = manager.get_cache_statistics()
   ```

4. **Performance Metrics**: Track discovery times
   ```python
   import time
   start_time = time.time()
   plugins = await manager.discover_plugins()
   duration = time.time() - start_time
   print(f"Discovery took {duration:.2f} seconds")
   ```

## Troubleshooting

### Common Issues

#### Provider Configuration Errors

**Problem**: Provider validation fails
```python
# Debug provider configuration
config = MetadataProviderConfig.parse_obj(config_data)
provider = create_http_json_provider(config_data)
is_valid = await provider.validate_provider_config()
```

**Solution**: Check authentication credentials and network connectivity

#### Network Timeouts

**Problem**: HTTP providers time out
```python
# Increase timeout
config = MetadataProviderConfig(
    # ...
    rate_limit=30,  # Reduce rate
)
```

**Solution**: Reduce rate limits or increase timeouts

#### Caching Issues

**Problem**: Stale metadata in cache
```python
# Clear cache
await manager.clear_cache()

# Reduce cache TTL
"cache_ttl": 1800  # 30 minutes
```

**Solution**: Clear cache and reduce TTL if data changes frequently

#### Memory Usage

**Problem**: High memory usage
```python
# Disable in-memory caching for large datasets
"cache_enabled": false
```

**Solution**: Disable caching for large datasets or increase system memory

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("agent_system.metadata").setLevel(logging.DEBUG)
```

### Health Checks

Implement health checks:

```python
async def health_check():
    manager = MetadataProviderManager()
    await manager.initialize()
    
    # Validate all providers
    results = await manager.validate_all_providers()
    
    healthy_providers = sum(1 for valid in results.values() if valid)
    total_providers = len(results)
    
    if healthy_providers < total_providers:
        logger.warning(f"{healthy_providers}/{total_providers} providers are healthy")
    
    return healthy_providers > 0
```

## Migration Guide

### From Legacy Plugin System

If migrating from the legacy plugin marketplace:

1. **Update Configuration**: Convert existing provider configurations
2. **Update Code**: Replace direct marketplace calls with metadata provider calls
3. **Migrate Data**: Run migration scripts to transfer existing plugin data
4. **Test Thoroughly**: Verify all existing functionality works with new system

### Example Migration

```python
# Old way
from agent_system.plugin_marketplace import plugin_marketplace
plugins = await plugin_marketplace.discover_plugins()

# New way
from agent_system.metadata_provider_manager import MetadataProviderManager
manager = MetadataProviderManager()
await manager.initialize()
plugins = await manager.discover_plugins()
```

## Future Enhancements

### Planned Features

1. **Additional Provider Types**:
   - Local directory scanning
   - Package manager integration (pip, npm)
   - Enterprise registry connectors

2. **Enhanced Security**:
   - Digital signature verification
   - Vulnerability scanning integration
   - Certificate pinning

3. **Performance Improvements**:
   - Distributed caching
   - Incremental discovery
   - Smart prefetching

4. **Analytics and Insights**:
   - Plugin usage analytics
   - Popularity metrics
   - Security scoring

### Contributing

To contribute to the metadata provider system:

1. **Fork the Repository**: Create a fork of the main repository
2. **Create Feature Branch**: Create a branch for your feature
3. **Add Tests**: Ensure comprehensive test coverage
4. **Update Documentation**: Document new features and changes
5. **Submit Pull Request**: Submit a pull request with detailed description

## Support

For issues and questions:

1. **Check Documentation**: Review this documentation and troubleshooting section
2. **Search Issues**: Check existing GitHub issues
3. **Create Issue**: Create a detailed issue with reproduction steps
4. **Community**: Join our community discussions

## License

The Plugin Metadata Provider System is licensed under the same license as the Agent System project. See the LICENSE file for details.