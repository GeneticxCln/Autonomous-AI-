"""
Dedicated worker service that consumes distributed job queues.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
from typing import Optional
import datetime

from .cache_manager import cache_manager
from .config_simple import settings
from .distributed_message_queue import distributed_message_queue
from .job_definitions import AGENT_JOB_QUEUE, JobQueueMessage
from .job_manager import job_store
from .jobs import JOB_TYPE_TO_HANDLER
from .service_registry import service_registry
from .database_models import db_manager, AgentCapabilityModel

logger = logging.getLogger(__name__)


class AgentWorker:
    """Consumes the distributed queue and executes registered jobs."""

    def __init__(self, *, queue_name: str = AGENT_JOB_QUEUE, poll_interval: int = 1):
        self.queue_name = queue_name
        self.poll_interval = poll_interval
        self._shutdown = asyncio.Event()
        self._service_instance = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._current_job_id: Optional[str] = None

    async def run(self):
        """Bootstrap infrastructure and start consuming messages."""
        await self._bootstrap()

        try:
            await self._consume_loop()
        except asyncio.CancelledError:
            self._shutdown.set()
            raise
        finally:
            await self._teardown()

    async def _bootstrap(self):
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        logger.info("Initializing agent worker for queue '%s'", self.queue_name)

        await cache_manager.connect()
        await distributed_message_queue.initialize()
        await service_registry.initialize()

        metadata = {
            "role": "agent_worker",
            "queue": self.queue_name,
            "node_id": getattr(settings, "DISTRIBUTED_NODE_ID", "worker"),
        }
        self._service_instance = await service_registry.register_service(
            "agent-worker",
            metadata=metadata,
        )
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Register capabilities (basic executor profile)
        try:
            with db_manager.get_session() as session:
                instance_id = self._service_instance.instance_id if self._service_instance else metadata["node_id"]
                existing = (
                    session.query(AgentCapabilityModel)
                    .filter(AgentCapabilityModel.instance_id == instance_id)
                    .first()
                )
                base_caps = [
                    {
                        "name": "agent_execution",
                        "description": "Execute autonomous agent cycles",
                        "input_types": ["agent_id"],
                        "output_types": ["job_result"],
                        "complexity_level": "high",
                        "estimated_duration": 300,
                        "quality_requirements": ["reliability", "throughput"],
                    }
                ]
                if existing:
                    existing.agent_name = "Agent Worker"
                    existing.role = "executor"
                    existing.capabilities = base_caps
                    existing.expertise_domains = ["agent_runtime"]
                    existing.capacity = 1
                    existing.tool_scopes = ["tools:*"]
                    existing.capability_metadata = metadata
                    existing.heartbeat_at = datetime.datetime.now(datetime.UTC)
                    session.add(existing)
                else:
                    rec = AgentCapabilityModel(
                        instance_id=instance_id,
                        agent_name="Agent Worker",
                        role="executor",
                        capabilities=base_caps,
                        expertise_domains=["agent_runtime"],
                        capacity=1,
                        tool_scopes=["tools:*"],
                        capability_metadata=metadata,
                    )
                    session.add(rec)
                session.commit()
        except Exception:
            logger.debug("Capability registration skipped", exc_info=True)

    async def _consume_loop(self):
        while not self._shutdown.is_set():
            envelope = await distributed_message_queue.consume(
                self.queue_name, timeout=self.poll_interval
            )
            if envelope is None:
                continue

            payload = envelope.payload or {}
            message = JobQueueMessage(**payload)
            handler = JOB_TYPE_TO_HANDLER.get(message.job_type.value)

            if not handler:
                logger.warning("No handler registered for job type %s", message.job_type)
                await distributed_message_queue.ack(self.queue_name, envelope.message_id)
                continue

            self._current_job_id = message.job_id
            try:
                await handler(message.job_id)
                await distributed_message_queue.ack(self.queue_name, envelope.message_id)
            except Exception as exc:  # pragma: no cover - worker resilience
                logger.exception("Job %s failed during execution: %s", message.job_id, exc)
                await distributed_message_queue.ack(self.queue_name, envelope.message_id)
            finally:
                self._current_job_id = None

    async def _heartbeat_loop(self):
        interval = max(5, getattr(settings, "DISTRIBUTED_HEARTBEAT_INTERVAL", 15))
        while not self._shutdown.is_set():
            if self._service_instance:
                await service_registry.heartbeat(
                    self._service_instance.service_name, self._service_instance.instance_id
                )
            if self._current_job_id:
                job_store.record_heartbeat(self._current_job_id)
            # Update capability heartbeat
            try:
                if self._service_instance:
                    with db_manager.get_session() as session:
                        session.query(AgentCapabilityModel).filter(
                            AgentCapabilityModel.instance_id == self._service_instance.instance_id
                        ).update({"heartbeat_at": datetime.datetime.now(datetime.UTC)})
                        session.commit()
            except Exception:
                logger.debug("Capability heartbeat update failed", exc_info=True)
            await asyncio.sleep(interval)

    async def shutdown(self):
        """Public method to request a graceful shutdown."""
        self._shutdown.set()

    async def _teardown(self):
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
        if self._service_instance:
            await service_registry.deregister(
                self._service_instance.service_name, self._service_instance.instance_id
            )
        await cache_manager.disconnect()
        logger.info("Worker shutdown complete")


async def _run_worker(args):
    worker = AgentWorker(queue_name=args.queue, poll_interval=args.poll_interval)
    try:
        await worker.run()
    finally:
        await worker.shutdown()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent background worker")
    parser.add_argument(
        "--queue",
        default=AGENT_JOB_QUEUE,
        help="Queue to consume (default: agent.jobs)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=1,
        help="Seconds to wait for new messages before polling again",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _handle_shutdown():
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_shutdown)

    try:
        loop.run_until_complete(_run_worker(args))
    except KeyboardInterrupt:
        logger.info("Worker interrupted, shutting down")
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            loop.run_until_complete(asyncio.gather(*pending))
        loop.close()


if __name__ == "__main__":
    main()
