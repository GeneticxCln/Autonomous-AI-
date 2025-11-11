"""
Advanced Caching Strategies
Multi-level caching with cache warming, invalidation, and intelligent eviction.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .cache_manager import cache_manager

logger = logging.getLogger(__name__)


class CacheLevel(str, Enum):
    """Cache levels in the multi-level cache."""

    L1 = "l1"  # In-memory (fastest, smallest)
    L2 = "l2"  # Redis (fast, medium size)
    L3 = "l3"  # Database (slower, largest)


class EvictionPolicy(str, Enum):
    """Cache eviction policies."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live


@dataclass
class CacheEntry:
    """A cache entry with metadata."""

    key: str
    value: Any
    level: CacheLevel
    created_at: float
    accessed_at: float
    access_count: int = 0
    ttl: Optional[float] = None
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.ttl is None:
            return False
        return (time.time() - self.created_at) > self.ttl

    def touch(self) -> None:
        """Update access metadata."""
        self.accessed_at = time.time()
        self.access_count += 1


class MultiLevelCache:
    """Multi-level cache with intelligent eviction and warming."""

    def __init__(
        self,
        l1_size: int = 1000,
        l2_ttl: int = 3600,
        l3_ttl: int = 86400,
        eviction_policy: EvictionPolicy = EvictionPolicy.LRU,
    ):
        self.l1_cache: Dict[str, CacheEntry] = {}  # In-memory
        self.l1_size = l1_size
        self.l2_ttl = l2_ttl
        self.l3_ttl = l3_ttl
        self.eviction_policy = eviction_policy
        self._lock = asyncio.Lock()
        self._warmup_tasks: List[asyncio.Task[None]] = []

    def _make_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
        """Generate a cache key."""
        key_data = {
            "prefix": prefix,
            "args": args,
            "kwargs": sorted(kwargs.items()),
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    async def get(
        self,
        key: str,
        level: Optional[CacheLevel] = None,
    ) -> Optional[Any]:
        """Get value from cache, checking levels in order."""
        # Try L1 first
        if level is None or level == CacheLevel.L1:
            async with self._lock:
                entry = self.l1_cache.get(key)
                if entry and not entry.is_expired():
                    entry.touch()
                    return entry.value
                elif entry:
                    # Expired, remove it
                    del self.l1_cache[key]

        # Try L2 (Redis)
        if level is None or level == CacheLevel.L2:
            try:
                if cache_manager._is_connected:
                    value = await cache_manager.get("mlcache", key)
                    if value is not None:
                        # Promote to L1
                        await self._set_l1(key, value, ttl=self.l2_ttl)
                        return value
            except Exception as e:
                logger.debug(f"L2 cache miss for {key}: {e}")

        # L3 would be database (not implemented here, but could be)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        level: CacheLevel = CacheLevel.L1,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Set value in cache at specified level."""
        if level == CacheLevel.L1:
            await self._set_l1(key, value, ttl=ttl, tags=tags)
        elif level == CacheLevel.L2:
            await self._set_l2(key, value, ttl=ttl or self.l2_ttl)

    async def _set_l1(
        self, key: str, value: Any, ttl: Optional[float] = None, tags: Optional[List[str]] = None
    ) -> None:
        """Set value in L1 cache."""
        async with self._lock:
            # Evict if needed
            if len(self.l1_cache) >= self.l1_size:
                await self._evict_l1()

            entry = CacheEntry(
                key=key,
                value=value,
                level=CacheLevel.L1,
                created_at=time.time(),
                accessed_at=time.time(),
                ttl=ttl,
                tags=tags or [],
            )
            self.l1_cache[key] = entry

    async def _set_l2(self, key: str, value: Any, ttl: float) -> None:
        """Set value in L2 cache (Redis)."""
        try:
            if cache_manager._is_connected:
                await cache_manager.set("mlcache", key, value, ttl=int(ttl))
        except Exception as e:
            logger.debug(f"Failed to set L2 cache for {key}: {e}")

    async def _evict_l1(self) -> None:
        """Evict entries from L1 cache based on policy."""
        if not self.l1_cache:
            return

        if self.eviction_policy == EvictionPolicy.LRU:
            # Remove least recently used
            sorted_entries = sorted(self.l1_cache.items(), key=lambda x: x[1].accessed_at)
            key_to_remove = sorted_entries[0][0]
            del self.l1_cache[key_to_remove]

        elif self.eviction_policy == EvictionPolicy.LFU:
            # Remove least frequently used
            sorted_entries = sorted(self.l1_cache.items(), key=lambda x: x[1].access_count)
            key_to_remove = sorted_entries[0][0]
            del self.l1_cache[key_to_remove]

        elif self.eviction_policy == EvictionPolicy.FIFO:
            # Remove oldest
            sorted_entries = sorted(self.l1_cache.items(), key=lambda x: x[1].created_at)
            key_to_remove = sorted_entries[0][0]
            del self.l1_cache[key_to_remove]

    async def invalidate(self, pattern: Optional[str] = None, tags: Optional[List[str]] = None) -> None:
        """Invalidate cache entries by pattern or tags."""
        async with self._lock:
            if pattern:
                # Invalidate by key pattern
                keys_to_remove = [key for key in self.l1_cache.keys() if pattern in key]
                for key in keys_to_remove:
                    del self.l1_cache[key]

            if tags:
                # Invalidate by tags
                keys_to_remove = [
                    key
                    for key, entry in self.l1_cache.items()
                    if any(tag in entry.tags for tag in tags)
                ]
                for key in keys_to_remove:
                    del self.l1_cache[key]

        # Also invalidate L2
        if cache_manager._is_connected:
            try:
                if pattern:
                    # Redis pattern matching
                    await cache_manager.delete_pattern("mlcache", pattern)
            except Exception as e:
                logger.debug(f"Failed to invalidate L2 cache: {e}")

    async def warmup(self, warmup_funcs: List[Callable[[], Any]]) -> None:
        """Warm up cache with pre-computed values."""
        for func in warmup_funcs:
            task = asyncio.create_task(self._warmup_task(func))
            self._warmup_tasks.append(task)

    async def _warmup_task(self, func: Callable[[], Any]) -> None:
        """Execute a warmup function and cache results."""
        try:
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()
            # Cache the result (implementation depends on function)
            logger.debug(f"Cache warmup completed for {func.__name__}")
        except Exception as e:
            logger.error(f"Cache warmup failed for {func.__name__}: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            l1_size = len(self.l1_cache)
            l1_hits = sum(1 for entry in self.l1_cache.values() if entry.access_count > 0)

        return {
            "l1": {
                "size": l1_size,
                "max_size": self.l1_size,
                "hits": l1_hits,
                "utilization": (l1_size / self.l1_size * 100) if self.l1_size > 0 else 0,
            },
            "eviction_policy": self.eviction_policy.value,
        }


# Global multi-level cache instance
multi_level_cache = MultiLevelCache()
