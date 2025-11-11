"""
Enhanced Plugin Ecosystem
Plugin marketplace, versioning, dependency management, and discovery.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

logger = logging.getLogger(__name__)


class PluginStatus(str, Enum):
    """Plugin status."""

    INSTALLED = "installed"
    AVAILABLE = "available"
    UPDATING = "updating"
    ERROR = "error"


@dataclass
class PluginMetadata:
    """Metadata for a plugin."""

    name: str
    version: str
    description: str
    author: str
    dependencies: List[str]
    entry_point: str
    repository_url: Optional[str] = None
    status: PluginStatus = PluginStatus.AVAILABLE
    installed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # metadata is ensured non-None by default_factory; keep guard for safety
        if self.metadata is None:
            self.metadata = {}


class PluginMarketplace:
    """Manages plugin discovery, installation, and versioning."""

    def __init__(self, plugin_dir: str = "./plugins", marketplace_url: Optional[str] = None) -> None:
        self.plugin_dir = Path(plugin_dir)
        self.marketplace_url = marketplace_url or os.getenv("PLUGIN_MARKETPLACE_URL")
        self.plugins: Dict[str, PluginMetadata] = {}
        self.installed_plugins: Dict[str, str] = {}  # name -> version
        self._lock = asyncio.Lock()

    async def discover_plugins(self, query: Optional[str] = None) -> List[PluginMetadata]:
        """Discover available plugins from marketplace."""
        if not self.marketplace_url:
            # Fail fast with clear instructions instead of returning mock data
            raise RuntimeError(
                "PLUGIN_MARKETPLACE_URL not configured. Provide an HTTP JSON index or set a source."
            )

        try:
            # Import requests at runtime to avoid hard dependency on typing stubs
            requests = importlib.import_module("requests")

            resp = requests.get(self.marketplace_url, timeout=10)
            resp.raise_for_status()
            raw = resp.json()
            data = cast(Union[List[Dict[str, Any]], Dict[str, Any]], raw)
            items: List[Dict[str, Any]] = (
                data if isinstance(data, list) else cast(List[Dict[str, Any]], data.get("plugins", []))
            )
            results: List[PluginMetadata] = []
            for item in items:
                try:
                    md = PluginMetadata(
                        name=item["name"],
                        version=item.get("version", "0.0.0"),
                        description=item.get("description", ""),
                        author=item.get("author", "unknown"),
                        dependencies=item.get("dependencies", []),
                        entry_point=item.get("entry_point", ""),
                        repository_url=item.get("repository_url"),
                    )
                    results.append(md)
                except Exception as exc:
                    logger.warning("Skipping invalid plugin metadata: %s", exc)

            if query:
                q = query.lower()
                results = [
                    p for p in results if q in p.name.lower() or q in p.description.lower()
                ]

            return results

        except Exception as e:
            logger.error(f"Failed to discover plugins: {e}")
            return []

    async def install_plugin(
        self,
        name: str,
        version: Optional[str] = None,
        source: Optional[str] = None,
    ) -> bool:
        """Install a plugin."""
        async with self._lock:
            # Check if already installed
            if name in self.installed_plugins:
                if version and self.installed_plugins[name] == version:
                    logger.info(f"Plugin {name}:{version} already installed")
                    return True
                else:
                    logger.warning(
                        f"Plugin {name} already installed with version {self.installed_plugins[name]}"
                    )

            # Get plugin metadata
            if source:
                metadata = await self._load_plugin_from_source(name, version, source)
            else:
                plugins = await self.discover_plugins(query=name)
                if not plugins:
                    logger.error(f"Plugin {name} not found")
                    return False
                metadata = plugins[0]  # Use first match

            if not version:
                version = metadata.version

            # Update status
            metadata.status = PluginStatus.UPDATING

        try:
            # Install dependencies
            if metadata.dependencies:
                await self._install_dependencies(metadata.dependencies)

            # Install plugin
            plugin_path = self.plugin_dir / name / version
            plugin_path.mkdir(parents=True, exist_ok=True)

            # Save metadata
            metadata_file = plugin_path / "metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(
                    {
                        "name": metadata.name,
                        "version": metadata.version,
                        "description": metadata.description,
                        "author": metadata.author,
                        "dependencies": metadata.dependencies,
                        "entry_point": metadata.entry_point,
                    },
                    f,
                    indent=2,
                )

            # In production, this would download and install the actual plugin
            # For now, just mark as installed

            async with self._lock:
                self.plugins[name] = metadata
                self.installed_plugins[name] = version
                metadata.status = PluginStatus.INSTALLED
                import time

                metadata.installed_at = time.time()

            logger.info(f"Plugin {name}:{version} installed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to install plugin {name}:{version}: {e}")
            async with self._lock:
                metadata.status = PluginStatus.ERROR
            return False

    async def uninstall_plugin(self, name: str) -> bool:
        """Uninstall a plugin."""
        async with self._lock:
            if name not in self.installed_plugins:
                logger.warning(f"Plugin {name} not installed")
                return False

            version = self.installed_plugins[name]
            _metadata = self.plugins.get(name)

        try:
            # Remove plugin directory
            plugin_path = self.plugin_dir / name / version
            if plugin_path.exists():
                import shutil

                shutil.rmtree(plugin_path)

            async with self._lock:
                del self.installed_plugins[name]
                if name in self.plugins:
                    del self.plugins[name]

            logger.info(f"Plugin {name}:{version} uninstalled")
            return True

        except Exception as e:
            logger.error(f"Failed to uninstall plugin {name}:{e}")
            return False

    async def update_plugin(self, name: str, version: Optional[str] = None) -> bool:
        """Update a plugin to a newer version."""
        # Get latest version
        plugins = await self.discover_plugins(query=name)
        if not plugins:
            return False

        latest = plugins[0]
        target_version = version or latest.version

        # Uninstall old version
        await self.uninstall_plugin(name)

        # Install new version
        return await self.install_plugin(name, target_version)

    async def _install_dependencies(self, dependencies: List[str]) -> None:
        """Install plugin dependencies."""
        if not dependencies:
            return

        logger.info(f"Installing dependencies: {', '.join(dependencies)}")
        # In production, this would use pip or another package manager
        # For now, just log
        # subprocess.run([sys.executable, "-m", "pip", "install"] + dependencies)

    async def _load_plugin_from_source(
        self,
        name: str,
        version: Optional[str],
        source: str,
    ) -> PluginMetadata:
        """Load plugin metadata from source (git, URL, etc.)."""
        # In production, this would fetch from the source
        # For now, return a basic metadata object
        return PluginMetadata(
            name=name,
            version=version or "1.0.0",
            description=f"Plugin from {source}",
            author="Unknown",
            dependencies=[],
            entry_point=f"{name}:{name.title()}Tool",
            repository_url=source,
        )

    def get_installed_plugins(self) -> Dict[str, str]:
        """Get list of installed plugins."""
        return self.installed_plugins.copy()

    async def get_plugin_info(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Get information about plugins."""
        if name:
            if name not in self.plugins:
                return {}
            metadata = self.plugins[name]
            return {
                "name": metadata.name,
                "version": metadata.version,
                "description": metadata.description,
                "author": metadata.author,
                "dependencies": metadata.dependencies,
                "status": metadata.status.value,
                "installed_at": metadata.installed_at,
            }
        else:
            return {
                name: {
                    "version": metadata.version,
                    "description": metadata.description,
                    "status": metadata.status.value,
                    "installed_at": metadata.installed_at,
                }
                for name, metadata in self.plugins.items()
            }

    def check_dependencies(self, plugin_name: str) -> Dict[str, bool]:
        """Check if plugin dependencies are satisfied."""
        if plugin_name not in self.plugins:
            return {}

        metadata = self.plugins[plugin_name]
        satisfied = {}

        for dep in metadata.dependencies:
            # Check if dependency is installed
            try:
                __import__(dep.split(">=")[0].split("==")[0])
                satisfied[dep] = True
            except ImportError:
                satisfied[dep] = False

        return satisfied


# Global plugin marketplace instance
plugin_marketplace = PluginMarketplace()
