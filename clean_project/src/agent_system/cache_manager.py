"""
Redis Cache Manager for Enterprise-Grade Caching
Supports session caching, data caching, and distributed caching
"""

from __future__ import annotations

import json
import logging
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import hashlib
from typing import TYPE_CHECKING

try:
    import redis.asyncio as redis  # type: ignore
    from redis.asyncio import Redis  # type: ignore
except Exception:  # ModuleNotFoundError or other import issues
    redis = None  # type: ignore
    if TYPE_CHECKING:  # for type checkers only
        from redis.asyncio import Redis as Redis  # pragma: no cover
    else:
        class Redis:  # minimal placeholder for runtime annotations
            pass


logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Cache configuration settings."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False
    decode_responses: bool = False
    max_connections: int = 20
    connection_pool_size: int = 20
    socket_connect_timeout: int = 5
    socket_timeout: int = 5
    socket_keepalive: bool = True
    socket_keepalive_options: Optional[Dict] = None
    health_check_interval: int = 30
    retry_on_timeout: bool = True
    encoding: str = "utf-8"
    encoding_errors: str = "strict"


class CacheManager:
    """
    Enterprise-grade Redis cache manager with:
    - Session caching
    - Data caching
    - Cache invalidation strategies
    - Distributed caching support
    - Health monitoring
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.redis_client: Optional[Redis] = None
        self.connection_pool = None
        self._is_connected = False
        self._cache_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}

    async def connect(self) -> bool:
        """Connect to Redis server."""
        try:
            if redis is None:
                logger.warning("Redis package not available; cache disabled")
                self._is_connected = False
                return False
            if self._is_connected and self.redis_client:
                return True

            # Create connection pool
            self.connection_pool = redis.ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                ssl=self.config.ssl,
                decode_responses=self.config.decode_responses,
                max_connections=self.config.max_connections,
                socket_connect_timeout=self.config.socket_connect_timeout,
                socket_timeout=self.config.socket_timeout,
                socket_keepalive=self.config.socket_keepalive,
                socket_keepalive_options=self.config.socket_keepalive_options,
                health_check_interval=self.config.health_check_interval,
                retry_on_timeout=self.config.retry_on_timeout,
                encoding=self.config.encoding,
                encoding_errors=self.config.encoding_errors,
            )

            # Create Redis client
            self.redis_client = redis.Redis(
                connection_pool=self.connection_pool, decode_responses=self.config.decode_responses
            )

            # Test connection
            await self.redis_client.ping()
            self._is_connected = True

            logger.info(f"✅ Redis cache connected: {self.config.host}:{self.config.port}")
            return True

        except Exception as e:
            logger.error(f"❌ Redis cache connection failed: {e}")
            self._is_connected = False
            return False

    async def disconnect(self):
        """Disconnect from Redis server."""
        try:
            if self.redis_client:
                await self.redis_client.close()
            if self.connection_pool:
                await self.connection_pool.disconnect()
            self._is_connected = False
            logger.info("✅ Redis cache disconnected")
        except Exception as e:
            logger.error(f"❌ Redis cache disconnect error: {e}")

    async def is_healthy(self) -> bool:
        """Check if Redis connection is healthy."""
        if not self._is_connected or not self.redis_client:
            return False

        try:
            await self.redis_client.ping()
            return True
        except Exception:
            self._is_connected = False
            return False

    def _make_key(self, namespace: str, key: str, *args) -> str:
        """Create a namespaced cache key."""
        if args:
            key_parts = [key] + [str(arg) for arg in args]
            key = ":".join(key_parts)

        full_key = f"agent:{namespace}:{key}"

        # Ensure key is not too long (Redis limit is 512MB but we want reasonable keys)
        if len(full_key) > 250:
            # Hash the key if it's too long
            key_hash = hashlib.md5(full_key.encode()).hexdigest()
            full_key = f"agent:{namespace}:hashed:{key_hash}"

        return full_key

    def _serialize(self, value: Any) -> Union[str, bytes]:
        """Serialize value for Redis storage."""
        if isinstance(value, (str, int, float)):
            return value
        elif isinstance(value, (dict, list, tuple)):
            return json.dumps(value, default=str)
        elif value is None:
            return ""
        else:
            # Pickle complex objects
            return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)

    def _deserialize(self, value: Union[str, bytes]) -> Any:
        """Deserialize value from Redis."""
        if not value:
            return None

        # Try to parse as JSON first
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                pass

        # Try to decode as string
        if isinstance(value, str):
            return value

        # Try to unpickle
        try:
            return pickle.loads(value)
        except (pickle.PickleError, ValueError, EOFError):
            logger.warning(f"Could not deserialize value: {type(value)}")
            return str(value)

    async def set(
        self, namespace: str, key: str, value: Any, ttl: Optional[int] = None, *args
    ) -> bool:
        """Set a value in cache with optional TTL."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return False

        try:
            redis_key = self._make_key(namespace, key, *args)
            serialized_value = self._serialize(value)

            if ttl:
                await self.redis_client.setex(redis_key, ttl, serialized_value)
            else:
                await self.redis_client.set(redis_key, serialized_value)

            self._cache_stats["sets"] += 1
            logger.debug(f"Cache SET: {redis_key} (TTL: {ttl}s)")
            return True

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache SET error for {key}: {e}")
            return False

    async def get(self, namespace: str, key: str, default: Any = None, *args) -> Any:
        """Get a value from cache."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return default

        try:
            redis_key = self._make_key(namespace, key, *args)
            value = await self.redis_client.get(redis_key)

            if value is None:
                self._cache_stats["misses"] += 1
                logger.debug(f"Cache MISS: {redis_key}")
                return default

            self._cache_stats["hits"] += 1
            result = self._deserialize(value)
            logger.debug(f"Cache HIT: {redis_key}")
            return result

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache GET error for {key}: {e}")
            return default

    async def delete(self, namespace: str, key: str, *args) -> bool:
        """Delete a value from cache."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return False

        try:
            redis_key = self._make_key(namespace, key, *args)
            result = await self.redis_client.delete(redis_key)

            if result:
                self._cache_stats["deletes"] += 1
                logger.debug(f"Cache DELETE: {redis_key}")
                return True

            return False

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache DELETE error for {key}: {e}")
            return False

    async def delete_pattern(self, namespace: str, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return 0

        try:
            redis_pattern = self._make_key(namespace, pattern)
            keys = await self.redis_client.keys(redis_pattern)

            if keys:
                deleted_count = await self.redis_client.delete(*keys)
                self._cache_stats["deletes"] += deleted_count
                logger.debug(f"Cache DELETE PATTERN: {redis_pattern} ({deleted_count} keys)")
                return deleted_count

            return 0

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache DELETE PATTERN error for {pattern}: {e}")
            return 0

    async def exists(self, namespace: str, key: str, *args) -> bool:
        """Check if a key exists in cache."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return False

        try:
            redis_key = self._make_key(namespace, key, *args)
            exists = await self.redis_client.exists(redis_key)
            return bool(exists)

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache EXISTS error for {key}: {e}")
            return False

    async def increment(self, namespace: str, key: str, amount: int = 1) -> Optional[int]:
        """Increment a numeric value in cache."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return None

        try:
            redis_key = self._make_key(namespace, key)
            result = await self.redis_client.incrby(redis_key, amount)
            logger.debug(f"Cache INCREMENT: {redis_key} (+{amount}) = {result}")
            return result

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache INCREMENT error for {key}: {e}")
            return None

    async def get_ttl(self, namespace: str, key: str, *args) -> Optional[int]:
        """Get TTL (time to live) for a key."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return None

        try:
            redis_key = self._make_key(namespace, key, *args)
            ttl = await self.redis_client.ttl(redis_key)
            return ttl

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache TTL error for {key}: {e}")
            return None

    async def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return 0

        try:
            pattern = self._make_key(namespace, "*")
            keys = await self.redis_client.keys(pattern)

            if keys:
                deleted_count = await self.redis_client.delete(*keys)
                self._cache_stats["deletes"] += deleted_count
                logger.info(f"Cache CLEAR NAMESPACE: {namespace} ({deleted_count} keys)")
                return deleted_count

            return 0

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache CLEAR NAMESPACE error for {namespace}: {e}")
            return 0

    async def get_cache_info(self) -> Dict[str, Any]:
        """Get comprehensive cache information."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return {"status": "disconnected", "stats": self._cache_stats}

        try:
            info = await self.redis_client.info()
            db_size = await self.redis_client.dbsize()

            hit_rate = 0
            total_requests = self._cache_stats["hits"] + self._cache_stats["misses"]
            if total_requests > 0:
                hit_rate = (self._cache_stats["hits"] / total_requests) * 100

            return {
                "status": "connected",
                "redis_info": {
                    "version": info.get("redis_version"),
                    "uptime": info.get("uptime_in_seconds"),
                    "used_memory": info.get("used_memory_human"),
                    "used_memory_peak": info.get("used_memory_peak_human"),
                    "connected_clients": info.get("connected_clients"),
                    "total_connections_received": info.get("total_connections_received"),
                    "total_commands_processed": info.get("total_commands_processed"),
                    "keyspace_hits": info.get("keyspace_hits"),
                    "keyspace_misses": info.get("keyspace_misses"),
                },
                "cache_stats": {
                    **self._cache_stats,
                    "hit_rate": round(hit_rate, 2),
                    "total_requests": total_requests,
                },
                "database_size": db_size,
                "config": {
                    "host": self.config.host,
                    "port": self.config.port,
                    "db": self.config.db,
                },
            }

        except Exception as e:
            logger.error(f"Cache info error: {e}")
            return {"status": "error", "error": str(e), "stats": self._cache_stats}

    # Session management methods
    async def set_session(
        self, session_id: str, user_data: Dict[str, Any], ttl: int = 1800  # 30 minutes default
    ) -> bool:
        """Set user session data."""
        return await self.set("sessions", session_id, user_data, ttl)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get user session data."""
        return await self.get("sessions", session_id)

    async def delete_session(self, session_id: str) -> bool:
        """Delete user session."""
        return await self.delete("sessions", session_id)

    async def clear_user_sessions(self, user_id: str) -> int:
        """Clear all sessions for a user."""
        pattern = f"{user_id}:*"
        return await self.delete_pattern("sessions", pattern)

    # API response caching
    async def cache_api_response(
        self,
        endpoint: str,
        params: Dict[str, Any],
        response: Any,
        ttl: int = 300,  # 5 minutes default
    ) -> bool:
        """Cache API response."""
        cache_key = f"{endpoint}:{hashlib.md5(str(sorted(params.items())).encode()).hexdigest()}"
        return await self.set("api_responses", cache_key, response, ttl)

    async def get_cached_api_response(self, endpoint: str, params: Dict[str, Any]) -> Optional[Any]:
        """Get cached API response."""
        cache_key = f"{endpoint}:{hashlib.md5(str(sorted(params.items())).encode()).hexdigest()}"
        return await self.get("api_responses", cache_key)

    # Performance optimization methods
    async def cache_expensive_operation(
        self, operation_name: str, input_data: Any, result: Any, ttl: int = 3600  # 1 hour default
    ) -> bool:
        """Cache results of expensive operations."""
        cache_key = f"{operation_name}:{hashlib.md5(str(input_data).encode()).hexdigest()}"
        return await self.set("expensive_ops", cache_key, result, ttl)

    async def get_cached_expensive_operation(
        self, operation_name: str, input_data: Any
    ) -> Optional[Any]:
        """Get cached result of expensive operation."""
        cache_key = f"{operation_name}:{hashlib.md5(str(input_data).encode()).hexdigest()}"
        return await self.get("expensive_ops", cache_key)


# Global cache manager instance
cache_manager = CacheManager()


# Convenience functions
async def get_cache() -> CacheManager:
    """Get the global cache manager instance."""
    if not cache_manager._is_connected:
        await cache_manager.connect()
    return cache_manager


async def set_cache_value(namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """Convenience function to set cache value."""
    cache = await get_cache()
    return await cache.set(namespace, key, value, ttl)


async def get_cache_value(namespace: str, key: str, default: Any = None) -> Any:
    """Convenience function to get cache value."""
    cache = await get_cache()
    return await cache.get(namespace, key, default)


async def delete_cache_value(namespace: str, key: str) -> bool:
    """Convenience function to delete cache value."""
    cache = await get_cache()
    return await cache.delete(namespace, key)


# Session management
async def set_user_session(session_id: str, user_data: Dict[str, Any], ttl: int = 1800) -> bool:
    """Set user session in cache."""
    cache = await get_cache()
    return await cache.set_session(session_id, user_data, ttl)


async def get_user_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get user session from cache."""
    cache = await get_cache()
    return await cache.get_session(session_id)


async def delete_user_session(session_id: str) -> bool:
    """Delete user session from cache."""
    cache = await get_cache()
    return await cache.delete_session(session_id)
