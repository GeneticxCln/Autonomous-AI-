import pytest

from agent_system.distributed_message_queue import DistributedMessageQueue, MessagePriority
from agent_system.distributed_state_manager import DistributedStateManager
from agent_system.service_registry import ServiceRegistry


@pytest.mark.asyncio
async def test_message_queue_fallback_publish_consume_ack():
    queue = DistributedMessageQueue(force_fallback=True)
    await queue.initialize()

    message_id = await queue.publish(
        "test-queue",
        {"payload": "data"},
        priority=MessagePriority.HIGH,
        headers={"source": "unit-test"},
    )

    envelope = await queue.consume("test-queue", timeout=1)
    assert envelope is not None
    assert envelope.message_id == message_id
    assert envelope.payload["payload"] == "data"
    assert await queue.ack("test-queue", envelope.message_id) is True

    # Ensure requeue works when pending contains items
    await queue.publish("test-queue", {"payload": "retry"}, priority=MessagePriority.NORMAL)
    envelope = await queue.consume("test-queue", timeout=1)
    assert envelope is not None
    requeued = await queue.requeue_stale("test-queue")
    # In fallback mode pending entries are immediately requeued
    assert requeued == 1


@pytest.mark.asyncio
async def test_service_registry_lifecycle():
    registry = ServiceRegistry(force_fallback=True)
    await registry.initialize()

    instance = await registry.register_service(
        "api",
        host="localhost",
        port=8000,
        metadata={"role": "primary"},
        ttl_seconds=5,
    )
    discovered = await registry.discover("api")
    assert discovered
    assert discovered[0].instance_id == instance.instance_id

    assert await registry.heartbeat("api", instance.instance_id)
    assert await registry.deregister("api", instance.instance_id)
    assert await registry.discover("api") == []


@pytest.mark.asyncio
async def test_distributed_state_manager_locking_and_updates():
    manager = DistributedStateManager(force_fallback=True)
    await manager.initialize()

    record = await manager.set_state("cluster", "status", {"healthy": True})
    assert record.version == 1
    assert record.value["healthy"] is True

    updated = await manager.update_state("cluster", "status", {"healthy": False, "nodes": 3})
    assert updated is not None
    assert updated.version == 2
    assert updated.value["nodes"] == 3

    owner_id = await manager.acquire_lock("workflow")
    assert owner_id is not None
    assert await manager.release_lock("workflow", owner_id)
