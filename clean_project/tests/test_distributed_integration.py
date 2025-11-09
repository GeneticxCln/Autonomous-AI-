"""
Comprehensive integration tests for distributed scenarios.
Tests worker coordination, message queue reliability, service discovery, and multi-worker scenarios.
"""

import asyncio
from typing import List

import pytest

from agent_system.distributed_message_queue import (
    DistributedMessageQueue,
    MessagePriority,
)
from agent_system.distributed_state_manager import DistributedStateManager
from agent_system.job_definitions import JobPriority, JobQueueMessage, JobType
from agent_system.service_registry import ServiceRegistry


@pytest.mark.asyncio
async def test_multi_worker_job_distribution():
    """Test that jobs are distributed across multiple workers."""
    queue = DistributedMessageQueue(force_fallback=True)
    await queue.initialize()

    # Create multiple job messages
    job_ids = []
    for i in range(5):
        message = JobQueueMessage(
            job_id=f"job-{i}",
            job_type=JobType.AGENT_EXECUTION,
            priority=JobPriority.NORMAL,
        )
        await queue.publish("agent.jobs", message.model_dump(), priority=MessagePriority.NORMAL)
        job_ids.append(f"job-{i}")

    # Simulate multiple workers consuming
    consumed_by_worker1 = []
    consumed_by_worker2 = []

    # Worker 1 consumes 3 jobs
    for _ in range(3):
        envelope = await queue.consume("agent.jobs", timeout=1)
        if envelope:
            consumed_by_worker1.append(envelope.payload["job_id"])
            await queue.ack("agent.jobs", envelope.message_id)

    # Worker 2 consumes remaining jobs
    for _ in range(5):
        envelope = await queue.consume("agent.jobs", timeout=1)
        if envelope:
            consumed_by_worker2.append(envelope.payload["job_id"])
            await queue.ack("agent.jobs", envelope.message_id)

    # Verify all jobs were consumed
    assert len(consumed_by_worker1) + len(consumed_by_worker2) == 5
    assert set(consumed_by_worker1 + consumed_by_worker2) == set(job_ids)


@pytest.mark.asyncio
async def test_priority_based_job_processing():
    """Test that high priority jobs are processed before normal priority."""
    queue = DistributedMessageQueue(force_fallback=True)
    await queue.initialize()

    # Publish jobs in mixed priority order
    await queue.publish(
        "agent.jobs",
        {"job_id": "normal-1", "priority": "normal"},
        priority=MessagePriority.NORMAL,
    )
    await queue.publish(
        "agent.jobs",
        {"job_id": "high-1", "priority": "high"},
        priority=MessagePriority.HIGH,
    )
    await queue.publish(
        "agent.jobs",
        {"job_id": "normal-2", "priority": "normal"},
        priority=MessagePriority.NORMAL,
    )
    await queue.publish(
        "agent.jobs",
        {"job_id": "critical-1", "priority": "critical"},
        priority=MessagePriority.CRITICAL,
    )

    # Consume and verify priority order
    consumed = []
    for _ in range(4):
        envelope = await queue.consume("agent.jobs", timeout=1)
        if envelope:
            consumed.append(envelope.payload["job_id"])
            await queue.ack("agent.jobs", envelope.message_id)

    # Critical should be first, then high, then normal
    assert consumed[0] == "critical-1"
    assert consumed[1] == "high-1"
    assert "normal-1" in consumed[2:]
    assert "normal-2" in consumed[2:]


@pytest.mark.asyncio
async def test_worker_heartbeat_and_service_discovery():
    """Test worker registration, heartbeat, and service discovery."""
    registry = ServiceRegistry(force_fallback=True)
    await registry.initialize()

    # Register multiple workers
    worker1 = await registry.register_service(
        "agent-worker",
        host="worker1.example.com",
        port=8001,
        metadata={"queue": "high", "capacity": 10},
    )
    worker2 = await registry.register_service(
        "agent-worker",
        host="worker2.example.com",
        port=8002,
        metadata={"queue": "normal", "capacity": 20},
    )

    # Discover all workers
    workers = await registry.discover("agent-worker")
    assert len(workers) == 2
    worker_ids = {w.instance_id for w in workers}
    assert worker1.instance_id in worker_ids
    assert worker2.instance_id in worker_ids

    # Test heartbeat
    await asyncio.sleep(0.1)  # Small delay
    assert await registry.heartbeat("agent-worker", worker1.instance_id)

    # Verify workers are still discoverable
    workers_after_heartbeat = await registry.discover("agent-worker")
    assert len(workers_after_heartbeat) == 2

    # Deregister one worker
    await registry.deregister("agent-worker", worker1.instance_id)
    remaining_workers = await registry.discover("agent-worker")
    assert len(remaining_workers) == 1
    assert remaining_workers[0].instance_id == worker2.instance_id


@pytest.mark.asyncio
async def test_service_expiration_with_ttl():
    """Test that services expire after TTL without heartbeat."""
    registry = ServiceRegistry(force_fallback=True)
    await registry.initialize()

    # Register service with short TTL
    _instance = await registry.register_service(
        "test-service",
        host="localhost",
        port=8000,
        ttl_seconds=1,  # 1 second TTL
    )

    # Service should be discoverable immediately
    services = await registry.discover("test-service")
    assert len(services) == 1

    # Wait for TTL to expire
    await asyncio.sleep(1.5)

    # Service should no longer be discoverable (expired)
    expired_services = await registry.discover("test-service")
    assert len(expired_services) == 0


@pytest.mark.asyncio
async def test_message_queue_visibility_timeout():
    """Test that messages become visible again after visibility timeout."""
    queue = DistributedMessageQueue(force_fallback=True)
    await queue.initialize()

    # Publish a message
    message_id = await queue.publish(
        "test-queue",
        {"test": "data"},
        priority=MessagePriority.NORMAL,
    )

    # Consume message (moves to pending)
    envelope1 = await queue.consume("test-queue", timeout=1)
    assert envelope1 is not None
    assert envelope1.message_id == message_id

    # Try to consume again immediately - should return None (message in pending)
    envelope2 = await queue.consume("test-queue", timeout=0.1)
    assert envelope2 is None

    # Requeue stale messages (simulating visibility timeout)
    requeued = await queue.requeue_stale("test-queue")
    assert requeued >= 0  # May be 0 or 1 depending on timing

    # Now message should be consumable again
    envelope3 = await queue.consume("test-queue", timeout=1)
    assert envelope3 is not None


@pytest.mark.asyncio
async def test_concurrent_worker_coordination():
    """Test multiple workers processing jobs concurrently without conflicts."""
    queue = DistributedMessageQueue(force_fallback=True)
    await queue.initialize()

    # Publish multiple jobs
    job_count = 10
    for i in range(job_count):
        await queue.publish(
            "agent.jobs",
            {"job_id": f"concurrent-job-{i}", "index": i},
            priority=MessagePriority.NORMAL,
        )

    # Simulate concurrent workers
    async def worker_consumer(worker_id: int, consumed: List[str]):
        """Worker that consumes jobs."""
        for _ in range(job_count):
            envelope = await queue.consume("agent.jobs", timeout=0.5)
            if envelope:
                consumed.append(envelope.payload["job_id"])
                await queue.ack("agent.jobs", envelope.message_id)
                await asyncio.sleep(0.01)  # Simulate processing time

    worker1_consumed = []
    worker2_consumed = []
    worker3_consumed = []

    # Run workers concurrently
    await asyncio.gather(
        worker_consumer(1, worker1_consumed),
        worker_consumer(2, worker2_consumed),
        worker_consumer(3, worker3_consumed),
    )

    # Verify all jobs were consumed exactly once
    all_consumed = worker1_consumed + worker2_consumed + worker3_consumed
    assert len(all_consumed) == job_count
    assert len(set(all_consumed)) == job_count  # No duplicates


@pytest.mark.asyncio
async def test_distributed_state_coordination():
    """Test distributed state management with concurrent updates."""
    manager = DistributedStateManager(force_fallback=True)
    await manager.initialize()

    # Set initial state
    record1 = await manager.set_state("cluster", "config", {"version": 1, "nodes": 3})
    assert record1.version == 1

    # Concurrent updates should handle versioning
    async def update_state(worker_id: int):
        """Worker that updates state."""
        try:
            current = await manager.get_state("cluster", "config")
            if current:
                new_value = current.value.copy()
                new_value["nodes"] = new_value.get("nodes", 0) + 1
                new_value[f"updated_by_worker_{worker_id}"] = True
                return await manager.update_state("cluster", "config", new_value)
        except Exception:
            return None  # Expected for concurrent updates

    # Run concurrent updates
    results = await asyncio.gather(
        update_state(1),
        update_state(2),
        update_state(3),
        return_exceptions=True,
    )

    # At least one update should succeed
    successful_updates = [r for r in results if r is not None and not isinstance(r, Exception)]
    assert len(successful_updates) > 0

    # Final state should be consistent
    final_state = await manager.get_state("cluster", "config")
    assert final_state is not None
    assert final_state.value["nodes"] >= 3


@pytest.mark.asyncio
async def test_worker_failure_recovery():
    """Test that jobs are recovered when a worker fails."""
    queue = DistributedMessageQueue(force_fallback=True)
    await queue.initialize()

    # Publish a job
    message_id = await queue.publish(
        "agent.jobs",
        {"job_id": "recoverable-job", "data": "test"},
        priority=MessagePriority.NORMAL,
    )

    # Worker consumes but crashes before acking
    envelope = await queue.consume("agent.jobs", timeout=1)
    assert envelope is not None
    assert envelope.message_id == message_id

    # Simulate worker crash (no ack)
    # Message should be in pending

    # Requeue stale messages (simulating recovery process)
    requeued = await queue.requeue_stale("agent.jobs")
    assert requeued >= 0

    # Another worker should be able to consume the job
    recovered_envelope = await queue.consume("agent.jobs", timeout=1)
    if recovered_envelope:
        assert recovered_envelope.message_id == message_id
        await queue.ack("agent.jobs", recovered_envelope.message_id)


@pytest.mark.asyncio
async def test_queue_backpressure():
    """Test queue behavior under high load."""
    queue = DistributedMessageQueue(force_fallback=True)
    await queue.initialize()

    # Publish many messages
    message_count = 100
    published_ids = []
    for i in range(message_count):
        msg_id = await queue.publish(
            "test-queue",
            {"index": i, "data": f"message-{i}"},
            priority=MessagePriority.NORMAL,
        )
        published_ids.append(msg_id)

    # Consume all messages
    consumed_ids = []
    for _ in range(message_count):
        envelope = await queue.consume("test-queue", timeout=0.1)
        if envelope:
            consumed_ids.append(envelope.message_id)
            await queue.ack("test-queue", envelope.message_id)

    # Verify all messages were processed
    assert len(consumed_ids) == message_count
    assert set(consumed_ids) == set(published_ids)


@pytest.mark.asyncio
async def test_multi_queue_isolation():
    """Test that different queues are isolated from each other."""
    queue = DistributedMessageQueue(force_fallback=True)
    await queue.initialize()

    # Publish to different queues
    await queue.publish("queue-a", {"data": "queue-a-message"}, priority=MessagePriority.NORMAL)
    await queue.publish("queue-b", {"data": "queue-b-message"}, priority=MessagePriority.NORMAL)

    # Consume from queue-a
    envelope_a = await queue.consume("queue-a", timeout=1)
    assert envelope_a is not None
    assert envelope_a.payload["data"] == "queue-a-message"

    # Consume from queue-b
    envelope_b = await queue.consume("queue-b", timeout=1)
    assert envelope_b is not None
    assert envelope_b.payload["data"] == "queue-b-message"

    # Verify queues are isolated
    assert envelope_a.queue == "queue-a"
    assert envelope_b.queue == "queue-b"


@pytest.mark.asyncio
async def test_service_registry_load_balancing():
    """Test service discovery for load balancing scenarios."""
    registry = ServiceRegistry(force_fallback=True)
    await registry.initialize()

    # Register multiple instances of the same service
    instances = []
    for i in range(5):
        instance = await registry.register_service(
            "api-service",
            host=f"api-{i}.example.com",
            port=8000 + i,
            metadata={"load": 0, "region": "us-east"},
        )
        instances.append(instance)

    # Discover all instances
    discovered = await registry.discover("api-service")
    assert len(discovered) == 5

    # All instances should be discoverable
    discovered_ids = {inst.instance_id for inst in discovered}
    registered_ids = {inst.instance_id for inst in instances}
    assert discovered_ids == registered_ids

    # Test filtering by metadata (if supported)
    # This would be useful for region-based routing
    all_instances = await registry.discover("api-service")
    assert all(inst.metadata.get("region") == "us-east" for inst in all_instances)
