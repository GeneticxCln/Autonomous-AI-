"""
Distributed Message Queue
Provides cross-node messaging with Redis backend and in-memory fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, Optional

from .cache_manager import cache_manager
from .config_simple import settings

logger = logging.getLogger(__name__)


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
            priority_value if isinstance(priority_value, MessagePriority) else MessagePriority[priority_value]
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

    def __init__(
        self,
        config: Optional[MessageQueueConfig] = None,
        *,
        force_fallback: bool = False,
    ):
        self.config = config or MessageQueueConfig()
        self.force_fallback = force_fallback
        self._is_initialized = False
        self._using_fallback = force_fallback
        self._fallback_queues: Dict[str, asyncio.PriorityQueue] = {}
        self._fallback_pending: Dict[str, Dict[str, MessageEnvelope]] = {}
        self._fallback_lock = asyncio.Lock()
        self._message_counter = 0
        self._redis = None

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
            await cache_manager.connect()

        if cache_manager._is_connected and cache_manager.redis_client:
            self._redis = cache_manager.redis_client
            self._using_fallback = False
            self._is_initialized = True
            logger.info("Distributed message queue connected to Redis backend")
            return True

        self._using_fallback = True
        self._is_initialized = True
        logger.warning("Redis unavailable, distributed message queue falling back to in-memory backend")
        return True

    def _queue_key(self, queue: str, priority: MessagePriority) -> str:
        return f"{self.config.namespace}:{queue}:{priority.name.lower()}"

    def _pending_key(self, queue: str) -> str:
        return f"{self.config.namespace}:{queue}:pending"

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
            await self._redis.rpush(key, raw)
            await self._redis.expire(key, self.config.retention_seconds)

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

        result = await self._redis.blpop(keys, timeout=effective_timeout)
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
        removed = await self._redis.hdel(pending_key, message_id)
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
        pending_messages = await self._redis.hgetall(pending_key)
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
            await self._redis.rpush(
                self._queue_key(queue, envelope.priority),
                json.dumps(envelope.to_dict(), default=str),
            )
            await self._redis.hdel(pending_key, message_id)
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
            counts[priority.name.lower()] = await self._redis.llen(key)

        pending = await self._redis.hlen(self._pending_key(queue))
        counts["pending"] = pending
        counts["backend"] = "redis"
        return counts

    async def _put_fallback(self, queue: str, envelope: MessageEnvelope) -> None:
        async with self._fallback_lock:
            if queue not in self._fallback_queues:
                self._fallback_queues[queue] = asyncio.PriorityQueue(
                    maxsize=self.config.max_fallback_queue_size
                )

            priority_queue = self._fallback_queues[queue]
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
            priority_queue = self._fallback_queues[queue]

        try:
            item = await asyncio.wait_for(priority_queue.get(), timeout=timeout)
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

            queued = self._fallback_queues.setdefault(queue, asyncio.PriorityQueue())
            requeued = 0
            for message_id, envelope in list(pending.items()):
                entry = (int(envelope.priority), self._message_counter, envelope)
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
        await self._redis.hset(self._pending_key(queue), envelope.message_id, json.dumps(entry, default=str))
        await self._redis.expire(self._pending_key(queue), self.config.retention_seconds)

    @staticmethod
    def _decode(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value


# Global queue instance used by the application
distributed_message_queue = DistributedMessageQueue()
