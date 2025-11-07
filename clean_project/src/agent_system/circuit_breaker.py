"""
Circuit Breaker Pattern for Enterprise Resilience
Provides fault tolerance and resilience for external service calls
"""

from __future__ import annotations

import asyncio
import time
import logging
from enum import Enum
from typing import Any, Callable, Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import functools
import aiohttp
import requests

from .config_simple import settings


logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5  # Number of failures to open circuit
    recovery_timeout: float = 60.0  # Seconds to wait before trying half-open
    success_threshold: int = 3  # Successes needed to close circuit from half-open
    timeout: float = 30.0  # Request timeout in seconds
    expected_exception: type = Exception  # Exception that should trigger circuit breaker
    monitor_callback: Optional[Callable] = None  # Callback for state changes


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0
    state_changes: List[Dict[str, Any]] = field(default_factory=list)
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_state_change: Optional[datetime] = None

    def add_request(self, success: bool, rejected: bool = False):
        """Add request statistics."""
        self.total_requests += 1
        if rejected:
            self.rejected_requests += 1
        elif success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            self.last_failure_time = datetime.now()

        if success and not rejected:
            self.last_success_time = datetime.now()

    def add_state_change(self, old_state: CircuitState, new_state: CircuitState, reason: str = ""):
        """Add state change event."""
        self.state_changes.append(
            {
                "timestamp": datetime.now().isoformat(),
                "old_state": old_state.value,
                "new_state": new_state.value,
                "reason": reason,
            }
        )
        self.last_state_change = datetime.now()

    def get_success_rate(self) -> float:
        """Get success rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    def get_rejection_rate(self) -> float:
        """Get rejection rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.rejected_requests / self.total_requests) * 100


class CircuitBreaker:
    """
    Enterprise circuit breaker implementation with:
    - Multiple states (Closed, Open, Half-Open)
    - Configurable failure thresholds
    - Recovery mechanisms
    - Statistics tracking
    - Event callbacks
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._lock = asyncio.Lock() if asyncio.iscoroutinefunction(self.call) else None

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self._last_failure_time is None:
            return True

        time_since_failure = time.time() - self._last_failure_time
        return time_since_failure >= self.config.recovery_timeout

    def _can_attempt_request(self) -> bool:
        """Check if a request can be attempted based on current state."""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            return self._should_attempt_reset()
        else:  # HALF_OPEN
            return True

    def _record_success(self):
        """Record a successful operation."""
        self._failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._change_state(CircuitState.CLOSED, "Recovery successful")

    def _record_failure(self):
        """Record a failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if (
            self.state == CircuitState.CLOSED
            and self._failure_count >= self.config.failure_threshold
        ):
            self._change_state(
                CircuitState.OPEN, f"Failure threshold exceeded ({self._failure_count})"
            )

        elif self.state == CircuitState.HALF_OPEN:
            self._change_state(CircuitState.OPEN, "Failed during recovery attempt")

    def _change_state(self, new_state: CircuitState, reason: str = ""):
        """Change circuit breaker state."""
        old_state = self.state
        self.state = new_state

        # Reset counters based on new state
        if new_state == CircuitState.OPEN:
            self._success_count = 0
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0

        # Record state change
        self.stats.add_state_change(old_state, new_state, reason)

        # Call monitoring callback
        if self.config.monitor_callback:
            try:
                self.config.monitor_callback(self.name, old_state, new_state, reason)
            except Exception as e:
                logger.error(f"Circuit breaker callback error: {e}")

        # Log state change
        logger.info(
            f"Circuit breaker '{self.name}': {old_state.value} → {new_state.value} ({reason})"
        )

    async def call_async(self, func: Callable, *args, fallback_result: Any = None, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection (async version).

        Args:
            func: Async function to execute
            args: Function arguments
            fallback_result: Result to return when circuit is open
            kwargs: Function keyword arguments

        Returns:
            Function result or fallback result
        """
        async with self._lock:
            # Check if request can be attempted
            if not self._can_attempt_request():
                self.stats.add_request(success=False, rejected=True)
                logger.warning(f"Circuit breaker '{self.name}' is OPEN, request rejected")
                return fallback_result

            # Attempt the request
            self.stats.add_request(success=False, rejected=False)

            try:
                # Check if function is async
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **kwargs), timeout=self.config.timeout
                    )
                else:
                    # Run sync function in thread pool
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                        timeout=self.config.timeout,
                    )

                # Record success
                self._record_success()
                self.stats.add_request(success=True, rejected=False)
                return result

            except self.config.expected_exception as e:
                logger.error(f"Circuit breaker '{self.name}' caught expected exception: {e}")
                self._record_failure()
                self.stats.add_request(success=False, rejected=False)
                return fallback_result

            except asyncio.TimeoutError:
                logger.error(f"Circuit breaker '{self.name}' timeout after {self.config.timeout}s")
                self._record_failure()
                self.stats.add_request(success=False, rejected=False)
                return fallback_result

            except Exception as e:
                logger.error(f"Circuit breaker '{self.name}' caught unexpected exception: {e}")
                self._record_failure()
                self.stats.add_request(success=False, rejected=False)
                return fallback_result

    def call_sync(self, func: Callable, *args, fallback_result: Any = None, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection (sync version).

        Args:
            func: Sync function to execute
            args: Function arguments
            fallback_result: Result to return when circuit is open
            kwargs: Function keyword arguments

        Returns:
            Function result or fallback result
        """
        # Check if request can be attempted
        if not self._can_attempt_request():
            self.stats.add_request(success=False, rejected=True)
            logger.warning(f"Circuit breaker '{self.name}' is OPEN, request rejected")
            return fallback_result

        # Attempt the request
        self.stats.add_request(success=False, rejected=False)

        try:
            result = func(*args, **kwargs)

            # Record success
            self._record_success()
            self.stats.add_request(success=True, rejected=False)
            return result

        except self.config.expected_exception as e:
            logger.error(f"Circuit breaker '{self.name}' caught expected exception: {e}")
            self._record_failure()
            self.stats.add_request(success=False, rejected=False)
            return fallback_result

        except Exception as e:
            logger.error(f"Circuit breaker '{self.name}' caught unexpected exception: {e}")
            self._record_failure()
            self.stats.add_request(success=False, rejected=False)
            return fallback_result

    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
            "stats": {
                "total_requests": self.stats.total_requests,
                "successful_requests": self.stats.successful_requests,
                "failed_requests": self.stats.failed_requests,
                "rejected_requests": self.stats.rejected_requests,
                "success_rate": self.stats.get_success_rate(),
                "rejection_rate": self.stats.get_rejection_rate(),
                "last_state_change": (
                    self.stats.last_state_change.isoformat()
                    if self.stats.last_state_change
                    else None
                ),
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
            },
        }

    def reset(self):
        """Manually reset circuit breaker to closed state."""
        self._change_state(CircuitState.CLOSED, "Manual reset")
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        logger.info(f"Circuit breaker '{self.name}' manually reset")


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._global_config = CircuitBreakerConfig()

    def register(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Register a new circuit breaker."""
        breaker_config = config or self._global_config
        self._breakers[name] = CircuitBreaker(name, breaker_config)
        logger.info(f"Circuit breaker '{name}' registered")
        return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._breakers.get(name)

    def remove(self, name: str):
        """Remove circuit breaker."""
        if name in self._breakers:
            del self._breakers[name]
            logger.info(f"Circuit breaker '{name}' removed")

    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all circuit breakers."""
        return {name: breaker.get_status() for name, breaker in self._breakers.items()}

    def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()

    def set_global_config(self, config: CircuitBreakerConfig):
        """Set global default configuration."""
        self._global_config = config


# Global circuit breaker registry
circuit_registry = CircuitBreakerRegistry()


# Decorator for automatic circuit breaker protection
def circuit_breaker(
    name: str, config: Optional[CircuitBreakerConfig] = None, fallback_result: Any = None
):
    """
    Decorator to add circuit breaker protection to functions.

    Args:
        name: Name of the circuit breaker
        config: Circuit breaker configuration
        fallback_result: Default result when circuit is open
    """

    def decorator(func):
        # Register circuit breaker
        breaker = circuit_registry.register(name, config)

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await breaker.call_async(
                    func, *args, fallback_result=fallback_result, **kwargs
                )

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return breaker.call_sync(func, *args, fallback_result=fallback_result, **kwargs)

            return sync_wrapper

    return decorator


# Specialized circuit breakers for common use cases
class APIRequestCircuitBreaker:
    """Circuit breaker specifically for HTTP API requests."""

    @staticmethod
    def create_breaker(
        name: str, expected_status_codes: Optional[List[int]] = None
    ) -> CircuitBreaker:
        """Create circuit breaker for API requests."""
        if expected_status_codes is None:
            expected_status_codes = [500, 502, 503, 504, 429]

        def api_exception_handler(response):
            """Handle HTTP response errors."""
            if response.status in expected_status_codes:
                return True
            if response.status >= 500:
                return True
            return False

        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2,
            timeout=10.0,
            expected_exception=api_exception_handler,
        )

        return circuit_registry.register(name, config)

    @staticmethod
    @circuit_breaker("http_requests")
    async def make_request(url: str, method: str = "GET", **kwargs) -> requests.Response:
        """Make HTTP request with circuit breaker protection."""
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, **kwargs) as response:
                return response

    @staticmethod
    @circuit_breaker("requests_lib")
    def make_sync_request(url: str, method: str = "GET", **kwargs) -> requests.Response:
        """Make synchronous HTTP request with circuit breaker protection."""
        return requests.request(method, url, **kwargs)


class DatabaseCircuitBreaker:
    """Circuit breaker for database operations."""

    @staticmethod
    def create_breaker(name: str) -> CircuitBreaker:
        """Create circuit breaker for database operations."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=3,
            timeout=15.0,
            expected_exception=Exception,  # Catch all database exceptions
        )

        return circuit_registry.register(name, config)

    @staticmethod
    @circuit_breaker("database_operations", fallback_result=None)
    def execute_query(query_func: Callable, *args, **kwargs):
        """Execute database query with circuit breaker protection."""
        return query_func(*args, **kwargs)


# Initialize default circuit breakers
def initialize_circuit_breakers():
    """Initialize default circuit breakers for common services."""
    # API circuit breakers
    circuit_registry.register(
        "openai_api",
        CircuitBreakerConfig(
            failure_threshold=3, recovery_timeout=60.0, success_threshold=2, timeout=30.0
        ),
    )

    circuit_registry.register(
        "anthropic_api",
        CircuitBreakerConfig(
            failure_threshold=3, recovery_timeout=60.0, success_threshold=2, timeout=30.0
        ),
    )

    circuit_registry.register(
        "redis_operations",
        CircuitBreakerConfig(
            failure_threshold=5, recovery_timeout=30.0, success_threshold=3, timeout=10.0
        ),
    )

    # Database circuit breakers
    circuit_registry.register(
        "database_queries",
        CircuitBreakerConfig(
            failure_threshold=5, recovery_timeout=60.0, success_threshold=3, timeout=15.0
        ),
    )

    logger.info("✅ Default circuit breakers initialized")


# Health check for circuit breakers
def circuit_breaker_health_check() -> Dict[str, Any]:
    """Get health check for all circuit breakers."""
    all_status = circuit_registry.get_all_status()

    total_breakers = len(all_status)
    open_breakers = sum(1 for status in all_status.values() if status["state"] == "open")
    healthy_breakers = total_breakers - open_breakers

    return {
        "overall_health": open_breakers == 0,
        "total_breakers": total_breakers,
        "healthy_breakers": healthy_breakers,
        "open_breakers": open_breakers,
        "breakers": all_status,
    }
