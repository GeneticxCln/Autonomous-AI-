"""
Multi-Region Deployment Support
Handles region-aware routing, data replication, and failover.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Region(str, Enum):
    """Supported regions."""

    US_EAST_1 = "us-east-1"
    US_WEST_2 = "us-west-2"
    EU_WEST_1 = "eu-west-1"
    AP_SOUTHEAST_1 = "ap-southeast-1"


@dataclass
class RegionConfig:
    """Configuration for a region."""

    region: Region
    endpoint: str
    database_url: str
    redis_url: str
    active: bool = True
    priority: int = 0  # Lower number = higher priority
    latency_ms: Optional[float] = None


class MultiRegionManager:
    """Manages multi-region deployment and routing."""

    def __init__(self) -> None:
        self.current_region = self._detect_region()
        self.regions: Dict[Region, RegionConfig] = {}
        self._region_health: Dict[Region, bool] = {}
        self._latency_cache: Dict[Region, float] = {}
        self._initialized = False

    def _detect_region(self) -> Region:
        """Detect current region from environment."""
        region_env = os.getenv("AWS_REGION")
        region_str: str = region_env if region_env is not None else os.getenv("REGION", "us-east-1")
        try:
            return Region(region_str.lower())
        except ValueError:
            logger.warning(f"Unknown region {region_str}, defaulting to us-east-1")
            return Region.US_EAST_1

    async def initialize(self) -> None:
        """Initialize multi-region configuration."""
        if self._initialized:
            return

        # Load region configurations
        self._load_region_configs()

        # Start health checking
        asyncio.create_task(self._health_check_loop())

        # Measure latency to other regions
        await self._measure_region_latencies()

        self._initialized = True
        logger.info(f"Multi-region manager initialized for region: {self.current_region}")

    def _load_region_configs(self) -> None:
        """Load region configurations from environment or defaults."""
        # Default configurations (can be overridden via environment)
        default_regions = {
            Region.US_EAST_1: RegionConfig(
                region=Region.US_EAST_1,
                endpoint="https://api-us-east-1.example.com",
                database_url=os.getenv("DATABASE_URL_US_EAST_1", ""),
                redis_url=os.getenv("REDIS_URL_US_EAST_1", ""),
                priority=1,
            ),
            Region.US_WEST_2: RegionConfig(
                region=Region.US_WEST_2,
                endpoint="https://api-us-west-2.example.com",
                database_url=os.getenv("DATABASE_URL_US_WEST_2", ""),
                redis_url=os.getenv("REDIS_URL_US_WEST_2", ""),
                priority=2,
            ),
            Region.EU_WEST_1: RegionConfig(
                region=Region.EU_WEST_1,
                endpoint="https://api-eu-west-1.example.com",
                database_url=os.getenv("DATABASE_URL_EU_WEST_1", ""),
                redis_url=os.getenv("REDIS_URL_EU_WEST_1", ""),
                priority=3,
            ),
        }

        # Only include regions with configured endpoints
        for region, config in default_regions.items():
            if config.database_url and config.redis_url:
                self.regions[region] = config
                self._region_health[region] = True

    async def _measure_region_latencies(self) -> None:
        """Measure latency to other regions."""
        for region, config in self.regions.items():
            if region == self.current_region:
                self._latency_cache[region] = 0.0
                continue

            try:
                # Simple latency measurement (ping endpoint)
                import time

                start = time.perf_counter()
                # In production, this would make an actual HTTP request
                await asyncio.sleep(0.01)  # Simulated
                latency = (time.perf_counter() - start) * 1000
                self._latency_cache[region] = latency
                config.latency_ms = latency
            except Exception as e:
                logger.debug(f"Failed to measure latency to {region}: {e}")
                self._latency_cache[region] = float("inf")

    async def _health_check_loop(self) -> None:
        """Periodically check health of all regions."""
        while True:
            try:
                for region, config in self.regions.items():
                    if region == self.current_region:
                        self._region_health[region] = True
                        continue

                    # Check region health (simplified)
                    # In production, this would check actual endpoints
                    self._region_health[region] = config.active

                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    def get_preferred_region(self, user_region: Optional[Region] = None) -> Region:
        """Get preferred region for a request."""
        if user_region and user_region in self.regions:
            if self._region_health.get(user_region, False):
                return user_region

        # Return current region if healthy
        if self._region_health.get(self.current_region, True):
            return self.current_region

        # Find nearest healthy region
        healthy_regions = [
            (region, config)
            for region, config in self.regions.items()
            if self._region_health.get(region, False)
        ]

        if not healthy_regions:
            # Fallback to current region
            return self.current_region

        # Sort by latency
        healthy_regions.sort(key=lambda x: self._latency_cache.get(x[0], float("inf")))
        return healthy_regions[0][0]

    def get_region_config(self, region: Region) -> Optional[RegionConfig]:
        """Get configuration for a specific region."""
        return self.regions.get(region)

    def is_region_healthy(self, region: Region) -> bool:
        """Check if a region is healthy."""
        return self._region_health.get(region, False)

    async def replicate_data(
        self, data: Dict[str, Any], target_regions: Optional[List[Region]] = None
    ) -> None:
        """Replicate data to other regions."""
        if target_regions is None:
            target_regions = [r for r in self.regions.keys() if r != self.current_region]

        for region in target_regions:
            if not self._region_health.get(region, False):
                logger.warning(f"Skipping replication to unhealthy region: {region}")
                continue

            try:
                config = self.regions.get(region)
                if config:
                    # In production, this would replicate to the region's database
                    logger.debug(f"Replicating data to {region}")
                    # Actual replication logic would go here
            except Exception as e:
                logger.error(f"Failed to replicate to {region}: {e}")

    def get_region_info(self) -> Dict[str, Any]:
        """Get information about all regions."""
        return {
            "current_region": self.current_region.value,
            "regions": {
                region.value: {
                    "endpoint": config.endpoint,
                    "active": config.active,
                    "healthy": self._region_health.get(region, False),
                    "latency_ms": config.latency_ms,
                    "priority": config.priority,
                }
                for region, config in self.regions.items()
            },
        }


# Global multi-region manager instance
multi_region_manager = MultiRegionManager()
