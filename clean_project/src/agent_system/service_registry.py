"""
Service Registry and Discovery
Registers running services and exposes discovery APIs for cluster members.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, cast

from .cache_manager import cache_manager
from .config_simple import settings

logger = logging.getLogger(__name__)


@dataclass
class ServiceRegistryConfig:
    """Configuration for service registry."""

    namespace: str = getattr(settings, "DISTRIBUTED_SERVICE_NAMESPACE", "agent:services")
    default_ttl_seconds: int = getattr(settings, "DISTRIBUTED_SERVICE_TTL", 45)
    heartbeat_interval_seconds: int = getattr(settings, "DISTRIBUTED_HEARTBEAT_INTERVAL", 15)


@dataclass
class ServiceInstance:
    """Metadata describing a service instance."""

    service_name: str
    instance_id: str
    host: str
    port: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=lambda: time.time())
    last_heartbeat: float = field(default_factory=lambda: time.time())
    ttl_seconds: int = getattr(settings, "DISTRIBUTED_SERVICE_TTL", 45)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "instance_id": self.instance_id,
            "host": self.host,
            "port": self.port,
            "metadata": self.metadata,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "ttl_seconds": self.ttl_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceInstance":
        return cls(
            service_name=data["service_name"],
            instance_id=data["instance_id"],
            host=data["host"],
            port=int(data["port"]),
            metadata=data.get("metadata", {}),
            registered_at=data.get("registered_at", time.time()),
            last_heartbeat=data.get("last_heartbeat", time.time()),
            ttl_seconds=int(
                data.get("ttl_seconds", getattr(settings, "DISTRIBUTED_SERVICE_TTL", 45))
            ),
        )

    def is_expired(self, now: Optional[float] = None) -> bool:
        reference = now or time.time()
        return (reference - self.last_heartbeat) > self.ttl_seconds


class ServiceRegistry:
    """Service discovery manager with Redis backend and in-memory fallback."""

    def __init__(
        self, config: Optional[ServiceRegistryConfig] = None, *, force_fallback: bool = False
    ):
        self.config = config or ServiceRegistryConfig()
        self.force_fallback = force_fallback
        self._is_initialized = False
        self._using_fallback = force_fallback
        # Async Redis client from cache_manager; typed as Any to avoid stub gaps
        self._redis: Any | None = None

        # Fallback storage
        self._services: Dict[str, Dict[str, ServiceInstance]] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> bool:
        if self._is_initialized:
            return True

        if self.force_fallback:
            self._using_fallback = True
            self._is_initialized = True
            return True

        if not cache_manager._is_connected:
            await cache_manager.connect()

        if cache_manager._is_connected and cache_manager.redis_client:
            self._redis = cache_manager.redis_client
            self._using_fallback = False
            self._is_initialized = True
            logger.info("Service registry connected to Redis backend")
            return True

        if getattr(settings, "DISTRIBUTED_ENABLED", False):
            raise RuntimeError("Service registry requires Redis when distributed is enabled")

        self._using_fallback = True
        self._is_initialized = True
        logger.warning("Redis unavailable, service registry falling back to in-memory backend")
        return True

    def _service_key(self, service_name: str, instance_id: str) -> str:
        return f"{self.config.namespace}:{service_name}:{instance_id}"

    def _index_key(self, service_name: str) -> str:
        return f"{self.config.namespace}:{service_name}:instances"

    async def register_service(
        self,
        service_name: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        instance_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> ServiceInstance:
        """Register (or refresh) a service instance."""
        await self.initialize()

        instance = ServiceInstance(
            service_name=service_name,
            instance_id=instance_id or str(uuid.uuid4()),
            host=host or socket.gethostname(),
            port=port or 0,
            metadata=metadata or {},
            ttl_seconds=ttl_seconds or self.config.default_ttl_seconds,
        )
        instance.last_heartbeat = time.time()

        if self._using_fallback:
            async with self._lock:
                service_map = self._services.setdefault(service_name, {})
                service_map[instance.instance_id] = instance
            return instance

        key = self._service_key(service_name, instance.instance_id)
        redis = self._redis
        assert redis is not None
        await redis.set(
            key, json.dumps(instance.to_dict(), default=str), ex=instance.ttl_seconds
        )
        await redis.sadd(self._index_key(service_name), instance.instance_id)
        return instance

    async def heartbeat(self, service_name: str, instance_id: str) -> bool:
        """Refresh a service TTL."""
        await self.initialize()

        if self._using_fallback:
            async with self._lock:
                service_map = self._services.get(service_name, {})
                instance = service_map.get(instance_id)
                if not instance:
                    return False
                instance.last_heartbeat = time.time()
                service_map[instance_id] = instance
                return True

        key = self._service_key(service_name, instance_id)
        redis = self._redis
        assert redis is not None
        raw = await redis.get(key)
        if not raw:
            return False

        data = json.loads(self._decode(raw))
        data["last_heartbeat"] = time.time()
        await redis.set(
            key,
            json.dumps(data, default=str),
            ex=data.get("ttl_seconds", self.config.default_ttl_seconds),
        )
        return True

    async def deregister(self, service_name: str, instance_id: str) -> bool:
        """Remove a service instance from the registry."""
        await self.initialize()

        if self._using_fallback:
            async with self._lock:
                service_map = self._services.get(service_name, {})
                return service_map.pop(instance_id, None) is not None

        key = self._service_key(service_name, instance_id)
        redis = self._redis
        assert redis is not None
        removed = await redis.delete(key)
        await redis.srem(self._index_key(service_name), instance_id)
        return bool(removed)

    async def discover(self, service_name: str) -> List[ServiceInstance]:
        """Return active instances for a service."""
        await self.initialize()

        if self._using_fallback:
            async with self._lock:
                service_map = self._services.get(service_name, {})
                now = time.time()
                active = []
                expired = []
                for instance_id, instance in service_map.items():
                    if instance.is_expired(now):
                        expired.append(instance_id)
                        continue
                    active.append(instance)
                for instance_id in expired:
                    service_map.pop(instance_id, None)
                return active

        redis = self._redis
        assert redis is not None
        instance_ids = await redis.smembers(self._index_key(service_name))
        if not instance_ids:
            return []

        instances: List[ServiceInstance] = []
        for instance_id in instance_ids:
            key = self._service_key(service_name, self._decode(instance_id))
            raw = await redis.get(key)
            if not raw:
                await redis.srem(self._index_key(service_name), self._decode(instance_id))
                continue
            data = json.loads(self._decode(raw))
            instance = ServiceInstance.from_dict(data)
            if instance.is_expired():
                await self.deregister(service_name, instance.instance_id)
                continue
            instances.append(instance)
        return instances

    async def cleanup_stale(self, service_name: Optional[str] = None) -> int:
        """Remove expired instances."""
        await self.initialize()

        if self._using_fallback:
            async with self._lock:
                services = [service_name] if service_name else list(self._services.keys())
                removed = 0
                now = time.time()
                for svc in services:
                    service_map = self._services.get(svc, {})
                    for instance_id, instance in list(service_map.items()):
                        if instance.is_expired(now):
                            service_map.pop(instance_id, None)
                            removed += 1
                return removed

        services = [service_name] if service_name else await self._list_services()
        removed = 0
        redis = self._redis
        assert redis is not None
        for svc in services:
            instance_ids = await redis.smembers(self._index_key(svc))
            for instance_id in instance_ids:
                instance_id_str = self._decode(instance_id)
                key = self._service_key(svc, instance_id_str)
                raw = await redis.get(key)
                if not raw:
                    await redis.srem(self._index_key(svc), instance_id_str)
                    removed += 1
                    continue
                data = json.loads(self._decode(raw))
                instance = ServiceInstance.from_dict(data)
                if instance.is_expired():
                    await self.deregister(svc, instance.instance_id)
                    removed += 1
        return removed

    async def _list_services(self) -> List[str]:
        if self._using_fallback:
            async with self._lock:
                return list(self._services.keys())
        pattern = f"{self.config.namespace}:*"
        redis = self._redis
        assert redis is not None
        keys = await redis.keys(pattern)
        services = set()
        for key in keys:
            decoded = self._decode(key)
            parts = decoded.split(":")
            if len(parts) >= 3:
                services.add(parts[1])
        return list(services)

    @staticmethod
    def _decode(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return cast(str, value)


# Global registry instance
service_registry = ServiceRegistry()
