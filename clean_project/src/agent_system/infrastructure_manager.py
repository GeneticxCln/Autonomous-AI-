"""
Enterprise Infrastructure Manager
Integrates Redis caching, task queues, and monitoring for production deployment
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .cache_manager import cache_manager, CacheConfig
from .task_queue import task_queue_manager, TaskConfig, TaskQueueManager
from .config_simple import settings


logger = logging.getLogger(__name__)


class InfrastructureManager:
    """
    Enterprise infrastructure manager that coordinates:
    - Redis caching and session management
    - Background job processing with Redis Queue
    - Health monitoring and performance tracking
    - Integration with main agent system
    """

    def __init__(self):
        self.is_initialized = False
        self.startup_time = None
        self.health_status = {"cache": False, "queue": False, "overall": False}

    async def initialize(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
    ) -> bool:
        """
        Initialize all infrastructure components.

        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number
            redis_password: Redis password (optional)

        Returns:
            True if all components initialized successfully
        """
        try:
            logger.info("🚀 Initializing Enterprise Infrastructure...")

            # Initialize cache manager
            cache_config = CacheConfig(
                host=redis_host, port=redis_port, db=redis_db, password=redis_password
            )
            cache_manager.config = cache_config

            logger.info("🔗 Connecting to Redis cache...")
            cache_connected = await cache_manager.connect()
            if not cache_connected:
                logger.error("❌ Failed to connect to Redis cache")
                return False

            self.health_status["cache"] = True
            logger.info("✅ Cache manager initialized")

            # Initialize task queue manager
            redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"
            if redis_password:
                redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"

            task_config = TaskConfig(redis_url=redis_url)
            task_queue_manager.config = task_config

            logger.info("📋 Initializing task queue manager...")
            queue_initialized = task_queue_manager.initialize()
            if not queue_initialized:
                logger.error("❌ Failed to initialize task queue")
                return False

            self.health_status["queue"] = True
            logger.info("✅ Task queue manager initialized")

            # Set up infrastructure monitoring
            await self._setup_monitoring()

            self.is_initialized = True
            self.startup_time = datetime.now()

            # Mark overall health as good
            self.health_status["overall"] = True

            logger.info("🎉 Enterprise Infrastructure initialized successfully!")
            logger.info("📊 Infrastructure Summary:")
            logger.info(f"   🗄️  Cache: Connected to {redis_host}:{redis_port}")
            logger.info(f"   📋 Queue: {len(task_queue_manager.queues)} priority queues")
            logger.info(f"   ⏰ Startup: {self.startup_time.isoformat()}")

            return True

        except Exception as e:
            logger.error(f"❌ Infrastructure initialization failed: {e}")
            return False

    async def _setup_monitoring(self):
        """Set up infrastructure monitoring."""
        try:
            # Cache health monitoring
            await cache_manager.set(
                "infrastructure:health",
                {
                    "status": "healthy",
                    "cache": True,
                    "queue": True,
                    "timestamp": datetime.now().isoformat(),
                },
                ttl=300,  # 5 minutes
            )

            # Queue statistics monitoring
            await self._cache_queue_stats()

            logger.info("📈 Infrastructure monitoring configured")

        except Exception as e:
            logger.warning(f"⚠️ Infrastructure monitoring setup failed: {e}")

    async def _cache_queue_stats(self):
        """Cache queue statistics for monitoring."""
        try:
            if task_queue_manager._is_initialized:
                stats = task_queue_manager.get_overall_stats()

                await cache_manager.set(
                    "infrastructure:queue_stats",
                    {**stats, "timestamp": datetime.now().isoformat()},
                    ttl=300,  # 5 minutes
                )
        except Exception as e:
            logger.debug(f"Queue stats caching failed: {e}")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive infrastructure health status."""
        try:
            # Get cache health
            cache_healthy = await cache_manager.is_healthy()

            # Get queue health
            queue_healthy = task_queue_manager._is_initialized

            # Get overall status
            overall_healthy = cache_healthy and queue_healthy

            status = {
                "overall": overall_healthy,
                "cache": cache_healthy,
                "queue": queue_healthy,
                "uptime_seconds": (
                    (datetime.now() - self.startup_time).total_seconds() if self.startup_time else 0
                ),
                "cache_stats": (
                    await cache_manager.get_cache_info()
                    if cache_healthy
                    else {"status": "disconnected"}
                ),
                "queue_stats": (
                    task_queue_manager.get_overall_stats()
                    if queue_healthy
                    else {"status": "not_initialized"}
                ),
            }

            return status

        except Exception as e:
            logger.error(f"Health status check failed: {e}")
            return {"overall": False, "error": str(e), "cache": False, "queue": False}

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get infrastructure performance metrics."""
        try:
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "cache": await cache_manager.get_cache_info(),
                "queue": task_queue_manager.get_overall_stats(),
            }

            # Calculate derived metrics
            if "cache_stats" in metrics["cache"]:
                cache_stats = metrics["cache"]["cache_stats"]
                metrics["cache"]["hit_rate_percent"] = cache_stats.get("hit_rate", 0)

            return metrics

        except Exception as e:
            logger.error(f"Performance metrics collection failed: {e}")
            return {"error": str(e)}

    async def cache_api_response(
        self, endpoint: str, params: Dict[str, Any], response: Any, ttl: int = 300
    ) -> bool:
        """Cache API response for improved performance."""
        try:
            return await cache_manager.cache_api_response(endpoint, params, response, ttl)
        except Exception as e:
            logger.error(f"API response caching failed: {e}")
            return False

    async def get_cached_api_response(self, endpoint: str, params: Dict[str, Any]) -> Optional[Any]:
        """Get cached API response."""
        try:
            return await cache_manager.get_cached_api_response(endpoint, params)
        except Exception as e:
            logger.error(f"API response retrieval failed: {e}")
            return None

    async def enqueue_background_task(
        self, func, *args, priority: str = "normal", timeout: int = 1800, **kwargs
    ):
        """Enqueue a background task."""
        try:
            from .task_queue import QueuePriority

            # Convert string priority to enum
            priority_map = {
                "low": QueuePriority.LOW,
                "normal": QueuePriority.NORMAL,
                "high": QueuePriority.HIGH,
                "critical": QueuePriority.CRITICAL,
            }

            queue_priority = priority_map.get(priority.lower(), QueuePriority.NORMAL)

            return task_queue_manager.enqueue_job(
                func, *args, priority=queue_priority, timeout=timeout, **kwargs
            )

        except Exception as e:
            logger.error(f"Background task enqueue failed: {e}")
            return None

    async def schedule_recurring_task(
        self, func, interval_seconds: int, *args, priority: str = "normal", **kwargs
    ):
        """Schedule a recurring background task."""
        try:
            from .task_queue import QueuePriority

            priority_map = {
                "low": QueuePriority.LOW,
                "normal": QueuePriority.NORMAL,
                "high": QueuePriority.HIGH,
                "critical": QueuePriority.CRITICAL,
            }

            queue_priority = priority_map.get(priority.lower(), QueuePriority.NORMAL)

            return task_queue_manager.schedule_job_interval(
                func, interval_seconds, *args, priority=queue_priority, **kwargs
            )

        except Exception as e:
            logger.error(f"Recurring task scheduling failed: {e}")
            return None

    async def invalidate_cache_pattern(self, namespace: str, pattern: str) -> int:
        """Invalidate cache entries matching a pattern."""
        try:
            return await cache_manager.delete_pattern(namespace, pattern)
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            return 0

    async def clear_cache_namespace(self, namespace: str) -> int:
        """Clear all cache entries in a namespace."""
        try:
            return await cache_manager.clear_namespace(namespace)
        except Exception as e:
            logger.error(f"Cache namespace clearing failed: {e}")
            return 0

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get detailed cache statistics."""
        try:
            return await cache_manager.get_cache_info()
        except Exception as e:
            logger.error(f"Cache stats retrieval failed: {e}")
            return {"error": str(e)}

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get detailed queue statistics."""
        try:
            return task_queue_manager.get_overall_stats()
        except Exception as e:
            logger.error(f"Queue stats retrieval failed: {e}")
            return {"error": str(e)}

    async def cleanup_infrastructure(self) -> Dict[str, int]:
        """Clean up infrastructure resources."""
        try:
            cleanup_results = {}

            # Clean up old failed jobs
            if task_queue_manager._is_initialized:
                cleaned_jobs = task_queue_manager.cleanup_failed_jobs()
                cleanup_results["failed_jobs_cleaned"] = cleaned_jobs

            # Clear old cache entries
            cleared_cache = await cache_manager.clear_namespace("temp_data")
            cleanup_results["cache_entries_cleared"] = cleared_cache

            logger.info(f"🧹 Infrastructure cleanup completed: {cleanup_results}")
            return cleanup_results

        except Exception as e:
            logger.error(f"Infrastructure cleanup failed: {e}")
            return {"error": str(e)}

    async def shutdown(self):
        """Gracefully shutdown infrastructure components."""
        try:
            logger.info("🔄 Shutting down infrastructure components...")

            # Shutdown task queue manager
            if task_queue_manager._is_initialized:
                task_queue_manager.stop_scheduler()
                logger.info("📋 Task queue manager stopped")

            # Disconnect cache manager
            await cache_manager.disconnect()
            logger.info("🗄️ Cache manager disconnected")

            self.is_initialized = False
            self.health_status = {"cache": False, "queue": False, "overall": False}

            logger.info("✅ Infrastructure shutdown completed")

        except Exception as e:
            logger.error(f"❌ Infrastructure shutdown error: {e}")


# Global infrastructure manager instance
infrastructure_manager = InfrastructureManager()


# Convenience functions
async def initialize_infrastructure(
    redis_host: str = "localhost",
    redis_port: int = 6379,
    redis_db: int = 0,
    redis_password: Optional[str] = None,
) -> bool:
    """Initialize the global infrastructure manager."""
    return await infrastructure_manager.initialize(redis_host, redis_port, redis_db, redis_password)


async def get_infrastructure_health() -> Dict[str, Any]:
    """Get infrastructure health status."""
    return await infrastructure_manager.get_health_status()


async def cache_response(
    endpoint: str, params: Dict[str, Any], response: Any, ttl: int = 300
) -> bool:
    """Cache API response."""
    return await infrastructure_manager.cache_api_response(endpoint, params, response, ttl)


async def get_cached_response(endpoint: str, params: Dict[str, Any]) -> Optional[Any]:
    """Get cached API response."""
    return await infrastructure_manager.get_cached_api_response(endpoint, params)


async def enqueue_task(func, *args, **kwargs):
    """Enqueue background task."""
    return await infrastructure_manager.enqueue_background_task(func, *args, **kwargs)


async def schedule_task(func, interval_seconds: int, *args, **kwargs):
    """Schedule recurring task."""
    return await infrastructure_manager.schedule_recurring_task(
        func, interval_seconds, *args, **kwargs
    )


async def get_performance_stats() -> Dict[str, Any]:
    """Get performance statistics."""
    return await infrastructure_manager.get_performance_metrics()


# Integration with main agent
async def agent_startup_integration():
    """Integration hook for agent startup."""
    try:
        # Use Redis config from settings if available
        redis_host = getattr(settings, "REDIS_HOST", "localhost")
        redis_port = getattr(settings, "REDIS_PORT", 6379)
        redis_db = getattr(settings, "REDIS_DB", 0)
        redis_password = getattr(settings, "REDIS_PASSWORD", None)

        await initialize_infrastructure(
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
            redis_password=redis_password,
        )

        return True

    except Exception as e:
        logger.error(f"Agent infrastructure integration failed: {e}")
        return False


async def agent_shutdown_integration():
    """Integration hook for agent shutdown."""
    try:
        await infrastructure_manager.shutdown()
        return True

    except Exception as e:
        logger.error(f"Agent infrastructure shutdown failed: {e}")
        return False


# Health check endpoints
async def health_check() -> Dict[str, Any]:
    """Comprehensive health check for all infrastructure components."""
    try:
        health = await get_infrastructure_health()

        # Add overall system health
        health["system"] = {
            "status": "healthy" if health["overall"] else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "cache": "healthy" if health["cache"] else "unhealthy",
                "queue": "healthy" if health["queue"] else "unhealthy",
            },
        }

        return health

    except Exception as e:
        return {"overall": False, "system": {"status": "error", "error": str(e)}}


# Performance monitoring
async def performance_monitor():
    """Background performance monitoring task."""
    try:
        metrics = await get_performance_stats()

        # Cache performance metrics
        await infrastructure_manager.cache_manager.set(
            "infrastructure:performance",
            {**metrics, "timestamp": datetime.now().isoformat()},
            ttl=600,  # 10 minutes
        )

        return metrics

    except Exception as e:
        logger.error(f"Performance monitoring failed: {e}")
        return {"error": str(e)}


# Cleanup scheduler
async def infrastructure_cleanup_scheduler():
    """Scheduled infrastructure cleanup task."""
    try:
        cleanup_results = await infrastructure_manager.cleanup_infrastructure()

        # Cache cleanup results
        await infrastructure_manager.cache_manager.set(
            "infrastructure:last_cleanup",
            {**cleanup_results, "timestamp": datetime.now().isoformat()},
            ttl=3600,  # 1 hour
        )

        return cleanup_results

    except Exception as e:
        logger.error(f"Scheduled infrastructure cleanup failed: {e}")
        return {"error": str(e)}
