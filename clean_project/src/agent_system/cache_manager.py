"""
Redis Cache Manager for Enterprise-Grade Caching
Supports session caching, data caching, and distributed caching
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import pickle
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

# Ensure the redis module reference is Optional-typed for mypy when import fails
redis: Any | None = None

try:
    import redis.asyncio as _redis_asyncio
    from redis.asyncio import ConnectionPool, Redis
    REDIS_IMPORT_ERROR: Optional[Exception] = None
except Exception as _exc:  # ModuleNotFoundError or other import issues
    REDIS_IMPORT_ERROR = _exc
    if TYPE_CHECKING:  # for type checkers only
        from redis.asyncio import ConnectionPool as ConnectionPool  # pragma: no cover
        from redis.asyncio import Redis as Redis  # pragma: no cover
    else:
        Redis = Any  # type: ignore
        ConnectionPool = Any  # type: ignore

# Assign imported module to the Optional-typed name used by this module
if '_redis_asyncio' in globals():
    # The name check above is defensive; assign if available
    try:
        redis = _redis_asyncio
    except NameError:
        pass


logger = logging.getLogger(__name__)


async def _await_if_awaitable(value: Any) -> Any:
    """Await the value if it's awaitable, otherwise return it unchanged."""
    if inspect.isawaitable(value):
        return await value
    return value


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
    socket_keepalive_options: Optional[Dict[str, Any]] = None
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
        self.connection_pool: Optional[ConnectionPool] = None
        self._is_connected = False
        self._cache_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}
        self._monitoring_system = None

    async def connect(self) -> bool:
        """Connect to Redis server."""
        if redis is None:
            detail = f": {REDIS_IMPORT_ERROR}" if REDIS_IMPORT_ERROR else ""
            raise RuntimeError(
                "Redis package not available. Install 'redis[async]>=5' to enable caching" + detail
            )

        if self._is_connected and self.redis_client:
            return True

        try:
            # Build URL and create async Redis client via from_url to avoid incompatible kwargs
            scheme = "rediss" if self.config.ssl else "redis"
            auth = f":{self.config.password}@" if self.config.password else ""
            url = f"{scheme}://{auth}{self.config.host}:{self.config.port}/{self.config.db}"

            # Use from_url which configures an internal pool; keep args minimal for compatibility
            self.redis_client = redis.from_url(
                url,
                decode_responses=self.config.decode_responses,
                max_connections=self.config.max_connections,
            )

            # Connection pool reference (optional)
            try:
                self.connection_pool = getattr(self.redis_client, "connection_pool", None)
            except Exception:
                self.connection_pool = None

            if self.redis_client is None:
                raise RuntimeError("Failed to create Redis client")

            await _await_if_awaitable(self.redis_client.ping())
            self._is_connected = True

            logger.info(f"✅ Redis cache connected: {self.config.host}:{self.config.port}")
            return True

        except Exception as e:
            self._is_connected = False
            raise RuntimeError(f"Redis cache connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from Redis server."""
        try:
            if self.redis_client:
                await _await_if_awaitable(self.redis_client.close())
            if self.connection_pool:
                await _await_if_awaitable(self.connection_pool.disconnect())
            self._is_connected = False
            logger.info("✅ Redis cache disconnected")
        except Exception as e:
            logger.error(f"❌ Redis cache disconnect error: {e}")

    async def is_healthy(self) -> bool:
        """Check if Redis connection is healthy."""
        client = self.redis_client
        if not self._is_connected or client is None:
            return False

        try:
            await _await_if_awaitable(client.ping())
            return True
        except Exception:
            self._is_connected = False
            return False

    def _make_key(self, namespace: str, key: str, *args: object) -> str:
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
        if isinstance(value, str):
            return value
        elif isinstance(value, (int, float)):
            return str(value)
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

    def register_monitoring_system(self, monitoring_system: Any) -> None:
        """Allow the monitoring layer to register itself without circular imports."""
        self._monitoring_system = monitoring_system

    def _record_cache_metric(self, operation: str, status: str, start_time: Optional[float] = None) -> None:
        monitoring = self._monitoring_system
        if monitoring is None:
            return

        duration = None
        if start_time is not None:
            duration = time.perf_counter() - start_time

        try:
            monitoring.record_cache_operation(operation, status, duration)
        except Exception as exc:
            logger.debug(f"Failed to record cache metric: {exc}")

    async def set(
        self, namespace: str, key: str, value: Any, ttl: Optional[int] = None, *args: object
    ) -> bool:
        """Set a value in cache with optional TTL."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return False

        start_time = time.perf_counter()
        try:
            redis_key = self._make_key(namespace, key, *args)
            serialized_value = self._serialize(value)

            client = self.redis_client
            if client is None:
                return False
            if ttl:
                await client.setex(redis_key, ttl, serialized_value)
            else:
                await client.set(redis_key, serialized_value)

            self._cache_stats["sets"] += 1
            logger.debug(f"Cache SET: {redis_key} (TTL: {ttl}s)")
            self._record_cache_metric("set", "success", start_time)
            return True

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache SET error for {key}: {e}")
            self._record_cache_metric("set", "error", start_time)
            return False

    async def get(self, namespace: str, key: str, default: Any = None, *args: object) -> Any:
        """Get a value from cache."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return default

        start_time = time.perf_counter()
        try:
            redis_key = self._make_key(namespace, key, *args)
            client = self.redis_client
            if client is None:
                return default
            value = await client.get(redis_key)

            if value is None:
                self._cache_stats["misses"] += 1
                logger.debug(f"Cache MISS: {redis_key}")
                self._record_cache_metric("get", "miss", start_time)
                return default

            self._cache_stats["hits"] += 1
            result = self._deserialize(value)
            logger.debug(f"Cache HIT: {redis_key}")
            self._record_cache_metric("get", "hit", start_time)
            return result

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache GET error for {key}: {e}")
            self._record_cache_metric("get", "error", start_time)
            return default

    async def delete(self, namespace: str, key: str, *args: object) -> bool:
        """Delete a value from cache."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return False

        start_time = time.perf_counter()
        try:
            redis_key = self._make_key(namespace, key, *args)
            client = self.redis_client
            if client is None:
                return False
            result = await client.delete(redis_key)

            if result:
                self._cache_stats["deletes"] += 1
                logger.debug(f"Cache DELETE: {redis_key}")
                self._record_cache_metric("delete", "success", start_time)
                return True

            return False

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache DELETE error for {key}: {e}")
            self._record_cache_metric("delete", "error", start_time)
            return False

    async def delete_pattern(self, namespace: str, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return 0

        start_time = time.perf_counter()
        try:
            redis_pattern = self._make_key(namespace, pattern)
            client = self.redis_client
            if client is None:
                return 0
            keys = await client.keys(redis_pattern)

            if keys:
                deleted_count_val = await client.delete(*keys)
                deleted_count = int(deleted_count_val)
                self._cache_stats["deletes"] += deleted_count
                logger.debug(f"Cache DELETE PATTERN: {redis_pattern} ({deleted_count} keys)")
                status = "success" if deleted_count else "miss"
                self._record_cache_metric("delete", status, start_time)
                return deleted_count

            return 0

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache DELETE PATTERN error for {pattern}: {e}")
            self._record_cache_metric("delete", "error", start_time)
            return 0

    async def scan_namespace(self, namespace: str, pattern: str = "*") -> List[str]:
        """Return all keys within a namespace matching the pattern."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return []

        try:
            client = self.redis_client
            if client is None:
                return []

            redis_pattern = self._make_key(namespace, pattern)
            cursor = 0
            results: List[str] = []

            while True:
                cursor, keys = await client.scan(cursor=cursor, match=redis_pattern, count=100)
                for key in keys:
                    key_str = key.decode() if isinstance(key, bytes) else str(key)
                    results.append(key_str)
                if cursor == 0:
                    break

            prefix = self._make_key(namespace, "")
            relative_keys = []
            for key in results:
                if key.startswith(prefix):
                    relative_keys.append(key[len(prefix):])
                else:
                    relative_keys.append(key)
            return relative_keys

        except Exception as exc:
            logger.error(f"Cache SCAN error for namespace {namespace}: {exc}")
            return []

    async def exists(self, namespace: str, key: str, *args: object) -> bool:
        """Check if a key exists in cache."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return False

        try:
            redis_key = self._make_key(namespace, key, *args)
            client = self.redis_client
            if client is None:
                return False
            exists = await client.exists(redis_key)
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
            client = self.redis_client
            if client is None:
                return None
            result = await client.incrby(redis_key, amount)
            logger.debug(f"Cache INCREMENT: {redis_key} (+{amount}) = {result}")
            return int(result)

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache INCREMENT error for {key}: {e}")
            return None

    async def get_ttl(self, namespace: str, key: str, *args: object) -> Optional[int]:
        """Get TTL (time to live) for a key."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected:
            return None

        try:
            redis_key = self._make_key(namespace, key, *args)
            client = self.redis_client
            if client is None:
                return None
            ttl = await client.ttl(redis_key)
            return int(ttl) if ttl is not None else None

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
            client = self.redis_client
            if client is None:
                return 0
            keys = await client.keys(pattern)

            if keys:
                deleted_count_val = await client.delete(*keys)
                deleted_count = int(deleted_count_val)
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
            client = self.redis_client
            if client is None:
                return {"status": "disconnected", "stats": self._cache_stats}
            info = await client.info()
            db_size = await client.dbsize()

            hit_rate: float = 0.0
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
        val = await self.get("sessions", session_id)
        return cast(Optional[Dict[str, Any]], val)

    async def delete_session(self, session_id: str) -> bool:
        """Delete user session."""
        return await self.delete("sessions", session_id)

    async def clear_user_sessions(self, user_id: str) -> int:
        """Clear all sessions for a user."""
        pattern = f"{user_id}:*"
        return await self.delete_pattern("sessions", pattern)

    async def increment_counter(
        self, namespace: str, key: str, window_seconds: Optional[int] = None, *args: object
    ) -> Optional[int]:
        """Atomically increment a counter with optional TTL."""
        if not self._is_connected:
            await self.connect()

        if not self._is_connected or not self.redis_client:
            return None

        start_time = time.perf_counter()
        try:
            redis_key = self._make_key(namespace, key, *args)
            client = self.redis_client
            if client is None:
                return None
            value = await client.incr(redis_key)
            if window_seconds and value == 1:
                # Only set the expiration the first time the key is seen.
                await client.expire(redis_key, window_seconds)

            self._record_cache_metric("incr", "success", start_time)
            return int(value)
        except Exception as exc:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache counter increment error for {key}: {exc}")
            self._record_cache_metric("incr", "error", start_time)
            return None

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
        val = await self.get("api_responses", cache_key)
        return cast(Optional[Any], val)

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
