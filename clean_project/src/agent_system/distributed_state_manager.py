"""
Distributed State Manager
Maintains shared cluster state with Redis backend and in-memory fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .cache_manager import cache_manager
from .config_simple import settings

logger = logging.getLogger(__name__)


@dataclass
class StateManagerConfig:
    """Configuration for distributed state management."""

    namespace: str = getattr(settings, "DISTRIBUTED_STATE_NAMESPACE", "agent:state")
    default_ttl: int = 300
    lock_ttl: int = getattr(settings, "DISTRIBUTED_VISIBILITY_TIMEOUT", 30)


@dataclass
class StateRecord:
    """Represents a distributed state entry."""

    namespace: str
    key: str
    value: Dict[str, Any]
    version: int = 1
    owner: str = getattr(settings, "DISTRIBUTED_NODE_ID", "local-node")
    updated_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "namespace": self.namespace,
            "key": self.key,
            "value": self.value,
            "version": self.version,
            "owner": self.owner,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateRecord":
        return cls(
            namespace=data["namespace"],
            key=data["key"],
            value=data.get("value", {}),
            version=int(data.get("version", 1)),
            owner=data.get("owner", getattr(settings, "DISTRIBUTED_NODE_ID", "local-node")),
            updated_at=data.get("updated_at", time.time()),
        )


class DistributedStateManager:
    """Shared state manager."""

    def __init__(
        self,
        config: Optional[StateManagerConfig] = None,
        *,
        force_fallback: bool = False,
    ):
        self.config = config or StateManagerConfig()
        self.force_fallback = force_fallback
        self._is_initialized = False
        self._using_fallback = force_fallback
        self._redis = None

        # Fallback storage
        self._state: Dict[str, Dict[str, StateRecord]] = {}
        self._expirations: Dict[str, Dict[str, float]] = {}
        self._locks: Dict[str, Dict[str, float]] = {}
        self._lock_owner: Dict[str, str] = {}
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
            logger.info("Distributed state manager connected to Redis backend")
            return True

        self._using_fallback = True
        self._is_initialized = True
        logger.warning("Redis unavailable, state manager falling back to in-memory backend")
        return True

    def _state_key(self, namespace: str, key: str) -> str:
        return f"{self.config.namespace}:{namespace}:{key}"

    def _lock_key(self, name: str) -> str:
        return f"{self.config.namespace}:lock:{name}"

    async def set_state(
        self,
        namespace: str,
        key: str,
        value: Dict[str, Any],
        *,
        ttl: Optional[int] = None,
        owner: Optional[str] = None,
    ) -> StateRecord:
        """Store state for a namespace/key."""
        await self.initialize()

        owner_id = owner or getattr(settings, "DISTRIBUTED_NODE_ID", "local-node")
        record = StateRecord(namespace=namespace, key=key, value=value, owner=owner_id)

        if self._using_fallback:
            async with self._lock:
                namespace_map = self._state.setdefault(namespace, {})
                existing = namespace_map.get(key)
                if existing:
                    record.version = existing.version + 1
                namespace_map[key] = record
                expires_at = time.time() + (ttl or self.config.default_ttl)
                self._expirations.setdefault(namespace, {})[key] = expires_at
            return record

        redis_key = self._state_key(namespace, key)
        raw = await self._redis.get(redis_key)
        if raw:
            existing = StateRecord.from_dict(json.loads(self._decode(raw)))
            record.version = existing.version + 1
        await self._redis.set(redis_key, json.dumps(record.to_dict(), default=str), ex=ttl or self.config.default_ttl)
        return record

    async def update_state(
        self,
        namespace: str,
        key: str,
        updates: Dict[str, Any],
        *,
        ttl: Optional[int] = None,
    ) -> Optional[StateRecord]:
        """Merge updates into an existing state record."""
        current = await self.get_state(namespace, key)
        if not current:
            return None

        new_value = dict(current.value)
        new_value.update(updates)
        return await self.set_state(namespace, key, new_value, ttl=ttl, owner=current.owner)

    async def get_state(self, namespace: str, key: str) -> Optional[StateRecord]:
        """Retrieve state for namespace/key."""
        await self.initialize()

        if self._using_fallback:
            async with self._lock:
                namespace_map = self._state.get(namespace, {})
                record = namespace_map.get(key)
                if not record:
                    return None
                expires = self._expirations.get(namespace, {}).get(key)
                if expires and expires < time.time():
                    namespace_map.pop(key, None)
                    self._expirations.get(namespace, {}).pop(key, None)
                    return None
                return record

        redis_key = self._state_key(namespace, key)
        raw = await self._redis.get(redis_key)
        if not raw:
            return None
        return StateRecord.from_dict(json.loads(self._decode(raw)))

    async def delete_state(self, namespace: str, key: str) -> bool:
        await self.initialize()

        if self._using_fallback:
            async with self._lock:
                namespace_map = self._state.get(namespace, {})
                self._expirations.get(namespace, {}).pop(key, None)
                return namespace_map.pop(key, None) is not None

        redis_key = self._state_key(namespace, key)
        removed = await self._redis.delete(redis_key)
        return bool(removed)

    async def list_namespace(self, namespace: str) -> Dict[str, StateRecord]:
        """Return all state entries in a namespace."""
        await self.initialize()

        if self._using_fallback:
            async with self._lock:
                namespace_map = self._state.get(namespace, {})
                # Filter expired entries
                expired = [
                    key
                    for key, expires in self._expirations.get(namespace, {}).items()
                    if expires < time.time()
                ]
                for key in expired:
                    namespace_map.pop(key, None)
                    self._expirations.get(namespace, {}).pop(key, None)
                return dict(namespace_map)

        pattern = f"{self.config.namespace}:{namespace}:*"
        keys = await self._redis.keys(pattern)
        results: Dict[str, StateRecord] = {}
        for redis_key in keys:
            raw = await self._redis.get(redis_key)
            if not raw:
                continue
            record = StateRecord.from_dict(json.loads(self._decode(raw)))
            results[record.key] = record
        return results

    async def acquire_lock(
        self,
        name: str,
        *,
        ttl: Optional[int] = None,
        owner: Optional[str] = None,
    ) -> Optional[str]:
        """Acquire a distributed lock."""
        await self.initialize()
        owner_id = owner or f"{getattr(settings, 'DISTRIBUTED_NODE_ID', 'node')}:{uuid.uuid4()}"
        ttl_seconds = ttl or self.config.lock_ttl

        if self._using_fallback:
            async with self._lock:
                expires = self._locks.get(name)
                if expires and expires.get("deadline", 0) > time.time():
                    return None
                self._locks[name] = {"deadline": time.time() + ttl_seconds}
                self._lock_owner[name] = owner_id
                return owner_id

        lock_key = self._lock_key(name)
        acquired = await self._redis.set(lock_key, owner_id, nx=True, ex=ttl_seconds)
        if acquired:
            return owner_id
        return None

    async def release_lock(self, name: str, owner_id: str) -> bool:
        """Release a distributed lock."""
        await self.initialize()

        if self._using_fallback:
            async with self._lock:
                if self._lock_owner.get(name) != owner_id:
                    return False
                self._locks.pop(name, None)
                self._lock_owner.pop(name, None)
                return True

        lock_key = self._lock_key(name)
        current_owner = await self._redis.get(lock_key)
        if not current_owner:
            return True
        if self._decode(current_owner) != owner_id:
            return False
        await self._redis.delete(lock_key)
        return True

    @staticmethod
    def _decode(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value


# Global state manager
distributed_state_manager = DistributedStateManager()
