"""
Redis Queue (RQ) Background Task Processing
Enterprise-grade background job processing with Redis
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine, Dict, Optional, cast

from .cache_manager import cache_manager

# Use synchronous redis client for RQ (rq expects sync redis-py)
redis_sync: Any | None = None
try:
    import redis as _redis_sync  # import under alias to avoid redefinition warnings
    from redis import Redis as SyncRedis
    REDIS_SYNC_IMPORT_ERROR: Optional[Exception] = None
except Exception as _exc:
    REDIS_SYNC_IMPORT_ERROR = _exc
    if TYPE_CHECKING:  # pragma: no cover
        from redis import Redis as SyncRedis
    else:
        SyncRedis = Any
else:
    redis_sync = _redis_sync

rq: Any | None = None
try:
    import rq as _rq  # import under alias to avoid redefinition warnings
    from rq import Queue
    from rq.job import Job
    from rq.registry import (
        DeferredJobRegistry,
        FailedJobRegistry,
        FinishedJobRegistry,
        ScheduledJobRegistry,
        StartedJobRegistry,
    )
    from rq_scheduler import Scheduler
    RQ_IMPORT_ERROR: Optional[Exception] = None
except Exception as _exc:  # ModuleNotFoundError or runtime import error
    RQ_IMPORT_ERROR = _exc
    if TYPE_CHECKING:
        from rq import Queue as Queue  # pragma: no cover
        from rq.job import Job as Job  # pragma: no cover
        from rq.registry import (  # pragma: no cover
            DeferredJobRegistry,
            FailedJobRegistry,
            FinishedJobRegistry,
            ScheduledJobRegistry,
            StartedJobRegistry,
        )
        from rq_scheduler import Scheduler as Scheduler  # pragma: no cover
    else:
        Queue = Any
        Job = Any
        Scheduler = Any
        DeferredJobRegistry = Any
        FailedJobRegistry = Any
        FinishedJobRegistry = Any
        ScheduledJobRegistry = Any
        StartedJobRegistry = Any
else:
    rq = _rq

logger = logging.getLogger(__name__)


class QueuePriority(Enum):
    """Queue priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TaskConfig:
    """Task queue configuration."""

    redis_url: str = "redis://localhost:6379/0"
    default_queue: str = "default"
    high_queue: str = "high"
    low_queue: str = "low"
    result_ttl: int = 3600  # 1 hour
    failure_ttl: int = 86400  # 24 hours
    max_retries: int = 3
    retry_delay: int = 60  # 1 minute
    connection_pool_size: int = 20
    worker_timeout: int = 1800  # 30 minutes


class TaskQueueManager:
    """
    Enterprise Redis Queue manager with:
    - Multiple priority queues
    - Job scheduling and delayed execution
    - Result caching and retrieval
    - Job monitoring and statistics
    - Retry mechanisms and error handling
    """

    def __init__(self, config: Optional[TaskConfig] = None):
        self.config = config or TaskConfig()
        self.queues: Dict[str, Queue] = {}
        self.scheduler: Optional[Scheduler] = None
        self._rq_connection: Optional[SyncRedis] = None
        self._is_initialized = False

    def initialize(self) -> bool:
        """Initialize Redis Queue connections."""
        try:
            if rq is None:
                detail = f": {RQ_IMPORT_ERROR}" if RQ_IMPORT_ERROR else ""
                raise RuntimeError(
                    "rq/rq-scheduler packages are required for the task queue"
                    f"{detail}. Install 'rq>=1.15' and 'rq-scheduler' to enable background jobs."
                )

            if redis_sync is None:
                detail = f": {REDIS_SYNC_IMPORT_ERROR}" if REDIS_SYNC_IMPORT_ERROR else ""
                raise RuntimeError(
                    "redis-py package is required for the task queue"
                    f"{detail}. Install 'redis>=5' to enable background jobs."
                )
            # Set Redis URL for RQ (rq can use this internally)
            os.environ["REDIS_URL"] = self.config.redis_url

            # Create a synchronous Redis connection for RQ if possible
            if redis_sync is not None:
                self._rq_connection = cast(SyncRedis, redis_sync.from_url(self.config.redis_url))
            else:
                self._rq_connection = None

            # Create queues with different priorities
            self.queues = {
                QueuePriority.CRITICAL.value: Queue(
                    QueuePriority.CRITICAL.value,
                    connection=self._rq_connection,
                    default_timeout=self.config.worker_timeout,
                ),
                QueuePriority.HIGH.value: Queue(
                    QueuePriority.HIGH.value,
                    connection=self._rq_connection,
                    default_timeout=self.config.worker_timeout,
                ),
                QueuePriority.NORMAL.value: Queue(
                    QueuePriority.NORMAL.value,
                    connection=self._rq_connection,
                    default_timeout=self.config.worker_timeout,
                ),
                QueuePriority.LOW.value: Queue(
                    QueuePriority.LOW.value,
                    connection=self._rq_connection,
                    default_timeout=self.config.worker_timeout,
                ),
            }

            # Initialize scheduler for delayed jobs
            self.scheduler = Scheduler(
                queue=self.queues[QueuePriority.NORMAL.value], connection=self._rq_connection
            )

            self._is_initialized = True

            logger.info("✅ Redis Queue (RQ) initialized with priority queues")
            return True

        except Exception as e:
            logger.error(f"❌ Redis Queue initialization failed: {e}")
            self._is_initialized = False
            raise

    def get_queue(self, priority: QueuePriority) -> Queue:
        """Get queue by priority."""
        if not self._is_initialized:
            raise RuntimeError("TaskQueueManager not initialized")

        return self.queues[priority.value]

    def enqueue_job(
        self,
        func: Callable[..., Any],
        *args: Any,
        priority: QueuePriority = QueuePriority.NORMAL,
        timeout: Optional[int] = None,
        ttl: Optional[int] = None,
        **kwargs: Any,
    ) -> Job:
        """
        Enqueue a job with optional parameters.

        Args:
            func: Function to execute
            args: Function arguments
            priority: Job priority
            timeout: Job timeout in seconds
            ttl: Result TTL in seconds
            kwargs: Additional job parameters
        """
        if not self._is_initialized:
            raise RuntimeError("TaskQueueManager not initialized")

        queue = self.get_queue(priority)

        job_kwargs = {
            "timeout": timeout or self.config.worker_timeout,
            "result_ttl": ttl or self.config.result_ttl,
            "failure_ttl": self.config.failure_ttl,
            "kwargs": kwargs,
        }

        job = queue.enqueue(func, *args, **job_kwargs)

        logger.info(f"📋 Job enqueued: {job.id} (priority: {priority.value})")
        return job

    def enqueue_job_with_retry(
        self,
        func: Callable[..., Any],
        *args: Any,
        priority: QueuePriority = QueuePriority.NORMAL,
        max_retries: int | None = None,
        retry_delay: int | None = None,
        **kwargs: Any,
    ) -> Job:
        """
        Enqueue a job with automatic retry on failure.
        """
        if not self._is_initialized:
            raise RuntimeError("TaskQueueManager not initialized")

        queue = self.get_queue(priority)

        def job_with_retry() -> Any:
            """Wrapper function that handles retries."""
            import time
            from functools import wraps

            @wraps(func)
            def wrapped_func(*args: Any, **kwargs: Any) -> Any:
                retries = max_retries or self.config.max_retries
                delay = retry_delay or self.config.retry_delay

                for attempt in range(retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        if attempt == retries:
                            logger.error(f"Job failed after {retries} retries: {e}")
                            raise e
                        else:
                            logger.warning(
                                f"Job attempt {attempt + 1} failed: {e}. Retrying in {delay}s..."
                            )
                            time.sleep(delay)

            return wrapped_func(*args, **kwargs)

        job = queue.enqueue(job_with_retry, *args, **kwargs)

        logger.info(f"📋 Job with retry enqueued: {job.id} (max_retries: {max_retries})")
        return job

    def schedule_job(
        self,
        func: Callable[..., Any],
        run_at: datetime,
        *args: Any,
        priority: QueuePriority = QueuePriority.NORMAL,
        **kwargs: Any,
    ) -> str:
        """
        Schedule a job to run at a specific time.
        """
        if not self._is_initialized:
            raise RuntimeError("TaskQueueManager not initialized")

        queue = self.get_queue(priority)

        job = queue.enqueue(func, *args, **kwargs)

        # Schedule the job
        assert self.scheduler is not None
        self.scheduler.enqueue_at(run_at, job)

        logger.info(f"⏰ Job scheduled: {job.id} (run at: {run_at})")
        return str(job.id)

    def schedule_job_interval(
        self,
        func: Callable[..., Any],
        interval_seconds: int,
        *args: Any,
        priority: QueuePriority = QueuePriority.NORMAL,
        **kwargs: Any,
    ) -> str:
        """
        Schedule a job to run at regular intervals.
        """
        if not self._is_initialized:
            raise RuntimeError("TaskQueueManager not initialized")

        job = self.get_queue(priority).enqueue(func, *args, **kwargs)

        # Schedule recurring job
        assert self.scheduler is not None
        self.scheduler.schedule(
            scheduled_time=datetime.now() + timedelta(seconds=interval_seconds),
            func=func,
            args=args,
            kwargs=kwargs,
            interval=interval_seconds,
            repeat=None,  # Infinite repeat
        )

        logger.info(f"🔄 Recurring job scheduled: {job.id} (interval: {interval_seconds}s)")
        return str(job.id)

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        if not self._is_initialized:
            return None

        try:
            return Job.fetch(job_id, connection=self._rq_connection)
        except Exception as e:
            logger.error(f"Error fetching job {job_id}: {e}")
            return None

    def get_job_result(self, job_id: str, timeout: int = 10) -> Optional[Any]:
        """Get job result, waiting if necessary."""
        job = self.get_job(job_id)
        if not job:
            return None

        try:
            result = job.result(timeout=timeout)
            return result
        except Exception as e:
            logger.error(f"Error getting job result {job_id}: {e}")
            return None

    def get_job_status(self, job_id: str) -> Optional[str]:
        """Get job status."""
        job = self.get_job(job_id)
        return job.get_status() if job else None

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        job = self.get_job(job_id)
        if not job:
            return False

        try:
            job.cancel()
            logger.info(f"❌ Job canceled: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error canceling job {job_id}: {e}")
            return False

    def get_queue_stats(self, priority: QueuePriority) -> Dict[str, Any]:
        """Get statistics for a specific queue."""
        if not self._is_initialized:
            return {"error": "TaskQueueManager not initialized"}

        queue = self.get_queue(priority)

        try:
            assert self.scheduler is not None
            stats = {
                "queue": priority.value,
                "size": len(queue),
                "started_registry": StartedJobRegistry(
                    queue=queue, connection=self._rq_connection
                ),
                "failed_registry": FailedJobRegistry(
                    queue=queue, connection=self._rq_connection
                ),
                "finished_registry": FinishedJobRegistry(
                    queue=queue, connection=self._rq_connection
                ),
                "scheduled_jobs": len(self.scheduler.get_jobs()),
            }

            # Get counts from registries
            registry_stats = {}
            for registry_name in ["started", "failed", "finished"]:
                registry_key = f"{registry_name}_registry"
                registry = stats[registry_key]
                count = 0
                try:
                    # Get job IDs from registry
                    if hasattr(registry, "get_job_ids"):
                        count = len(registry.get_job_ids())
                    elif hasattr(registry, "count"):
                        count = registry.count
                except Exception as e:
                    logger.warning(f"Error getting {registry_name} registry stats: {e}")
                    count = 0

                registry_stats[registry_name] = count

            return {
                "queue_name": priority.value,
                "queue_size": len(queue),
                "started_jobs": registry_stats["started"],
                "failed_jobs": registry_stats["failed"],
                "finished_jobs": registry_stats["finished"],
                "scheduled_jobs": stats["scheduled_jobs"],
            }

        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {"error": str(e)}

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all queues."""
        all_stats = {}

        for priority in QueuePriority:
            try:
                stats = self.get_queue_stats(priority)
                all_stats[priority.value] = stats
            except Exception as e:
                all_stats[priority.value] = {"error": str(e)}

        return all_stats

    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall queue statistics."""
        if not self._is_initialized:
            return {"error": "TaskQueueManager not initialized"}

        try:
            all_stats = self.get_all_stats()

            total_queued = 0
            total_started = 0
            total_failed = 0
            total_finished = 0
            total_scheduled = 0

            for priority_stats in all_stats.values():
                if "error" not in priority_stats:
                    total_queued += priority_stats.get("queue_size", 0)
                    total_started += priority_stats.get("started_jobs", 0)
                    total_failed += priority_stats.get("failed_jobs", 0)
                    total_finished += priority_stats.get("finished_jobs", 0)
                    total_scheduled += priority_stats.get("scheduled_jobs", 0)

            return {
                "total_queued": total_queued,
                "total_started": total_started,
                "total_failed": total_failed,
                "total_finished": total_finished,
                "total_scheduled": total_scheduled,
                "queue_details": all_stats,
                "redis_connection": "healthy" if cache_manager._is_connected else "disconnected",
            }

        except Exception as e:
            logger.error(f"Error getting overall stats: {e}")
            return {"error": str(e)}

    def cleanup_failed_jobs(self, older_than_days: int = 7) -> int:
        """Clean up old failed jobs."""
        if not self._is_initialized:
            return 0

        try:
            cutoff_date = datetime.now() - timedelta(days=older_than_days)
            cleaned_count = 0

            for queue in self.queues.values():
                failed_registry = FailedJobRegistry(
                    queue=queue, connection=self._rq_connection
                )

                # Get all job IDs from failed registry
                job_ids = failed_registry.get_job_ids()
                for job_id in job_ids:
                    job = self.get_job(job_id)
                    if job and job.ended_at and job.ended_at < cutoff_date:
                        # Remove from registry and delete job
                        failed_registry.remove(job, delete_job=True)
                        cleaned_count += 1

            logger.info(f"🧹 Cleaned up {cleaned_count} old failed jobs")
            return cleaned_count

        except Exception as e:
            logger.error(f"Error cleaning up failed jobs: {e}")
            return 0

    def stop_scheduler(self) -> None:
        """Stop the scheduler."""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("⏹️ Scheduler stopped")


# Global task queue manager instance
task_queue_manager = TaskQueueManager()


def _execute_job_callable(func_path: str, call_args: tuple[Any, ...], call_kwargs: Dict[str, Any]) -> Any:
    """Synchronously execute a job by importing the target function."""
    module_name, _, attr_path = func_path.rpartition(".")
    if not module_name:
        raise RuntimeError(f"Invalid job path: {func_path}")

    module = importlib.import_module(module_name)
    target: Any = module
    for attr in attr_path.split("."):
        target = getattr(target, attr)

    result = target(*call_args, **call_kwargs)
    if inspect.isawaitable(result):
        return asyncio.run(cast(Coroutine[Any, Any, Any], result))
    return result


# Decorator for easy job creation
def queue_job(
    priority: QueuePriority = QueuePriority.NORMAL,
    timeout: Optional[int] = None,
    ttl: Optional[int] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Awaitable[Any]]]:
    """Decorator to easily create queued jobs."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
        func_path = f"{func.__module__}.{func.__qualname__}"

        async def _invoke_original(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            execute_immediately = kwargs.pop("_execute_immediately", False)

            if execute_immediately:
                return await _invoke_original(*args, **kwargs)

            if not task_queue_manager._is_initialized:
                raise RuntimeError(
                    "Task queue manager is not initialized. Call initialize_task_queue() "
                    "before dispatching jobs or pass _execute_immediately=True."
                )

            job = task_queue_manager.enqueue_job(
                _execute_job_callable,
                func_path,
                args,
                kwargs,
                priority=priority,
                timeout=timeout,
                ttl=ttl,
            )

            return {"job_id": job.id, "queue": priority.value}

        # Add metadata for job creation
        wrapper._queue_job = True  # type: ignore[attr-defined]
        wrapper._priority = priority  # type: ignore[attr-defined]
        wrapper._timeout = timeout  # type: ignore[attr-defined]
        wrapper._ttl = ttl  # type: ignore[attr-defined]
        wrapper._job_path = func_path  # type: ignore[attr-defined]
        return wrapper

    return decorator


# Common agent tasks
@queue_job(priority=QueuePriority.HIGH)
async def send_notification_task(user_id: str, message: str, notification_type: str = "info") -> Dict[str, Any]:
    """Background task to send notifications."""
    try:
        logger.info(f"🔔 Sending {notification_type} notification to user {user_id}: {message}")

        # Simulate notification sending
        await cache_manager.set(
            "notifications",
            str(user_id),
            {
                "message": message,
                "type": notification_type,
                "timestamp": datetime.now().isoformat(),
            },
            ttl=300,  # 5 minutes
        )

        return {"status": "sent", "user_id": user_id, "type": notification_type}
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        raise


@queue_job(priority=QueuePriority.NORMAL)
async def process_ai_analysis_task(data: Dict[str, Any]) -> Dict[str, Any]:
    """Background task for AI analysis processing."""
    try:
        logger.info("🧠 Processing AI analysis in background")

        # Simulate AI analysis
        analysis_result = {
            "input_data": data,
            "analysis_type": "background_processing",
            "processed_at": datetime.now().isoformat(),
            "status": "completed",
        }

        # Cache the result
        await cache_manager.set(
            "ai_analysis",
            str(data.get("id", "unknown")),
            analysis_result,
            ttl=3600,  # 1 hour
        )

        return analysis_result
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        raise


@queue_job(priority=QueuePriority.LOW)
async def cleanup_task() -> Dict[str, Any]:
    """Background task for system cleanup."""
    try:
        logger.info("🧹 Performing system cleanup")

        # Clean up old cache entries
        await cache_manager.clear_namespace("expired_sessions")
        await cache_manager.clear_namespace("temp_data")

        # Clean up old failed jobs
        cleaned_jobs = task_queue_manager.cleanup_failed_jobs()

        return {
            "status": "completed",
            "cleaned_jobs": cleaned_jobs,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        raise


@queue_job(priority=QueuePriority.CRITICAL)
async def emergency_task(alert_data: Dict[str, Any]) -> Dict[str, Any]:
    """Emergency task for critical alerts."""
    try:
        logger.critical(f"🚨 EMERGENCY TASK: {alert_data}")

        # Store emergency alert
        await cache_manager.set(
            "emergency_alerts",
            str(alert_data.get("id", "latest")),
            {"alert": alert_data, "timestamp": datetime.now().isoformat(), "severity": "critical"},
            ttl=86400,  # 24 hours
        )

        return {"status": "emergency_processed", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.critical(f"Emergency task failed: {e}")
        raise


# Task queue initialization
def initialize_task_queue(redis_url: str = "redis://localhost:6379/0") -> bool:
    """Initialize the global task queue manager."""
    try:
        # Connect to Redis first
        if not cache_manager._is_connected:
            asyncio.run(cache_manager.connect())

        # Initialize task queue manager
        config = TaskConfig(redis_url=redis_url)
        manager = TaskQueueManager(config)
        manager.initialize()
        global task_queue_manager
        task_queue_manager = manager

        return True

    except Exception as e:
        logger.error(f"Task queue initialization failed: {e}")
        raise
