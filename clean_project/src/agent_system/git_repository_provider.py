"""
Git Repository Provider for Plugin Metadata
Fetches plugin metadata from Git repositories containing plugin definitions
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from .plugin_metadata_models import (
    EnhancedPluginMetadata,
    MetadataProviderConfig,
    MetadataProviderError,
    MetadataProviderType,
    MetadataProviderValidationError,
    PluginMetadataSource,
    parse_metadata_from_dict,
)

logger = logging.getLogger(__name__)


class GitRepositoryProvider:
    """Provider for fetching plugin metadata from Git repositories."""
    
    def __init__(self, config: MetadataProviderConfig):
        self.config = config
        self._temp_dir: Optional[Path] = None
        self._repo_cache: Dict[str, datetime] = {}
        
        # Validate configuration
        if not self.config.repository_url:
            raise MetadataProviderError("repository_url is required for Git provider")
        # After validation, treat as non-optional for internal use
        self._repo_url: str = str(self.config.repository_url)
    
    async def __aenter__(self) -> "GitRepositoryProvider":
        """Async context manager entry."""
        await self._ensure_temp_dir()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._cleanup_temp_dir()
    
    async def _ensure_temp_dir(self) -> None:
        """Ensure temporary directory is created."""
        if self._temp_dir is None:
            self._temp_dir = Path(tempfile.mkdtemp(prefix="plugin_git_provider_"))
            logger.debug(f"Created temp directory: {self._temp_dir}")
    
    async def _cleanup_temp_dir(self) -> None:
        """Clean up temporary directory."""
        if self._temp_dir and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir)
                logger.debug(f"Cleaned up temp directory: {self._temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory {self._temp_dir}: {e}")
    
    def _is_repo_cached(self, repo_url: str) -> bool:
        """Check if repository is cached and not expired."""
        if repo_url not in self._repo_cache:
            return False
        
        cache_time = self._repo_cache[repo_url]
        age = datetime.now(UTC) - cache_time
        
        # Cache for 1 hour by default
        cache_duration = 3600 if self.config.cache_ttl is None else self.config.cache_ttl
        return age.total_seconds() < cache_duration
    
    async def _clone_repository(self, repo_url: str, branch: str = "main") -> Path:
        """Clone a repository to a temporary directory."""
        await self._ensure_temp_dir()
        repo_name = self._get_repo_name_from_url(repo_url)
        temp_dir = self._temp_dir
        if temp_dir is None:
            raise MetadataProviderError("Temporary directory not initialized")
        repo_path = temp_dir / repo_name
        
        # Use cache if available and valid
        if self.config.cache_enabled and self._is_repo_cached(repo_url):
            logger.debug(f"Using cached repository: {repo_url}")
            # Update the cache timestamp
            self._repo_cache[repo_url] = datetime.now(UTC)
            return repo_path
        
        # Remove existing directory if it exists
        if repo_path.exists():
            shutil.rmtree(repo_path)
        
        try:
            # Build git clone command
            cmd = ["git", "clone", "--depth=1", "--branch", branch]
            
            # Add authentication if provided
            if self.config.auth_token:
                # GitHub/GitLab token authentication
                if "github.com" in repo_url:
                    auth_url = repo_url.replace("https://", f"https://{self.config.auth_token}@")
                elif "gitlab.com" in repo_url:
                    auth_url = repo_url.replace("https://", f"https://oauth2:{self.config.auth_token}@")
                else:
                    auth_url = f"https://{self.config.auth_token}@{repo_url}"
                cmd[-1] = auth_url
            elif self.config.username and self.config.password:
                auth_url = f"https://{self.config.username}:{self.config.password}@{repo_url}"
                cmd[-1] = auth_url
            
            cmd.append(str(repo_path))
            
            # Execute git clone
            logger.info(f"Cloning repository: {repo_url}")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown git error"
                raise MetadataProviderError(f"Git clone failed: {error_msg}")
            
            # Cache the repository
            self._repo_cache[repo_url] = datetime.now(UTC)
            logger.info(f"Successfully cloned repository: {repo_url}")
            
            return repo_path
        
        except Exception as e:
            logger.error(f"Failed to clone repository {repo_url}: {e}")
            raise MetadataProviderError(f"Failed to clone repository: {e}")
    
    def _get_repo_name_from_url(self, repo_url: str) -> str:
        """Extract repository name from URL."""
        # Handle different Git hosting platforms
        if "github.com" in repo_url:
            path = repo_url.split("github.com/")[-1]
            return path.replace("/", "_").replace(".git", "")
        elif "gitlab.com" in repo_url:
            path = repo_url.split("gitlab.com/")[-1]
            return path.replace("/", "_").replace(".git", "")
        elif "bitbucket.org" in repo_url:
            path = repo_url.split("bitbucket.org/")[-1]
            return path.replace("/", "_")
        else:
            # Generic handling
            return repo_url.split("/")[-1].replace(".git", "")
    
    def _find_metadata_files(self, repo_path: Path) -> List[Path]:
        """Find plugin metadata files in the repository."""
        metadata_files = []
        
        # Common plugin metadata file names and locations
        metadata_patterns = [
            # Root level files
            "plugin.json",
            "plugins.json", 
            "metadata.json",
            "package.json",
            "pyproject.toml",
            "setup.py",
            "Cargo.toml",
            "composer.json",
            
            # Plugin-specific directories
            "plugins/**/plugin.json",
            "plugins/**/metadata.json",
            "plugins/**/package.json",
            "src/**/plugin.json",
            "src/**/metadata.json",
            
            # Nested configurations
            "**/plugin.json",
            "**/metadata.json",
            "**/plugins.json",
        ]
        
        for pattern in metadata_patterns:
            if "**" in pattern:
                # Handle glob patterns
                for file_path in repo_path.glob(pattern):
                    if file_path.is_file():
                        metadata_files.append(file_path)
            else:
                # Handle simple paths
                file_path = repo_path / pattern
                if file_path.exists():
                    metadata_files.append(file_path)
        
        return list(set(metadata_files))  # Remove duplicates
    
    def _parse_metadata_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse metadata from a plugin file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            
            if file_path.name == "pyproject.toml":
                return self._parse_toml_metadata(content, file_path)
            elif file_path.name == "setup.py":
                return self._parse_python_setup_metadata(content, file_path)
            elif file_path.name == "Cargo.toml":
                return self._parse_cargo_metadata(content, file_path)
            elif file_path.name == "composer.json":
                return self._parse_composer_metadata(content, file_path)
            else:
                # Assume JSON format
                data = json.loads(content)
                return data if isinstance(data, dict) else None
        
        except Exception as e:
            logger.warning(f"Failed to parse metadata file {file_path}: {e}")
            return None
    
    def _parse_toml_metadata(self, content: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse TOML metadata from pyproject.toml."""
        try:
            import importlib
            try:
                tomllib = importlib.import_module("tomllib")
            except ModuleNotFoundError:
                try:
                    tomllib = importlib.import_module("tomli")
                except ModuleNotFoundError:
                    logger.warning("TOML parsing not available, skipping pyproject.toml")
                    return None
        
            data = cast(Any, tomllib).loads(content)
            metadata = {}
            
            # Extract from [tool.poetry] or [project] section
            if "tool" in data and "poetry" in data["tool"]:
                poetry_data = data["tool"]["poetry"]
                metadata["name"] = poetry_data.get("name")
                metadata["version"] = poetry_data.get("version")
                metadata["description"] = poetry_data.get("description")
                metadata["author"] = poetry_data.get("authors", [{}])[0] if poetry_data.get("authors") else None
                metadata["dependencies"] = list(poetry_data.get("dependencies", {}).keys())
                metadata["repository_url"] = poetry_data.get("repository")
                metadata["homepage"] = poetry_data.get("homepage")
                metadata["keywords"] = poetry_data.get("keywords", [])
            elif "project" in data:
                project_data = data["project"]
                metadata["name"] = project_data.get("name")
                metadata["version"] = project_data.get("version")
                metadata["description"] = project_data.get("description")
                metadata["author"] = project_data.get("authors", [{}])[0] if project_data.get("authors") else None
                metadata["dependencies"] = list(project_data.get("dependencies", {}).keys())
                metadata["repository_url"] = project_data.get("urls", {}).get("repository")
                metadata["homepage"] = project_data.get("urls", {}).get("homepage")
                metadata["keywords"] = project_data.get("keywords", [])
            
            return metadata if metadata.get("name") else None
        
        except Exception as e:
            logger.warning(f"Failed to parse TOML content: {e}")
            return None
    
    def _parse_python_setup_metadata(self, content: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse metadata from setup.py file."""
        # This is a simplified parser - real implementation would be more robust
        try:
            metadata = {}
            
            # Look for setup() function call and extract arguments
            lines = content.split("\n")
            in_setup = False
            setup_args = {}
            
            for line in lines:
                line = line.strip()
                if "setup(" in line:
                    in_setup = True
                elif in_setup and ")" in line:
                    in_setup = False
                elif in_setup and "=" in line:
                    # Simple key=value extraction (very basic)
                    if '"' in line or "'" in line:
                        # Extract quoted string value
                        start_quote = max(line.find('"'), line.find("'"))
                        end_quote = line.rfind(line[start_quote])
                        if start_quote != -1 and end_quote != -1:
                            key = line.split("=")[0].strip()
                            value = line[start_quote+1:end_quote]
                            setup_args[key] = value
            
            # Map to our metadata format
            metadata["name"] = setup_args.get("name")
            metadata["version"] = setup_args.get("version")
            metadata["description"] = setup_args.get("description")
            metadata["author"] = setup_args.get("author")
            metadata["author_email"] = setup_args.get("author_email")
            metadata["url"] = setup_args.get("url")
            metadata["repository_url"] = setup_args.get("repository") or setup_args.get("url")
            
            return metadata if metadata.get("name") else None
        
        except Exception as e:
            logger.warning(f"Failed to parse setup.py: {e}")
            return None
    
    def _parse_cargo_metadata(self, content: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse metadata from Cargo.toml file."""
        try:
            import importlib
            try:
                tomllib = importlib.import_module("tomllib")
            except ModuleNotFoundError:
                try:
                    tomllib = importlib.import_module("tomli")
                except ModuleNotFoundError:
                    logger.warning("TOML parsing not available, skipping Cargo.toml")
                    return None
        
            data = cast(Any, tomllib).loads(content)
            
            if "package" in data:
                pkg_data = data["package"]
                metadata = {
                    "name": pkg_data.get("name"),
                    "version": pkg_data.get("version"),
                    "description": pkg_data.get("description"),
                    "author": pkg_data.get("authors", [{}])[0] if pkg_data.get("authors") else None,
                    "repository_url": pkg_data.get("repository"),
                    "homepage": pkg_data.get("homepage"),
                    "keywords": pkg_data.get("keywords", []),
                }
                return metadata if metadata.get("name") else None
            
            return None
        
        except Exception as e:
            logger.warning(f"Failed to parse Cargo.toml: {e}")
            return None
    
    def _parse_composer_metadata(self, content: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse metadata from composer.json file."""
        try:
            data = json.loads(content)
            
            metadata = {
                "name": data.get("name"),
                "version": data.get("version"),
                "description": data.get("description"),
                "author": data.get("authors", [{}])[0] if data.get("authors") else None,
                "repository_url": data.get("repository", {}).get("url") if isinstance(data.get("repository"), dict) else data.get("repository"),
                "homepage": data.get("homepage"),
                "keywords": data.get("keywords", []),
                "dependencies": list(data.get("require", {}).keys()) if data.get("require") else [],
            }
            
            return metadata if metadata.get("name") else None
        
        except Exception as e:
            logger.warning(f"Failed to parse composer.json: {e}")
            return None
    
    def _determine_entry_point(self, repo_path: Path, plugin_name: str, metadata: Dict[str, Any]) -> str:
        """Determine the entry point for the plugin."""
        # Check if entry_point is explicitly defined
        if "entry_point" in metadata:
            return str(metadata["entry_point"])
        
        # Look for common entry point patterns
        entry_patterns = [
            f"{plugin_name}/__init__.py",  # raw name with hyphen
            f"{plugin_name.replace('-', '_')}/__init__.py",
            f"src/{plugin_name}/__init__.py",
            f"src/{plugin_name.replace('-', '_')}/__init__.py",
            f"lib/{plugin_name}/__init__.py",
            f"lib/{plugin_name.replace('-', '_')}/__init__.py",
            "main.py",
            "app.py",
            "__init__.py",
        ]
        
        for pattern in entry_patterns:
            entry_path = repo_path / pattern
            if entry_path.exists():
                module_path = str(entry_path).replace("/", ".").replace(".py", "")
                module_path = module_path.replace("-", "_")
                # Build CamelCase class name without underscores
                import re as _re
                parts = [p for p in _re.split(r"[-_]", plugin_name) if p]
                class_base = "".join(part.capitalize() for part in parts)
                class_name = f"{class_base}Plugin"
                return f"{module_path}:{class_name}"
        
        # Fallback to plugin name with default class
        return f"{plugin_name.replace('-', '_')}:{plugin_name.replace('-', '_').title()}Plugin"
    
    async def discover_plugins(self, query: Optional[str] = None) -> List[EnhancedPluginMetadata]:
        """Discover plugins from the Git repository."""
        logger.info(f"Discovering plugins from Git repository: {self._repo_url}")
        
        try:
            repo_path = await self._clone_repository(self._repo_url)
            metadata_files = self._find_metadata_files(repo_path)
            
            if not metadata_files:
                logger.warning(f"No plugin metadata files found in repository: {self._repo_url}")
                return []
            
            enhanced_plugins = []
            
            for file_path in metadata_files:
                try:
                    raw_metadata = self._parse_metadata_file(file_path)
                    if not raw_metadata:
                        continue
                    
                    # Skip if name doesn't match query
                    if query and query.lower() not in raw_metadata.get("name", "").lower():
                        continue
                    
                    # Enhance metadata
                    enhanced_plugin = await self._enhance_plugin_metadata(raw_metadata, repo_path, file_path)
                    if enhanced_plugin:
                        enhanced_plugins.append(enhanced_plugin)
                
                except Exception as e:
                    logger.warning(f"Failed to process metadata file {file_path}: {e}")
                    continue
            
            logger.info(f"Successfully discovered {len(enhanced_plugins)} plugins from repository")
            return enhanced_plugins
        
        except Exception as e:
            logger.error(f"Plugin discovery failed: {e}")
            raise MetadataProviderError(f"Plugin discovery failed: {e}")
    
    async def get_plugin_metadata(self, plugin_name: str, version: Optional[str] = None) -> Optional[EnhancedPluginMetadata]:
        """Get metadata for specific plugin from repository."""
        logger.debug(f"Getting metadata for plugin: {plugin_name}:{version or 'latest'}")
        
        try:
            repo_path = await self._clone_repository(self._repo_url)
            metadata_files = self._find_metadata_files(repo_path)
            
            for file_path in metadata_files:
                raw_metadata = self._parse_metadata_file(file_path)
                
                if raw_metadata and raw_metadata.get("name") == plugin_name:
                    # Check version if specified
                    if version and raw_metadata.get("version") != version:
                        continue
                    
                    enhanced_plugin = await self._enhance_plugin_metadata(raw_metadata, repo_path, file_path)
                    return enhanced_plugin
            
            logger.warning(f"Plugin {plugin_name} not found in repository")
            return None
        
        except Exception as e:
            logger.error(f"Failed to get plugin metadata for {plugin_name}:{e}")
            raise MetadataProviderError(f"Failed to get plugin metadata: {e}")
    
    async def _enhance_plugin_metadata(self, raw_metadata: Dict[str, Any], repo_path: Path, file_path: Path) -> Optional[EnhancedPluginMetadata]:
        """Enhance raw plugin data with repository-specific information."""
        try:
            # Create enhanced metadata with repository defaults
            enhanced_data = raw_metadata.copy()
            
            # Add provider-specific information
            enhanced_data["source_type"] = PluginMetadataSource.LOCAL
            enhanced_data["provider_type"] = MetadataProviderType.GIT_REPOSITORY
            enhanced_data["provider_config"] = self.config.model_dump(exclude={"auth_token", "api_key", "password"})
            
            # Add repository information
            enhanced_data["repository_url"] = self._repo_url
            enhanced_data["homepage"] = enhanced_data.get("homepage") or self._repo_url
            
            # Determine entry point
            plugin_name = enhanced_data.get("name", "")
            if plugin_name:
                enhanced_data["entry_point"] = self._determine_entry_point(repo_path, plugin_name, enhanced_data)
            
            # Add file path information
            enhanced_data["metadata_file_path"] = str(file_path.relative_to(repo_path))
            enhanced_data["last_validated"] = datetime.now(UTC)
            
            # Parse using the enhanced model
            enhanced_plugin = parse_metadata_from_dict(enhanced_data, PluginMetadataSource.LOCAL)
            
            # Add repository-specific metadata
            enhanced_plugin.metadata.update({
                "provider_name": self.config.name,
                "repository_url": self._repo_url,
                "metadata_file": enhanced_data["metadata_file_path"],
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
            # Test repository accessibility
            repo_path = await self._clone_repository(self._repo_url)
            
            # Check if repository has plugin metadata files
            metadata_files = self._find_metadata_files(repo_path)
            
            if not metadata_files:
                logger.warning("No plugin metadata files found in repository")
                return False
            
            # Try to parse at least one metadata file
            test_metadata = self._parse_metadata_file(metadata_files[0])
            if not test_metadata:
                logger.warning("Failed to parse plugin metadata")
                return False
            
            logger.info(f"Provider validation successful: found {len(metadata_files)} metadata files")
            return True
        
        except Exception as e:
            logger.error(f"Provider validation failed: {e}")
            return False
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information."""
        return {
            "name": self.config.name,
            "type": self.config.provider_type,
            "repository_url": self._repo_url,
            "enabled": self.config.enabled,
            "priority": self.config.priority,
            "cache_enabled": self.config.cache_enabled,
            "cache_ttl": self.config.cache_ttl,
            "last_sync": self.config.last_sync.isoformat() if self.config.last_sync else None,
            "sync_errors": self.config.sync_errors,
        }
    
    async def get_repository_info(self) -> Dict[str, Any]:
        """Get information about the repository."""
        try:
            repo_path = await self._clone_repository(self._repo_url)
            
            # Get git information
            git_info: Dict[str, Any] = {}
            
            # Get current branch
            try:
                result = await asyncio.create_subprocess_exec(
                    "git", "branch", "--show-current",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(repo_path),
                )
                stdout, _ = await result.communicate()
                git_info["current_branch"] = stdout.decode().strip() if stdout else "unknown"
            except Exception:
                git_info["current_branch"] = "unknown"
            
            # Get last commit
            try:
                result = await asyncio.create_subprocess_exec(
                    "git", "log", "-1", "--pretty=format:%H|%an|%ad|%s",
                    "--date=iso",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(repo_path),
                )
                stdout, _ = await result.communicate()
                commit_data = stdout.decode().strip().split("|")
                if len(commit_data) == 4:
                    git_info["last_commit"] = {
                        "hash": commit_data[0],
                        "author": commit_data[1],
                        "date": commit_data[2],
                        "message": commit_data[3],
                    }
            except Exception:
                pass
            
            # Count files
            try:
                result = await asyncio.create_subprocess_exec(
                    "git", "ls-files",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(repo_path),
                )
                stdout, _ = await result.communicate()
                file_count = len(stdout.decode().strip().split("\n")) if stdout else 0
                git_info["file_count"] = file_count
            except Exception:
                git_info["file_count"] = 0
            
            return git_info
        
        except Exception as e:
            logger.error(f"Failed to get repository info: {e}")
            return {"error": str(e)}


# Factory function for creating Git repository providers
def create_git_repository_provider(config_data: Dict[str, Any]) -> GitRepositoryProvider:
    """Create Git repository provider from configuration data."""
    config = MetadataProviderConfig.model_validate({
        **config_data,
        "provider_type": MetadataProviderType.GIT_REPOSITORY,
    })
    return GitRepositoryProvider(config)


# Common repository configurations
DEFAULT_REPOSITORY_CONFIGS = {
    "agent_system_plugins": {
        "name": "Agent System Plugins",
        "repository_url": "https://github.com/agent-system/plugins.git",
        "description": "Official Agent System plugin repository",
        "cache_enabled": True,
        "cache_ttl": 1800,
    },
    "enterprise_plugins": {
        "name": "Enterprise Plugin Repository",
        "repository_url": "https://gitlab.com/company/plugins.git",
        "description": "Enterprise plugin repository with private plugins",
        "auth_token": "${GITLAB_TOKEN}",
        "cache_enabled": True,
        "cache_ttl": 3600,
    },
    "community_plugins": {
        "name": "Community Plugin Hub",
        "repository_url": "https://github.com/community/plugins.git",
        "description": "Community-driven plugin collection",
        "cache_enabled": True,
        "cache_ttl": 7200,
    },
}