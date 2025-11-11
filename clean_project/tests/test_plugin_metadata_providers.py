"""
Tests for Plugin Metadata Provider System
Comprehensive test suite for metadata providers and configuration management
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from agent_system.git_repository_provider import (
    GitRepositoryProvider,
    create_git_repository_provider,
)
from agent_system.http_json_provider import HTTPJSONIndexProvider, create_http_json_provider
from agent_system.metadata_provider_manager import (
    DEFAULT_CONFIG_TEMPLATE,
    MetadataProviderManager,
)

# Import the modules to test
from agent_system.plugin_metadata_models import (
    EnhancedPluginMetadata,
    MetadataProviderConfig,
    MetadataProviderError,
    MetadataProviderType,
    MetadataValidationStatus,
    PluginMetadataSource,
    parse_metadata_from_dict,
)


class TestEnhancedPluginMetadata:
    """Test EnhancedPluginMetadata model."""
    
    def test_valid_metadata_creation(self):
        """Test creating valid plugin metadata."""
        metadata = EnhancedPluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin description",
            author="Test Author",
            entry_point="test_plugin:TestPlugin",
            category="development",
            tags=["testing", "development"],
            permissions=["test.read", "test.write"],
        )
        
        assert metadata.name == "test-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.category == "development"
        assert "testing" in metadata.tags
        assert metadata.provider_type is None
        assert metadata.source_type == PluginMetadataSource.MARKETPLACE
    
    def test_metadata_validation(self):
        """Test metadata validation."""
        # Valid metadata
        valid_metadata = EnhancedPluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test description",
            author="Test Author",
            entry_point="test_plugin:TestPlugin",
        )
        
        status = valid_metadata.validate_metadata()
        assert status == MetadataValidationStatus.VALID
        assert len(valid_metadata.validation_errors) == 0
    
    def test_invalid_metadata(self):
        """Test invalid metadata validation."""
        # Invalid metadata (missing required fields)
        invalid_metadata = EnhancedPluginMetadata(
            name="",  # Empty name should fail
            version="1.0.0",
            description="Test description",
            author="Test Author",
            entry_point="test_plugin:TestPlugin",
        )
        
        status = invalid_metadata.validate_metadata()
        assert status == MetadataValidationStatus.INVALID
        assert len(invalid_metadata.validation_errors) > 0
        assert "Required field 'name'" in str(invalid_metadata.validation_errors)
    
    def test_version_validation(self):
        """Test version format validation."""
        # Valid versions
        valid_versions = ["1.0.0", "1.2.3", "1.0.0-beta.1", "2.1.0-alpha"]
        for version in valid_versions:
            metadata = EnhancedPluginMetadata(
                name="test",
                version=version,
                description="Test",
                author="Test",
                entry_point="test:Test",
            )
            metadata.validate_metadata()
            assert metadata.validation_status in [MetadataValidationStatus.VALID, MetadataValidationStatus.WARNING]
        
        # Invalid versions
        invalid_versions = ["v1.0.0", "1.0", "1.0.0.0.0"]
        for version in invalid_versions:
            metadata = EnhancedPluginMetadata(
                name="test",
                version=version,
                description="Test",
                author="Test",
                entry_point="test:Test",
            )
            metadata.validate_metadata()
            assert metadata.validation_status == MetadataValidationStatus.INVALID
    
    def test_conversion_to_legacy_format(self):
        """Test conversion to legacy PluginMetadata format."""
        enhanced_metadata = EnhancedPluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test description",
            author="Test Author",
            dependencies=["dependency1", "dependency2"],
            entry_point="test_plugin:TestPlugin",
            repository_url="https://github.com/test/plugin",
        )
        
        legacy_metadata = enhanced_metadata.to_legacy_metadata()
        
        assert legacy_metadata.name == enhanced_metadata.name
        assert legacy_metadata.version == enhanced_metadata.version
        assert legacy_metadata.description == enhanced_metadata.description
        assert legacy_metadata.author == enhanced_metadata.author
        assert legacy_metadata.dependencies == enhanced_metadata.dependencies
        assert legacy_metadata.entry_point == enhanced_metadata.entry_point
        assert legacy_metadata.repository_url == enhanced_metadata.repository_url
    
    def test_download_url_generation(self):
        """Test download URL generation."""
        # GitHub repository
        github_metadata = EnhancedPluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test description",
            author="Test Author",
            entry_point="test_plugin:TestPlugin",
            repository_url="https://github.com/user/test-plugin",
        )
        
        download_url = github_metadata.get_download_url()
        assert download_url == "https://github.com/user/test-plugin/archive/refs/heads/main.zip"
        
        # GitLab repository
        gitlab_metadata = EnhancedPluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test description",
            author="Test Author",
            entry_point="test_plugin:TestPlugin",
            repository_url="https://gitlab.com/user/test-plugin",
        )
        
        download_url = gitlab_metadata.get_download_url()
        assert download_url == "https://gitlab.com/user/test-plugin/-/archive/main/archive.zip"
    
    def test_compatibility_checking(self):
        """Test plugin compatibility checking."""
        compatible_metadata = EnhancedPluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test description",
            author="Test Author",
            entry_point="test_plugin:TestPlugin",
            compatibility={
                "python_version": "3.8",
                "os": ["linux", "darwin"],
            },
        )
        
        # Compatible system
        system_info = {
            "python_version": "3.8.10",
            "os": "linux",
        }
        
        assert compatible_metadata.is_compatible_with(system_info) is True
        
        # Incompatible system
        incompatible_system = {
            "python_version": "3.7.5",
            "os": "linux",
        }
        
        assert compatible_metadata.is_compatible_with(incompatible_system) is False


class TestMetadataProviderConfig:
    """Test MetadataProviderConfig model."""
    
    def test_http_json_config(self):
        """Test HTTP JSON provider configuration."""
        config = MetadataProviderConfig(
            provider_type=MetadataProviderType.HTTP_JSON,
            name="test-http-provider",
            description="Test HTTP provider",
            base_url="https://example.com/api",
            cache_enabled=True,
            cache_ttl=3600,
            enabled=True,
            priority=80,
        )
        
        assert config.provider_type == MetadataProviderType.HTTP_JSON
        assert config.base_url == "https://example.com/api"
        assert config.cache_enabled is True
        assert config.cache_ttl == 3600
        assert config.enabled is True
        assert config.priority == 80
    
    def test_git_repository_config(self):
        """Test Git repository provider configuration."""
        config = MetadataProviderConfig(
            provider_type=MetadataProviderType.GIT_REPOSITORY,
            name="test-git-provider",
            description="Test Git provider",
            repository_url="https://github.com/test/repo.git",
            auth_token="test-token",
            cache_enabled=True,
            enabled=True,
        )
        
        assert config.provider_type == MetadataProviderType.GIT_REPOSITORY
        assert config.repository_url == "https://github.com/test/repo.git"
        assert config.auth_token == "test-token"
        assert config.cache_enabled is True
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        # Valid configuration
        valid_config = MetadataProviderConfig(
            provider_type=MetadataProviderType.HTTP_JSON,
            name="valid-provider",
            base_url="https://example.com",
        )
        assert valid_config.enabled is True
        assert valid_config.priority == 50
        
        # Configuration with custom values
        custom_config = MetadataProviderConfig(
            provider_type=MetadataProviderType.GIT_REPOSITORY,
            name="custom-provider",
            enabled=False,
            priority=25,
        )
        assert custom_config.enabled is False
        assert custom_config.priority == 25


class TestHTTPJSONIndexProvider:
    """Test HTTPJSONIndexProvider functionality."""
    
    @pytest.fixture
    def provider_config(self):
        """Create a test provider configuration."""
        return MetadataProviderConfig(
            provider_type=MetadataProviderType.HTTP_JSON,
            name="test-http-provider",
            description="Test HTTP provider",
            base_url="https://api.test.com",
            cache_enabled=True,
            cache_ttl=300,  # 5 minutes
            enabled=True,
            priority=80,
        )
    
    @pytest.fixture
    def provider(self, provider_config):
        """Create an HTTP JSON provider instance."""
        return HTTPJSONIndexProvider(provider_config)
    
    @pytest.mark.asyncio
    async def test_provider_initialization(self, provider):
        """Test provider initialization."""
        assert provider.config.name == "test-http-provider"
        assert provider.config.provider_type == MetadataProviderType.HTTP_JSON
        assert provider.config.base_url == "https://api.test.com"
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_plugin_discovery_success(self, mock_get, provider):
        """Test successful plugin discovery."""
        # Mock response data
        mock_response_data = [
            {
                "name": "test-plugin-1",
                "version": "1.0.0",
                "description": "Test plugin 1",
                "author": "Test Author 1",
                "entry_point": "plugin1:Plugin1",
            },
            {
                "name": "test-plugin-2",
                "version": "2.0.0",
                "description": "Test plugin 2",
                "author": "Test Author 2",
                "entry_point": "plugin2:Plugin2",
            },
        ]
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value=mock_response_data)
        mock_get.return_value.__aenter__.return_value = mock_response
        
        async with provider:
            plugins = await provider.discover_plugins()
            
            assert len(plugins) == 2
            assert plugins[0].name == "test-plugin-1"
            assert plugins[0].version == "1.0.0"
            assert plugins[1].name == "test-plugin-2"
            assert plugins[1].version == "2.0.0"
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_plugin_discovery_with_query(self, mock_get, provider):
        """Test plugin discovery with query."""
        mock_response_data = [
            {
                "name": "search-plugin",
                "version": "1.0.0",
                "description": "Plugin with search term",
                "author": "Test Author",
                "entry_point": "search:SearchPlugin",
            }
        ]
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value=mock_response_data)
        mock_get.return_value.__aenter__.return_value = mock_response
        
        async with provider:
            plugins = await provider.discover_plugins("search")
            
            assert len(plugins) == 1
            assert "search" in plugins[0].name.lower()
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_network_error_handling(self, mock_get, provider):
        """Test network error handling."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_get.return_value.__aenter__.return_value = mock_response
        
        async with provider:
            plugins = await provider.discover_plugins()
            
            assert len(plugins) == 0
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_provider_info(self, mock_get, provider):
        """Test provider info retrieval."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value=[])
        mock_get.return_value.__aenter__.return_value = mock_response
        
        async with provider:
            info = provider.get_provider_info()
            
            assert info["name"] == "test-http-provider"
            assert info["type"] == MetadataProviderType.HTTP_JSON
            assert info["base_url"] == "https://api.test.com"
            assert info["enabled"] is True
            assert info["cache_enabled"] is True


class TestGitRepositoryProvider:
    """Test GitRepositoryProvider functionality."""
    
    @pytest.fixture
    def provider_config(self):
        """Create a test provider configuration."""
        return MetadataProviderConfig(
            provider_type=MetadataProviderType.GIT_REPOSITORY,
            name="test-git-provider",
            description="Test Git provider",
            repository_url="https://github.com/test/repo.git",
            cache_enabled=True,
            cache_ttl=300,
            enabled=True,
            priority=90,
        )
    
    @pytest.fixture
    def provider(self, provider_config):
        """Create a Git repository provider instance."""
        return GitRepositoryProvider(provider_config)
    
    @pytest.mark.asyncio
    async def test_provider_initialization(self, provider):
        """Test provider initialization."""
        assert provider.config.name == "test-git-provider"
        assert provider.config.provider_type == MetadataProviderType.GIT_REPOSITORY
        assert provider.config.repository_url == "https://github.com/test/repo.git"
    
    @pytest.mark.asyncio
    async def test_temp_dir_management(self, provider):
        """Test temporary directory management."""
        await provider._ensure_temp_dir()
        assert provider._temp_dir is not None
        assert provider._temp_dir.exists()
        
        await provider._cleanup_temp_dir()
        # Note: cleanup might not immediately delete the directory in all cases
    
    def test_repo_name_extraction(self, provider):
        """Test repository name extraction from URL."""
        # GitHub
        github_name = provider._get_repo_name_from_url("https://github.com/user/repo-name.git")
        assert github_name == "user_repo-name"
        
        # GitLab
        gitlab_name = provider._get_repo_name_from_url("https://gitlab.com/group/project-name.git")
        assert gitlab_name == "group_project-name"
        
        # Generic
        generic_name = provider._get_repo_name_from_url("https://example.com/git/repo.git")
        assert generic_name == "repo"
    
    @pytest.mark.asyncio
    async def test_metadata_file_parsing(self, provider):
        """Test metadata file parsing."""
        # Test JSON metadata parsing
        json_content = json.dumps({
            "name": "test-plugin",
            "version": "1.0.0",
            "description": "Test plugin",
            "author": "Test Author",
            "entry_point": "test:TestPlugin",
        })
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(json_content)
            temp_file = Path(f.name)
        
        try:
            metadata = provider._parse_metadata_file(temp_file)
            
            assert metadata["name"] == "test-plugin"
            assert metadata["version"] == "1.0.0"
            assert metadata["description"] == "Test plugin"
            assert metadata["author"] == "Test Author"
            assert metadata["entry_point"] == "test:TestPlugin"
        
        finally:
            temp_file.unlink()
    
    @pytest.mark.asyncio
    async def test_entry_point_determination(self, provider):
        """Test entry point determination."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a plugin directory structure
            plugin_dir = temp_path / "test-plugin"
            plugin_dir.mkdir()
            
            # Create __init__.py file
            init_file = plugin_dir / "__init__.py"
            init_file.write_text("# Test plugin")
            
            # Test entry point determination
            entry_point = provider._determine_entry_point(temp_path, "test-plugin", {})
            
            assert "test_plugin" in entry_point
            assert "TestPlugin" in entry_point


class TestMetadataProviderManager:
    """Test MetadataProviderManager functionality."""
    
    @pytest.fixture
    def temp_db_url(self):
        """Create a temporary database URL."""
        import tempfile
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        return f"sqlite:///{temp_db.name}"
    
    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary configuration file."""
        import tempfile
        config_data = {
            "providers": [
                {
                    "name": "test-http-provider",
                    "provider_type": "http_json",
                    "description": "Test HTTP provider",
                    "base_url": "https://api.test.com",
                    "enabled": True,
                    "priority": 80,
                },
                {
                    "name": "test-git-provider",
                    "provider_type": "git_repository",
                    "description": "Test Git provider",
                    "repository_url": "https://github.com/test/repo.git",
                    "enabled": True,
                    "priority": 90,
                },
            ],
            "global_settings": {
                "cache_enabled": True,
                "cache_ttl": 3600,
                "parallel_discovery": True,
                "max_workers": 5,
            }
        }
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(config_data, temp_file, indent=2)
        temp_file.close()
        
        return temp_file.name
    
    @pytest.mark.asyncio
    async def test_manager_initialization(self, temp_db_url, temp_config_file):
        """Test metadata provider manager initialization."""
        manager = MetadataProviderManager(temp_config_file, temp_db_url)
        
        try:
            await manager.initialize()
            
            assert manager._config_loaded is True
            assert manager._enable_caching is True
            assert manager._cache_ttl == 3600
            assert manager._parallel_discovery is True
            assert manager._max_workers == 5
        
        finally:
            await manager.close()
    
    @pytest.mark.asyncio
    async def test_configuration_loading(self, temp_db_url, temp_config_file):
        """Test configuration loading."""
        manager = MetadataProviderManager(temp_config_file, temp_db_url)
        
        try:
            await manager.initialize()
            
            # Check provider configurations are loaded
            assert len(manager._provider_configs) >= 2
            
            # Check HTTP provider
            http_config = manager._provider_configs.get("test-http-provider")
            assert http_config is not None
            assert http_config.provider_type == MetadataProviderType.HTTP_JSON
            assert http_config.base_url == "https://api.test.com"
            
            # Check Git provider
            git_config = manager._provider_configs.get("test-git-provider")
            assert git_config is not None
            assert git_config.provider_type == MetadataProviderType.GIT_REPOSITORY
            assert git_config.repository_url == "https://github.com/test/repo.git"
        
        finally:
            await manager.close()
    
    @pytest.mark.asyncio
    async def test_plugin_discovery_with_mock_providers(self, temp_db_url, temp_config_file):
        """Test plugin discovery with mocked providers."""
        manager = MetadataProviderManager(temp_config_file, temp_db_url)
        
        try:
            await manager.initialize()
            
            # Mock the discover_plugins method for each provider
            mock_plugin_1 = EnhancedPluginMetadata(
                name="mock-plugin-1",
                version="1.0.0",
                description="Mock plugin 1",
                author="Mock Author",
                entry_point="mock1:MockPlugin1",
            )
            
            _mock_plugin_2 = EnhancedPluginMetadata(
                name="mock-plugin-2",
                version="2.0.0",
                description="Mock plugin 2",
                author="Mock Author",
                entry_point="mock2:MockPlugin2",
            )
            
            # Mock provider discovery
            with patch.object(manager._providers['test-http-provider'], 'discover_plugins') as mock_discover:
                mock_discover.return_value = [mock_plugin_1]
                
                plugins = await manager.discover_plugins()
                
                assert len(plugins) == 1
                assert plugins[0].name == "mock-plugin-1"
        
        finally:
            await manager.close()
    
    @pytest.mark.asyncio
    async def test_provider_validation(self, temp_db_url, temp_config_file):
        """Test provider validation."""
        manager = MetadataProviderManager(temp_config_file, temp_db_url)
        
        try:
            await manager.initialize()
            
            # Mock validation method
            with patch.object(manager._providers['test-http-provider'], 'validate_provider_config') as mock_validate:
                mock_validate.return_value = True
                
                results = await manager.validate_all_providers()
                
                assert 'test-http-provider' in results
                assert results['test-http-provider'] is True
        
        finally:
            await manager.close()
    
    @pytest.mark.asyncio
    async def test_cache_management(self, temp_db_url, temp_config_file):
        """Test cache management."""
        manager = MetadataProviderManager(temp_config_file, temp_db_url)
        
        try:
            await manager.initialize()
            
            # Create test metadata
            test_metadata = EnhancedPluginMetadata(
                name="cache-test-plugin",
                version="1.0.0",
                description="Test plugin for caching",
                author="Test Author",
                entry_point="cache_test:CacheTestPlugin",
            )
            
            # Test in-memory caching
            await manager._cache_plugins([test_metadata], "test-provider")
            
            # Check if metadata is cached
            cache_key = "cache-test-plugin:latest"
            assert cache_key in manager._metadata_cache
            assert manager._metadata_cache[cache_key].name == "cache-test-plugin"
            
            # Test cache clearing
            await manager.clear_cache()
            
            # Check cache is cleared
            assert len(manager._metadata_cache) == 0
        
        finally:
            await manager.close()
    
    @pytest.mark.asyncio
    async def test_configuration_save_and_load(self, temp_db_url, temp_config_file):
        """Test configuration persistence."""
        manager = MetadataProviderManager(temp_config_file, temp_db_url)
        
        try:
            await manager.initialize()
            
            # Modify configuration
            manager._cache_ttl = 7200  # 2 hours
            manager._enable_caching = False
            
            # Save configuration
            await manager.save_configuration()
            
            # Create new manager instance
            new_manager = MetadataProviderManager(temp_config_file, temp_db_url)
            await new_manager.initialize()
            
            # Check configuration is loaded
            assert new_manager._cache_ttl == 7200
            assert new_manager._enable_caching is False
        
        finally:
            await manager.close()
            await new_manager.close()


class TestProviderFactoryFunctions:
    """Test provider factory functions."""
    
    def test_create_http_json_provider(self):
        """Test HTTP JSON provider creation."""
        config_data = {
            "name": "factory-test-http",
            "description": "Factory test HTTP provider",
            "base_url": "https://factory.test.com",
            "enabled": True,
            "priority": 70,
        }
        
        provider = create_http_json_provider(config_data)
        
        assert isinstance(provider, HTTPJSONIndexProvider)
        assert provider.config.name == "factory-test-http"
        assert provider.config.provider_type == MetadataProviderType.HTTP_JSON
        assert provider.config.base_url == "https://factory.test.com"
    
    def test_create_git_repository_provider(self):
        """Test Git repository provider creation."""
        config_data = {
            "name": "factory-test-git",
            "description": "Factory test Git provider",
            "repository_url": "https://github.com/factory/test.git",
            "enabled": True,
            "priority": 75,
        }
        
        provider = create_git_repository_provider(config_data)
        
        assert isinstance(provider, GitRepositoryProvider)
        assert provider.config.name == "factory-test-git"
        assert provider.config.provider_type == MetadataProviderType.GIT_REPOSITORY
        assert provider.config.repository_url == "https://github.com/factory/test.git"


class TestConfigurationTemplates:
    """Test configuration templates and defaults."""
    
    def test_default_config_template(self):
        """Test default configuration template."""
        assert "providers" in DEFAULT_CONFIG_TEMPLATE
        assert "global_settings" in DEFAULT_CONFIG_TEMPLATE
        
        # Check providers exist
        providers = DEFAULT_CONFIG_TEMPLATE["providers"]
        assert len(providers) >= 2
        
        # Check global settings exist
        global_settings = DEFAULT_CONFIG_TEMPLATE["global_settings"]
        assert "cache_enabled" in global_settings
        assert "cache_ttl" in global_settings
        assert "parallel_discovery" in global_settings
        assert "max_workers" in global_settings
        
        assert global_settings["cache_enabled"] is True
        assert isinstance(global_settings["cache_ttl"], int)
        assert global_settings["parallel_discovery"] is True
        assert global_settings["max_workers"] == 5
    
    def test_config_template_validity(self):
        """Test that default configuration template is valid."""
        # Try to create a manager with default configuration
        config_json = json.dumps(DEFAULT_CONFIG_TEMPLATE)
        config_data = json.loads(config_json)
        
        # Should not raise an exception
        providers = config_data.get("providers", [])
        for provider_data in providers:
            # Should be able to create a config object
            config = MetadataProviderConfig.parse_obj(provider_data)
            assert config.name is not None
            assert config.provider_type is not None


class TestMetadataParsing:
    """Test metadata parsing functions."""
    
    def test_parse_metadata_from_dict(self):
        """Test parsing metadata from dictionary."""
        metadata_dict = {
            "name": "parse-test-plugin",
            "version": "1.0.0",
            "description": "Parse test plugin",
            "author": "Parse Author",
            "entry_point": "parse_test:ParseTestPlugin",
            "dependencies": ["dependency1", "dependency2"],
        }
        
        metadata = parse_metadata_from_dict(metadata_dict)
        
        assert metadata.name == "parse-test-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Parse test plugin"
        assert metadata.author == "Parse Author"
        assert metadata.entry_point == "parse_test:ParseTestPlugin"
        assert "dependency1" in metadata.dependencies
        assert metadata.source_type == PluginMetadataSource.CUSTOM
    
    def test_parse_metadata_with_legacy_format(self):
        """Test parsing metadata with legacy format (using 'class' instead of 'entry_point')."""
        legacy_metadata_dict = {
            "name": "legacy-test-plugin",
            "version": "1.0.0",
            "description": "Legacy test plugin",
            "author": "Legacy Author",
            "class": "legacy_test:LegacyTestPlugin",
        }
        
        metadata = parse_metadata_from_dict(legacy_metadata_dict)
        
        assert metadata.name == "legacy-test-plugin"
        assert metadata.entry_point == "legacy_test:LegacyTestPlugin"  # Should be converted
    
    def test_parse_metadata_with_source_type(self):
        """Test parsing metadata with specific source type."""
        metadata_dict = {
            "name": "enterprise-test-plugin",
            "version": "1.0.0",
            "description": "Enterprise test plugin",
            "author": "Enterprise Author",
            "entry_point": "enterprise_test:EnterpriseTestPlugin",
        }
        
        metadata = parse_metadata_from_dict(metadata_dict, PluginMetadataSource.ENTERPRISE)
        
        assert metadata.source_type == PluginMetadataSource.ENTERPRISE


class TestMetadataProviderCRUD:
    """Tests for creating, updating, and deleting metadata providers."""

    @pytest.mark.asyncio
    async def test_create_update_delete_provider(self, tmp_path):
        db_path = tmp_path / "providers.db"
        manager = MetadataProviderManager(database_url=f"sqlite:///{db_path}")
        await manager.initialize()

        try:
            provider_config = MetadataProviderConfig(
                name="crud-provider",
                provider_type=MetadataProviderType.HTTP_JSON,
                description="CRUD provider",
                base_url="https://example.com",
                enabled=True,
                priority=60,
                cache_enabled=False,
            )

            fake_provider = AsyncMock()
            create_mock = AsyncMock(return_value=fake_provider)
            with patch.object(manager, "_create_provider", create_mock):
                created = await manager.create_provider(provider_config)

            assert created.name == "crud-provider"
            create_mock.assert_awaited_once()
            assert manager._providers["crud-provider"] is fake_provider

            config_snapshot, stats = await manager.get_provider_details("crud-provider")
            assert config_snapshot.name == "crud-provider"
            assert stats["total_plugins"] == 0

            updates = {"description": "Updated provider", "priority": 80, "enabled": False}
            updated = await manager.update_provider("crud-provider", updates)
            assert updated.priority == 80
            assert updated.enabled is False
            assert "crud-provider" not in manager._providers

            reenable_mock = AsyncMock(return_value=fake_provider)
            with patch.object(manager, "_create_provider", reenable_mock):
                reenabled = await manager.update_provider("crud-provider", {"enabled": True})

            assert reenabled.enabled is True
            reenable_mock.assert_awaited_once()
            assert manager._providers["crud-provider"] is fake_provider

            await manager.delete_provider("crud-provider")
            assert "crud-provider" not in manager._provider_configs
            assert "crud-provider" not in manager._providers

            with pytest.raises(MetadataProviderError):
                await manager.get_provider_details("crud-provider")

        finally:
            await manager.close()


# Integration tests
class TestMetadataProviderIntegration:
    """Integration tests for the complete metadata provider system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_plugin_discovery(self):
        """Test end-to-end plugin discovery workflow."""
        # Create temporary configuration
        config_data = {
            "providers": [
                {
                    "name": "integration-http-provider",
                    "provider_type": "http_json",
                    "description": "Integration test HTTP provider",
                    "base_url": "https://httpbin.org",
                    "enabled": True,
                    "priority": 80,
                    "cache_enabled": False,  # Disable cache for test
                }
            ],
            "global_settings": {
                "cache_enabled": False,
                "parallel_discovery": False,
                "max_workers": 2,
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_url = f"sqlite:///{f.name}"
        
        try:
            manager = MetadataProviderManager(config_path, db_url)
            await manager.initialize()
            
            # Test provider validation
            validation_results = await manager.validate_all_providers()
            assert "integration-http-provider" in validation_results
            
            # Test plugin discovery (should handle network errors gracefully)
            plugins = await manager.discover_plugins()
            
            # Should not crash, may return empty list due to network issues
            assert isinstance(plugins, list)
            
            # Test provider info
            info = manager.get_provider_info()
            assert info["total_providers"] >= 0
            assert "providers" in info
        
        finally:
            await manager.close()
            Path(config_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_rbac_integration(self):
        """Test RBAC integration with metadata providers."""
        # Mock security context
        class MockSecurityContext:
            def __init__(self, permissions):
                self.permissions = permissions
        
        # Create manager
        manager = MetadataProviderManager()
        
        # Set security context with limited permissions
        limited_context = MockSecurityContext(["plugins.read"])
        manager.set_security_context(limited_context)
        
        # Create test plugins with different permission requirements
        public_plugin = EnhancedPluginMetadata(
            name="public-plugin",
            version="1.0.0",
            description="Public plugin",
            author="Public Author",
            entry_point="public:PublicPlugin",
            permissions=["plugins.read"],  # User has this permission
        )
        
        restricted_plugin = EnhancedPluginMetadata(
            name="restricted-plugin",
            version="1.0.0",
            description="Restricted plugin",
            author="Restricted Author",
            entry_point="restricted:RestrictedPlugin",
            permissions=["plugins.admin"],  # User doesn't have this permission
        )
        
        trusted_plugin = EnhancedPluginMetadata(
            name="trusted-plugin",
            version="1.0.0",
            description="Trusted plugin",
            author="Trusted Author",
            entry_point="trusted:TrustedPlugin",
            trusted_source=True,
            permissions=["plugins.trusted.read"],  # User doesn't have this permission
        )
        
        all_plugins = [public_plugin, restricted_plugin, trusted_plugin]
        
        # Filter plugins by permissions
        filtered_plugins = manager._filter_plugins_by_permissions(all_plugins)
        
        # Only public plugin should be accessible
        assert len(filtered_plugins) == 1
        assert filtered_plugins[0].name == "public-plugin"


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])