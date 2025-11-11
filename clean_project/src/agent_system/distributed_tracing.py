"""
Distributed Tracing with OpenTelemetry and Jaeger
Enterprise-grade distributed tracing for microservices observability
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from contextlib import asynccontextmanager, contextmanager, nullcontext
from datetime import datetime, timezone
from typing import Any, Callable, ContextManager, Dict, Iterator, Optional, cast

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.metrics import get_meter_provider, set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider, sampling
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

from .config_simple import settings

logger = logging.getLogger(__name__)


class DistributedTracingManager:
    """
    Enterprise distributed tracing manager with:
    - OpenTelemetry integration
    - Jaeger backend support
    - Custom span creation
    - Performance monitoring
    - Error tracking
    """

    def __init__(self) -> None:
        self.tracer: Optional[Any] = None
        self.meter: Optional[Any] = None
        self.is_initialized = False
        self.service_name = "autonomous-agent-system"
        self.service_version = "1.0.0"
        self.environment = getattr(settings, "ENVIRONMENT", "development")

    def initialize(
        self,
        jaeger_host: str = "localhost",
        jaeger_port: int = 14268,
        service_name: Optional[str] = None,
    ) -> bool:
        """
        Initialize distributed tracing with Jaeger backend.

        Args:
            jaeger_host: Jaeger collector host
            jaeger_port: Jaeger collector port
            service_name: Service name for tracing

        Returns:
            True if initialization successful
        """
        try:
            # Set service name
            if service_name:
                self.service_name = service_name

            # Create resource with service information
            resource = Resource.create(
                {
                    ResourceAttributes.SERVICE_NAME: self.service_name,
                    ResourceAttributes.SERVICE_VERSION: self.service_version,
                    ResourceAttributes.DEPLOYMENT_ENVIRONMENT: self.environment,
                }
            )

            # Create trace provider
            trace_provider = TracerProvider(
                resource=resource,
                sampler=sampling.ALWAYS_ON,  # Sample all traces for development
            )

            # Configure Jaeger exporter
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_host,
                agent_port=jaeger_port,
                collector_endpoint=f"http://{jaeger_host}:{jaeger_port}/api/traces",
            )

            # Add span processor
            span_processor = BatchSpanProcessor(jaeger_exporter)
            trace_provider.add_span_processor(span_processor)

            # Set global trace provider
            trace.set_tracer_provider(trace_provider)

            # Get tracer
            self.tracer = trace.get_tracer(__name__)

            # Initialize meter provider for metrics
            metric_reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
            meter_provider = MeterProvider(metric_readers=[metric_reader])
            set_meter_provider(meter_provider)
            self.meter = get_meter_provider().get_meter(__name__)

            self.is_initialized = True

            logger.info(f"✅ Distributed tracing initialized: {self.service_name}")
            logger.info(f"📊 Jaeger endpoint: http://{jaeger_host}:{jaeger_port}")

            return True

        except Exception as e:
            logger.error(f"❌ Distributed tracing initialization failed: {e}")
            return False

    def create_span(
        self,
        operation_name: str,
        attributes: Optional[Dict[str, Any]] = None,
        kind: str = "internal",
    ) -> ContextManager[Any]:
        """
        Create a custom span for tracing operations.

        Args:
            operation_name: Name of the operation
            attributes: Additional span attributes
            kind: Span kind (internal, server, client, producer, consumer)
        """
        if not self.is_initialized:
            return nullcontext()

        # Map string kind to span kind
        kind_map = {
            "internal": trace.SpanKind.INTERNAL,
            "server": trace.SpanKind.SERVER,
            "client": trace.SpanKind.CLIENT,
            "producer": trace.SpanKind.PRODUCER,
            "consumer": trace.SpanKind.CONSUMER,
        }

        span_kind = kind_map.get(kind, trace.SpanKind.INTERNAL)

        # Create span via a context manager that yields the span and applies attributes
        tracer = self.tracer
        if tracer is None:
            return nullcontext()

        @contextmanager
        def _span_cm() -> Iterator[Any]:
            tracer_any = cast(Any, tracer)
            with tracer_any.start_as_current_span(operation_name, kind=span_kind) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))
                yield span

        return _span_cm()

    def trace_function(self, operation_name: str, attributes: Optional[Dict[str, Any]] = None) -> Callable[..., Any]:
        """
        Decorator to automatically trace function execution.

        Args:
            operation_name: Name of the operation
            attributes: Additional span attributes
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.create_span(operation_name, attributes) as span:
                    # Add function info
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)

                    # Add arguments (be careful with sensitive data)
                    if hasattr(func, "__annotations__"):
                        span.set_attribute("function.signature", str(func.__annotations__))

                    try:
                        result = await func(*args, **kwargs)
                        span.set_attribute("result.type", type(result).__name__)
                        span.set_attribute("status", "success")
                        return result
                    except Exception as e:
                        span.set_attribute("error", str(e))
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("status", "error")
                        raise

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.create_span(operation_name, attributes) as span:
                    # Add function info
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)

                    try:
                        result = func(*args, **kwargs)
                        span.set_attribute("result.type", type(result).__name__)
                        span.set_attribute("status", "success")
                        return result
                    except Exception as e:
                        span.set_attribute("error", str(e))
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("status", "error")
                        raise

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

        return decorator

    def trace_async_context(self, operation_name: str, attributes: Optional[Dict[str, Any]] = None) -> Any:
        """
        Create an async context manager for tracing.

        Args:
            operation_name: Name of the operation
            attributes: Additional span attributes
        """

        @asynccontextmanager
        async def tracing_context() -> Any:
            with self.create_span(operation_name, attributes) as span:
                start_time = time.time()
                try:
                    yield span
                finally:
                    duration = time.time() - start_time
                    span.set_attribute("duration.seconds", duration)

        return tracing_context()

    def add_span_attribute(self, key: str, value: Any) -> None:
        """Add attribute to current span."""
        if not self.is_initialized:
            return

        current_span = trace.get_current_span()
        if current_span:
            current_span.set_attribute(key, str(value))

    def add_span_event(self, event_name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add event to current span."""
        if not self.is_initialized:
            return

        current_span = trace.get_current_span()
        if current_span:
            current_span.add_event(event_name, attributes or {})

    def trace_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """Trace an error with full context."""
        if not self.is_initialized:
            return

        current_span = trace.get_current_span()
        if current_span:
            current_span.set_attribute("error", str(error))
            current_span.set_attribute("error.type", type(error).__name__)
            current_span.set_attribute("error.message", str(error))

            if context:
                for key, value in context.items():
                    current_span.set_attribute(f"error.context.{key}", str(value))

    def create_custom_metrics(self) -> Dict[str, Any]:
        """Create custom business metrics."""
        if not self.is_initialized or not self.meter:
            return {}

        metrics = {}

        try:
            # Request counter
            metrics["request_count"] = self.meter.create_counter(
                name="agent_requests_total",
                description="Total number of agent requests",
                unit="requests",
            )

            # Request duration
            metrics["request_duration"] = self.meter.create_histogram(
                name="agent_request_duration_seconds",
                description="Request duration in seconds",
                unit="seconds",
            )

            # Active sessions gauge
            metrics["active_sessions"] = self.meter.create_up_down_counter(
                name="agent_active_sessions",
                description="Number of active user sessions",
                unit="sessions",
            )

            # Cache hit rate
            metrics["cache_hits"] = self.meter.create_counter(
                name="agent_cache_hits_total", description="Total number of cache hits", unit="hits"
            )

            # Queue size gauge
            metrics["queue_size"] = self.meter.create_up_down_counter(
                name="agent_queue_size", description="Current queue size by priority", unit="jobs"
            )

            logger.info("✅ Custom metrics created")
            return metrics

        except Exception as e:
            logger.error(f"❌ Custom metrics creation failed: {e}")
            return {}

    def record_metric(
        self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a custom metric value."""
        if not self.is_initialized:
            return

        # This would be implemented based on the metrics created
        # For now, just log the metric
        labels_str = f" (labels: {labels})" if labels else ""
        logger.debug(f"📊 Metric: {metric_name} = {value}{labels_str}")

    def instrument_fastapi(self, app: Any) -> None:
        """Instrument FastAPI application for tracing."""
        if not self.is_initialized:
            return

        try:
            FastAPIInstrumentor.instrument_app(
                app,
                tracer_provider=trace.get_tracer_provider(),
                excluded_urls="/health|/metrics|/favicon.ico",
            )
            logger.info("✅ FastAPI instrumented for tracing")
        except Exception as e:
            logger.error(f"❌ FastAPI instrumentation failed: {e}")

    def instrument_redis(self) -> None:
        """Instrument Redis for tracing."""
        if not self.is_initialized:
            return

        try:
            RedisInstrumentor().instrument()
            logger.info("✅ Redis instrumented for tracing")
        except Exception as e:
            logger.error(f"❌ Redis instrumentation failed: {e}")

    def instrument_requests(self) -> None:
        """Instrument HTTP requests for tracing."""
        if not self.is_initialized:
            return

        try:
            RequestsInstrumentor().instrument()
            logger.info("✅ HTTP requests instrumented for tracing")
        except Exception as e:
            logger.error(f"❌ HTTP requests instrumentation failed: {e}")

    def instrument_sqlalchemy(self, engine: Any) -> None:
        """Instrument SQLAlchemy for tracing."""
        if not self.is_initialized:
            return

        try:
            SQLAlchemyInstrumentor().instrument(
                engine=engine, tracer_provider=trace.get_tracer_provider()
            )
            logger.info("✅ SQLAlchemy instrumented for tracing")
        except Exception as e:
            logger.error(f"❌ SQLAlchemy instrumentation failed: {e}")

    def get_tracing_info(self) -> Dict[str, Any]:
        """Get current tracing information."""
        return {
            "service_name": self.service_name,
            "service_version": self.service_version,
            "environment": self.environment,
            "is_initialized": self.is_initialized,
            "jaeger_endpoint": "http://localhost:14268" if self.is_initialized else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Global tracing manager instance
tracing_manager = DistributedTracingManager()


# Utility functions
def initialize_tracing(
    jaeger_host: str = "localhost",
    jaeger_port: int = 14268,
    service_name: str = "autonomous-agent-system",
) -> bool:
    """Initialize the global tracing manager."""
    return tracing_manager.initialize(jaeger_host, jaeger_port, service_name)


def get_tracer(operation_name: str) -> Any:
    """Get a tracer for creating spans."""
    if not tracing_manager.is_initialized:
        return None

    return tracing_manager.create_span(operation_name)


def trace_function(operation_name: str, attributes: Optional[Dict[str, Any]] = None) -> Callable[..., Any]:
    """Decorator for automatic function tracing."""
    return tracing_manager.trace_function(operation_name, attributes)


def trace_async(operation_name: str, attributes: Optional[Dict[str, Any]] = None) -> Any:
    """Create async context manager for tracing."""
    return tracing_manager.trace_async_context(operation_name, attributes)


# (asyncio is imported at module top)
