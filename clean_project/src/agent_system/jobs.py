"""
Concrete job functions executed by background workers.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

from .agent import AutonomousAgent
from .job_definitions import AgentExecutionPayload, JobStatus, JobType
from .job_manager import job_store

logger = logging.getLogger(__name__)


async def execute_agent_job_async(job_id: str) -> Dict[str, Any]:
    """
    Execute an agent in the background.

    Args:
        job_id: Identifier stored in the job table.

    Returns:
        Result metadata persisted to the job record.
    """
    job_record = await job_store.get_job(job_id)
    if not job_record:
        raise RuntimeError(f"Job {job_id} not found")

    payload = AgentExecutionPayload(**job_record["parameters"])
    logger.info("Starting agent execution job %s (agent=%s)", job_id, payload.agent_id)
    await job_store.mark_job_running(job_id)

    agent = AutonomousAgent()
    start = time.perf_counter()
    result: Dict[str, Any] = {"job_id": job_id, "agent_id": payload.agent_id}

    try:
        await agent.run_async(
            max_cycles=payload.max_cycles,
            max_concurrent_goals=payload.max_concurrent_goals,
        )
        duration = time.perf_counter() - start
        result["duration_seconds"] = round(duration, 2)
        result["status"] = JobStatus.SUCCEEDED.value
        await job_store.mark_job_succeeded(job_id, result=result)
        logger.info("Completed job %s in %.2fs", job_id, duration)
        return result
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Job %s failed: %s", job_id, exc)
        result["status"] = JobStatus.FAILED.value
        await job_store.mark_job_failed(job_id, error=str(exc), result=result)
        raise
    finally:
        try:
            agent.stop()
        except Exception:  # pragma: no cover - best effort
            logger.debug("Agent cleanup failed for job %s", job_id)


def execute_agent_job(job_id: str) -> Dict[str, Any]:
    """Synchronous wrapper for contexts that cannot await."""
    return asyncio.run(execute_agent_job_async(job_id))


JOB_TYPE_TO_HANDLER = {
    JobType.AGENT_EXECUTION.value: execute_agent_job_async,
}
