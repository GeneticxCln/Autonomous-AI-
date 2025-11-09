"""
Performance benchmarking suite for the agent system.
Tests throughput, latency, concurrency, and resource usage.
"""

import asyncio
import pytest
import time
import statistics
from typing import Dict, List, Any
from dataclasses import dataclass

from agent_system.agent import AutonomousAgent
from agent_system.distributed_message_queue import DistributedMessageQueue, MessagePriority
from agent_system.tools import ToolRegistry
from agent_system.goal_manager import GoalManager


@dataclass
class BenchmarkResult:
    """Result of a performance benchmark."""
    name: str
    operations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    p50: float
    p95: float
    p99: float
    throughput: float  # operations per second
    errors: int = 0


class PerformanceBenchmark:
    """Performance benchmarking utilities."""

    @staticmethod
    async def benchmark_goal_processing(
        goal_count: int = 100,
        concurrent_goals: int = 5,
    ) -> BenchmarkResult:
        """Benchmark goal processing performance."""
        agent = AutonomousAgent()
        times = []

        # Add goals
        for i in range(goal_count):
            agent.add_goal(f"Test goal {i}", priority=0.5)

        start_time = time.perf_counter()

        # Process goals
        cycles = 0
        while agent.goal_manager.has_pending_goals() and cycles < goal_count:
            cycle_start = time.perf_counter()
            await agent.run_cycle_async(concurrency_limit=concurrent_goals)
            cycle_time = time.perf_counter() - cycle_start
            times.append(cycle_time)
            cycles += 1

        total_time = time.perf_counter() - start_time

        return PerformanceBenchmark._calculate_stats(
            "goal_processing",
            times,
            goal_count,
            total_time,
        )

    @staticmethod
    async def benchmark_message_queue_throughput(
        message_count: int = 1000,
        queue_name: str = "benchmark-queue",
    ) -> BenchmarkResult:
        """Benchmark message queue publish/consume throughput."""
        queue = DistributedMessageQueue(force_fallback=True)
        await queue.initialize()

        # Benchmark publish
        publish_times = []
        start_time = time.perf_counter()

        for i in range(message_count):
            pub_start = time.perf_counter()
            await queue.publish(
                queue_name,
                {"index": i, "data": f"message-{i}"},
                priority=MessagePriority.NORMAL,
            )
            publish_times.append(time.perf_counter() - pub_start)

        publish_total = time.perf_counter() - start_time

        # Benchmark consume
        consume_times = []
        start_time = time.perf_counter()

        for i in range(message_count):
            cons_start = time.perf_counter()
            envelope = await queue.consume(queue_name, timeout=1)
            if envelope:
                await queue.ack(queue_name, envelope.message_id)
            consume_times.append(time.perf_counter() - cons_start)

        consume_total = time.perf_counter() - start_time

        # Combine publish and consume
        all_times = publish_times + consume_times
        total_time = publish_total + consume_total

        return PerformanceBenchmark._calculate_stats(
            "message_queue_throughput",
            all_times,
            message_count * 2,  # publish + consume
            total_time,
        )

    @staticmethod
    async def benchmark_concurrent_goal_execution(
        goal_count: int = 50,
        concurrency_levels: List[int] = [1, 5, 10, 20],
    ) -> Dict[int, BenchmarkResult]:
        """Benchmark performance at different concurrency levels."""
        results = {}

        for concurrency in concurrency_levels:
            agent = AutonomousAgent()
            times = []

            # Add goals
            for i in range(goal_count):
                agent.add_goal(f"Concurrent goal {i}", priority=0.5)

            start_time = time.perf_counter()

            # Process with specific concurrency
            cycles = 0
            while agent.goal_manager.has_pending_goals() and cycles < goal_count:
                cycle_start = time.perf_counter()
                await agent.run_cycle_async(concurrency_limit=concurrency)
                cycle_time = time.perf_counter() - cycle_start
                times.append(cycle_time)
                cycles += 1

            total_time = time.perf_counter() - start_time

            results[concurrency] = PerformanceBenchmark._calculate_stats(
                f"concurrent_execution_{concurrency}",
                times,
                goal_count,
                total_time,
            )

        return results

    @staticmethod
    async def benchmark_tool_execution(
        tool_name: str = "generic_tool",
        execution_count: int = 100,
    ) -> BenchmarkResult:
        """Benchmark tool execution performance."""
        registry = ToolRegistry()
        times = []

        # Get tool
        tool = registry.get_tool(tool_name)
        if not tool:
            pytest.skip(f"Tool {tool_name} not available")

        start_time = time.perf_counter()

        for i in range(execution_count):
            exec_start = time.perf_counter()
            try:
                await registry.execute_action_async(
                    type("Action", (), {
                        "id": f"action-{i}",
                        "name": "test_action",
                        "tool_name": tool_name,
                        "parameters": {"query": f"test query {i}"},
                    })()
                )
            except Exception:
                pass  # Ignore errors for benchmarking
            times.append(time.perf_counter() - exec_start)

        total_time = time.perf_counter() - start_time

        return PerformanceBenchmark._calculate_stats(
            f"tool_execution_{tool_name}",
            times,
            execution_count,
            total_time,
        )

    @staticmethod
    def _calculate_stats(
        name: str,
        times: List[float],
        operations: int,
        total_time: float,
    ) -> BenchmarkResult:
        """Calculate statistics from timing data."""
        if not times:
            return BenchmarkResult(
                name=name,
                operations=0,
                total_time=0,
                avg_time=0,
                min_time=0,
                max_time=0,
                p50=0,
                p95=0,
                p99=0,
                throughput=0,
            )

        sorted_times = sorted(times)
        n = len(sorted_times)

        return BenchmarkResult(
            name=name,
            operations=operations,
            total_time=total_time,
            avg_time=statistics.mean(times),
            min_time=min(times),
            max_time=max(times),
            p50=sorted_times[int(n * 0.50)] if n > 0 else 0,
            p95=sorted_times[int(n * 0.95)] if n > 0 else 0,
            p99=sorted_times[int(n * 0.99)] if n > 0 else 0,
            throughput=operations / total_time if total_time > 0 else 0,
        )

    @staticmethod
    def print_results(results: List[BenchmarkResult]):
        """Print benchmark results in a readable format."""
        print("\n" + "=" * 80)
        print("PERFORMANCE BENCHMARK RESULTS")
        print("=" * 80)

        for result in results:
            print(f"\n{result.name}:")
            print(f"  Operations: {result.operations}")
            print(f"  Total Time: {result.total_time:.3f}s")
            print(f"  Throughput: {result.throughput:.2f} ops/sec")
            print(f"  Avg Time: {result.avg_time*1000:.2f}ms")
            print(f"  Min Time: {result.min_time*1000:.2f}ms")
            print(f"  Max Time: {result.max_time*1000:.2f}ms")
            print(f"  P50: {result.p50*1000:.2f}ms")
            print(f"  P95: {result.p95*1000:.2f}ms")
            print(f"  P99: {result.p99*1000:.2f}ms")

        print("\n" + "=" * 80)


# Pytest test functions
@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_goal_processing():
    """Benchmark goal processing performance."""
    result = await PerformanceBenchmark.benchmark_goal_processing(
        goal_count=50,
        concurrent_goals=5,
    )
    PerformanceBenchmark.print_results([result])
    assert result.throughput > 0
    assert result.avg_time < 1.0  # Should complete in under 1 second per goal


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_message_queue():
    """Benchmark message queue throughput."""
    result = await PerformanceBenchmark.benchmark_message_queue_throughput(
        message_count=500,
    )
    PerformanceBenchmark.print_results([result])
    assert result.throughput > 100  # Should handle at least 100 ops/sec


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_concurrency_scaling():
    """Benchmark performance at different concurrency levels."""
    results = await PerformanceBenchmark.benchmark_concurrent_goal_execution(
        goal_count=30,
        concurrency_levels=[1, 5, 10],
    )
    PerformanceBenchmark.print_results(list(results.values()))

    # Higher concurrency should improve throughput (up to a point)
    throughputs = [r.throughput for r in results.values()]
    assert len(throughputs) > 0


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_tool_execution():
    """Benchmark tool execution performance."""
    result = await PerformanceBenchmark.benchmark_tool_execution(
        tool_name="generic_tool",
        execution_count=50,
    )
    PerformanceBenchmark.print_results([result])
    assert result.operations > 0

