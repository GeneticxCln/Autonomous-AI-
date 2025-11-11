"""
Distributed Message Queue
Provides cross-node messaging with Redis backend and in-memory fallback.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from .cache_manager import cache_manager

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from redis.asyncio import Redis as RedisClient
else:
    RedisClient = Any
from .config_simple import settings

logger = logging.getLogger(__name__)


async def _await_if_awaitable(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class MessagePriority(IntEnum):
    """Message priority ordering (lower values processed first)."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class MessageEnvelope:
    """Normalized representation of a queued message."""

    message_id: str
    queue: str
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    headers: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: time.time())
    retries: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize envelope for storage."""
        return {
            "message_id": self.message_id,
            "queue": self.queue,
            "payload": self.payload,
            "priority": self.priority.name,
            "headers": self.headers,
            "timestamp": self.timestamp,
            "retries": self.retries,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageEnvelope":
        """Deserialize envelope from storage."""
        priority_value = data.get("priority", MessagePriority.NORMAL.name)
        priority = (
            priority_value
            if isinstance(priority_value, MessagePriority)
            else MessagePriority[priority_value]
        )
        return cls(
            message_id=data["message_id"],
            queue=data["queue"],
            payload=data.get("payload", {}),
            priority=priority,
            headers=data.get("headers", {}),
            timestamp=data.get("timestamp", time.time()),
            retries=data.get("retries", 0),
        )


@dataclass
class MessageQueueConfig:
    """Configuration for the distributed queue."""

    namespace: str = getattr(settings, "DISTRIBUTED_MESSAGE_NAMESPACE", "agent:queues")
    visibility_timeout: int = getattr(settings, "DISTRIBUTED_VISIBILITY_TIMEOUT", 30)
    retention_seconds: int = 3600
    poll_interval_seconds: int = getattr(settings, "DISTRIBUTED_QUEUE_POLL_INTERVAL", 1)
    max_fallback_queue_size: int = 5000


class DistributedMessageQueue:
    """
    Distributed queue with Redis backend and asyncio-based in-memory fallback.

    Supports:
    - Priority based routing
    - Visibility timeouts and retry handling
    - Graceful degradation when Redis is unavailable
    """

    # Priority queue entries are (priority_value, monotonic_counter, envelope)
    PriorityItem = Tuple[int, int, MessageEnvelope]

    def __init__(
        self,
        config: Optional[MessageQueueConfig] = None,
        *,
        force_fallback: bool = False,
    ) -> None:
        self.config = config or MessageQueueConfig()
        self.force_fallback = force_fallback
        self._is_initialized: bool = False
        self._using_fallback: bool = force_fallback
        self._fallback_queues: Dict[
            str, asyncio.PriorityQueue[DistributedMessageQueue.PriorityItem]
        ] = {}
        self._fallback_pending: Dict[str, Dict[str, MessageEnvelope]] = {}
        self._fallback_lock: asyncio.Lock = asyncio.Lock()
        self._message_counter: int = 0
        self._redis: Optional[RedisClient] = None

    async def initialize(self) -> bool:
        """Initialize queue backend."""
        if self._is_initialized:
            return True

        if self.force_fallback:
            self._using_fallback = True
            self._is_initialized = True
            logger.info("Distributed message queue running in forced in-memory mode")
            return True

        if not cache_manager._is_connected:
            try:
                await cache_manager.connect()
            except Exception as exc:
                # Fall back to in-memory backend when Redis is unavailable
                self._using_fallback = True
                self._is_initialized = True
                logger.warning(
                    "Redis unavailable for distributed queue: %s; using in-memory fallback",
                    exc,
                )
                return True

        if cache_manager._is_connected and cache_manager.redis_client:
            self._redis = cache_manager.redis_client
            self._using_fallback = False
            self._is_initialized = True
            logger.info("Distributed message queue connected to Redis backend")
            return True

        # If distributed is enabled, fail fast instead of falling back
        if getattr(settings, "DISTRIBUTED_ENABLED", False):
            raise RuntimeError(
                "Distributed messaging requires Redis. Configure REDIS and ensure connectivity."
            )

        self._using_fallback = True
        self._is_initialized = True
        logger.warning(
            "Redis unavailable, distributed message queue falling back to in-memory backend"
        )
        return True

    def _queue_key(self, queue: str, priority: MessagePriority) -> str:
        return f"{self.config.namespace}:{queue}:{priority.name.lower()}"

    def _pending_key(self, queue: str) -> str:
        return f"{self.config.namespace}:{queue}:pending"

    def _require_redis(self) -> RedisClient:
        """Return initialized Redis client or raise."""
        if self._redis is None:
            raise RuntimeError("Redis backend not initialized")
        return self._redis

    async def publish(
        self,
        queue: str,
        payload: Dict[str, Any],
        *,
        priority: MessagePriority = MessagePriority.NORMAL,
        headers: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish a message to the queue."""
        await self.initialize()

        envelope = MessageEnvelope(
            message_id=str(uuid.uuid4()),
            queue=queue,
            payload=payload,
            priority=priority,
            headers=headers or {},
        )

        if self._using_fallback:
            await self._put_fallback(queue, envelope)
        else:
            raw = json.dumps(envelope.to_dict(), default=str)
            key = self._queue_key(queue, priority)
            r = self._require_redis()
            res1 = r.rpush(key, raw)
            await _await_if_awaitable(res1)
            res2 = r.expire(key, self.config.retention_seconds)
            await _await_if_awaitable(res2)

        return envelope.message_id

    async def consume(
        self,
        queue: str,
        *,
        timeout: Optional[int] = None,
    ) -> Optional[MessageEnvelope]:
        """Consume the next available message."""
        await self.initialize()
        effective_timeout = timeout if timeout is not None else self.config.poll_interval_seconds

        if self._using_fallback:
            return await self._consume_fallback(queue, effective_timeout)

        keys = [
            self._queue_key(queue, priority)
            for priority in (
                MessagePriority.CRITICAL,
                MessagePriority.HIGH,
                MessagePriority.NORMAL,
                MessagePriority.LOW,
            )
        ]

        r = self._require_redis()
        result = r.blpop(keys, timeout=effective_timeout)
        result = await _await_if_awaitable(result)
        if not result:
            return None

        _, raw = result
        data = self._decode(raw)
        envelope = MessageEnvelope.from_dict(json.loads(data))
        await self._mark_pending(queue, envelope)
        return envelope

    async def ack(self, queue: str, message_id: str) -> bool:
        """Acknowledge successful message processing."""
        await self.initialize()

        if self._using_fallback:
            async with self._fallback_lock:
                pending = self._fallback_pending.setdefault(queue, {})
                return pending.pop(message_id, None) is not None

        pending_key = self._pending_key(queue)
        r = self._require_redis()
        removed_res = r.hdel(pending_key, message_id)
        removed = await _await_if_awaitable(removed_res)
        return bool(removed)

    async def requeue_stale(self, queue: str) -> int:
        """
        Requeue messages whose visibility window expired.

        Returns:
            Number of messages requeued.
        """
        await self.initialize()

        if self._using_fallback:
            return await self._requeue_fallback(queue)

        pending_key = self._pending_key(queue)
        r = self._require_redis()
        pending_res = r.hgetall(pending_key)
        pending_messages = await _await_if_awaitable(pending_res)
        if not pending_messages:
            return 0

        now = time.time()
        requeued = 0
        for message_id, raw in pending_messages.items():
            entry = json.loads(self._decode(raw))
            deadline = entry.get("visibility_deadline", 0)
            if deadline > now:
                continue

            data = entry.get("message", {})
            envelope = MessageEnvelope.from_dict(data)
            envelope.retries = entry.get("retries", envelope.retries) + 1
            r2 = self._require_redis()
            res3 = r2.rpush(
                self._queue_key(queue, envelope.priority),
                json.dumps(envelope.to_dict(), default=str),
            )
            await _await_if_awaitable(res3)
            res4 = r2.hdel(pending_key, message_id)
            await _await_if_awaitable(res4)
            requeued += 1

        if requeued:
            logger.info("Requeued %s stale messages for queue %s", requeued, queue)
        return requeued

    async def get_stats(self, queue: str) -> Dict[str, Any]:
        """Return lightweight queue statistics."""
        await self.initialize()

        if self._using_fallback:
            async with self._fallback_lock:
                pending = self._fallback_pending.get(queue, {})
                queued = self._fallback_queues.get(queue)
                size = queued.qsize() if queued else 0
                return {"backend": "memory", "queued": size, "pending": len(pending)}

        counts = {}
        for priority in MessagePriority:
            key = self._queue_key(queue, priority)
            r = self._require_redis()
            llen_res = r.llen(key)
            counts[priority.name.lower()] = await _await_if_awaitable(llen_res)

        hlen_res = r.hlen(self._pending_key(queue))
        pending_count = await _await_if_awaitable(hlen_res)
        counts["pending"] = pending_count
        counts["backend"] = "redis"
        return counts

    async def _put_fallback(self, queue: str, envelope: MessageEnvelope) -> None:
        async with self._fallback_lock:
            if queue not in self._fallback_queues:
                self._fallback_queues[queue] = asyncio.PriorityQueue(
                    maxsize=self.config.max_fallback_queue_size
                )

            priority_queue: asyncio.PriorityQueue[DistributedMessageQueue.PriorityItem] = (
                self._fallback_queues[queue]
            )
            if priority_queue.full():
                # Drop lowest priority entry to make space
                try:
                    priority_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

            entry = (int(envelope.priority), self._message_counter, envelope)
            self._message_counter += 1
            await priority_queue.put(entry)

    async def _consume_fallback(self, queue: str, timeout: int) -> Optional[MessageEnvelope]:
        async with self._fallback_lock:
            if queue not in self._fallback_queues:
                self._fallback_queues[queue] = asyncio.PriorityQueue()
            priority_queue: asyncio.PriorityQueue[DistributedMessageQueue.PriorityItem] = (
                self._fallback_queues[queue]
            )

        try:
            item: DistributedMessageQueue.PriorityItem = await asyncio.wait_for(
                priority_queue.get(), timeout=timeout
            )
        except asyncio.TimeoutError:
            return None

        _, _, envelope = item
        async with self._fallback_lock:
            pending = self._fallback_pending.setdefault(queue, {})
            pending[envelope.message_id] = envelope
        return envelope

    async def _requeue_fallback(self, queue: str) -> int:
        async with self._fallback_lock:
            pending = self._fallback_pending.get(queue, {})
            if not pending:
                return 0

            queued: asyncio.PriorityQueue[DistributedMessageQueue.PriorityItem] = (
                self._fallback_queues.setdefault(queue, asyncio.PriorityQueue())
            )
            requeued = 0
            for message_id, envelope in list(pending.items()):
                entry: DistributedMessageQueue.PriorityItem = (
                    int(envelope.priority),
                    self._message_counter,
                    envelope,
                )
                self._message_counter += 1
                await queued.put(entry)
                requeued += 1
                pending.pop(message_id, None)

            return requeued

    async def _mark_pending(self, queue: str, envelope: MessageEnvelope) -> None:
        entry = {
            "message": envelope.to_dict(),
            "visibility_deadline": time.time() + self.config.visibility_timeout,
            "retries": envelope.retries,
        }
        r = self._require_redis()
        hset_res = r.hset(
            self._pending_key(queue), envelope.message_id, json.dumps(entry, default=str)
        )
        await _await_if_awaitable(hset_res)
        exp_res = r.expire(self._pending_key(queue), self.config.retention_seconds)
        await _await_if_awaitable(exp_res)

    @staticmethod
    def _decode(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        if isinstance(value, str):
            return value
        return str(value)


# Global queue instance used by the application
distributed_message_queue = DistributedMessageQueue()
