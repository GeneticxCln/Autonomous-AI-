#!/usr/bin/env python3
"""
Performance Benchmarking Suite
Comprehensive performance testing for enterprise deployment
"""
import asyncio
import sys
import os
import time
import json
import statistics
from datetime import datetime
from typing import Dict, Any, List
import aiohttp
import requests

# Add the source directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class PerformanceBenchmark:
    """Comprehensive performance benchmarking suite."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {}
        self.start_time = None

    def log_result(self, test_name: str, result: Dict[str, Any]):
        """Log benchmark result."""
        self.results[test_name] = result
        print(f"📊 {test_name}:")
        for key, value in result.items():
            if isinstance(value, float):
                print(f"   {key}: {value:.2f}")
            else:
                print(f"   {key}: {value}")
        print()

    async def benchmark_api_endpoints(self) -> Dict[str, Any]:
        """Benchmark API endpoints performance."""
        print("🚀 Benchmarking API endpoints...")

        endpoints = ["/health", "/api/v1/system/info", "/api/v1/agents", "/docs"]

        results = {}

        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    # Test multiple requests
                    response_times = []
                    successful_requests = 0
                    failed_requests = 0

                    for _ in range(20):
                        start_time = time.time()
                        try:
                            async with session.get(
                                f"{self.base_url}{endpoint}",
                                timeout=aiohttp.ClientTimeout(total=10),
                            ) as response:
                                if response.status == 200:
                                    successful_requests += 1
                                else:
                                    failed_requests += 1
                            response_time = time.time() - start_time
                            response_times.append(response_time)
                        except Exception as e:
                            failed_requests += 1
                            print(f"   Error for {endpoint}: {e}")

                    if response_times:
                        results[endpoint] = {
                            "avg_response_time": statistics.mean(response_times),
                            "min_response_time": min(response_times),
                            "max_response_time": max(response_times),
                            "median_response_time": statistics.median(response_times),
                            "p95_response_time": (
                                statistics.quantiles(response_times, n=20)[18]
                                if len(response_times) >= 20
                                else max(response_times)
                            ),
                            "successful_requests": successful_requests,
                            "failed_requests": failed_requests,
                            "success_rate": (
                                successful_requests / (successful_requests + failed_requests)
                            )
                            * 100,
                        }
                    else:
                        results[endpoint] = {
                            "error": "No successful requests",
                            "successful_requests": successful_requests,
                            "failed_requests": failed_requests,
                        }

                except Exception as e:
                    results[endpoint] = {"error": str(e)}

        self.log_result("API Endpoints", results)
        return results

    async def benchmark_concurrent_requests(
        self, concurrency: int = 10, total_requests: int = 100
    ) -> Dict[str, Any]:
        """Benchmark concurrent request handling."""
        print(f"🚀 Benchmarking concurrent requests (concurrency: {concurrency})...")

        async def make_request(session: aiohttp.ClientSession, request_id: int):
            start_time = time.time()
            try:
                async with session.get(
                    f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    end_time = time.time()
                    return {
                        "request_id": request_id,
                        "status_code": response.status,
                        "response_time": end_time - start_time,
                        "success": response.status == 200,
                    }
            except Exception as e:
                end_time = time.time()
                return {
                    "request_id": request_id,
                    "status_code": 0,
                    "response_time": end_time - start_time,
                    "success": False,
                    "error": str(e),
                }

        async with aiohttp.ClientSession() as session:
            # Create semaphore to limit concurrency
            semaphore = asyncio.Semaphore(concurrency)

            async def bounded_request(request_id: int):
                async with semaphore:
                    return await make_request(session, request_id)

            # Execute all requests
            start_time = time.time()
            tasks = [bounded_request(i) for i in range(total_requests)]
            results = await asyncio.gather(*tasks)
            total_time = time.time() - start_time

        # Analyze results
        successful_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]

        if successful_results:
            response_times = [r["response_time"] for r in successful_results]

            benchmark_result = {
                "total_requests": total_requests,
                "successful_requests": len(successful_results),
                "failed_requests": len(failed_results),
                "success_rate": (len(successful_results) / total_requests) * 100,
                "total_time": total_time,
                "requests_per_second": total_requests / total_time,
                "avg_response_time": statistics.mean(response_times),
                "min_response_time": min(response_times),
                "max_response_time": max(response_times),
                "median_response_time": statistics.median(response_times),
                "p95_response_time": (
                    statistics.quantiles(response_times, n=100)[94]
                    if len(response_times) >= 100
                    else max(response_times)
                ),
                "p99_response_time": (
                    statistics.quantiles(response_times, n=100)[98]
                    if len(response_times) >= 100
                    else max(response_times)
                ),
            }
        else:
            benchmark_result = {
                "total_requests": total_requests,
                "successful_requests": 0,
                "failed_requests": total_requests,
                "success_rate": 0,
                "error": "No successful requests",
            }

        self.log_result(f"Concurrent Requests (concurrency: {concurrency})", benchmark_result)
        return benchmark_result

    def benchmark_memory_usage(self) -> Dict[str, Any]:
        """Benchmark memory usage."""
        print("💾 Benchmarking memory usage...")

        try:
            import psutil

            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # Get system memory
            system_memory = psutil.virtual_memory()

            memory_result = {
                "process_memory_mb": memory_info.rss / 1024 / 1024,
                "process_memory_percent": memory_percent,
                "system_memory_total_gb": system_memory.total / 1024 / 1024 / 1024,
                "system_memory_used_gb": system_memory.used / 1024 / 1024 / 1024,
                "system_memory_available_gb": system_memory.available / 1024 / 1024 / 1024,
                "system_memory_percent": system_memory.percent,
            }

        except ImportError:
            memory_result = {"error": "psutil not available"}

        self.log_result("Memory Usage", memory_result)
        return memory_result

    def benchmark_cpu_usage(self) -> Dict[str, Any]:
        """Benchmark CPU usage."""
        print("🖥️  Benchmarking CPU usage...")

        try:
            import psutil

            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_count_logical = psutil.cpu_count(logical=True)

            # Get load average (Unix only)
            try:
                load1, load5, load15 = psutil.getloadavg()
                load_average = {"load_1m": load1, "load_5m": load5, "load_15m": load15}
            except AttributeError:
                load_average = {"error": "Load average not available on this platform"}

            cpu_result = {
                "cpu_percent": cpu_percent,
                "cpu_count_physical": cpu_count,
                "cpu_count_logical": cpu_count_logical,
                **load_average,
            }

        except ImportError:
            cpu_result = {"error": "psutil not available"}

        self.log_result("CPU Usage", cpu_result)
        return cpu_result

    async def benchmark_database_operations(self) -> Dict[str, Any]:
        """Benchmark database operations."""
        print("🗄️  Benchmarking database operations...")

        # This would test actual database operations
        # For now, simulate with API calls

        db_operations = []

        # Simulate SELECT operations
        for i in range(10):
            start_time = time.time()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.base_url}/api/v1/agents", timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status == 200:
                            db_operations.append(
                                {
                                    "operation": "SELECT",
                                    "duration": time.time() - start_time,
                                    "success": True,
                                }
                            )
                        else:
                            db_operations.append(
                                {
                                    "operation": "SELECT",
                                    "duration": time.time() - start_time,
                                    "success": False,
                                }
                            )
            except Exception as e:
                db_operations.append(
                    {
                        "operation": "SELECT",
                        "duration": time.time() - start_time,
                        "success": False,
                        "error": str(e),
                    }
                )

        # Analyze results
        successful_ops = [op for op in db_operations if op["success"]]
        if successful_ops:
            durations = [op["duration"] for op in successful_ops]
            db_result = {
                "total_operations": len(db_operations),
                "successful_operations": len(successful_ops),
                "failed_operations": len(db_operations) - len(successful_ops),
                "success_rate": (len(successful_ops) / len(db_operations)) * 100,
                "avg_duration": statistics.mean(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "median_duration": statistics.median(durations),
            }
        else:
            db_result = {
                "total_operations": len(db_operations),
                "successful_operations": 0,
                "failed_operations": len(db_operations),
                "success_rate": 0,
                "error": "No successful operations",
            }

        self.log_result("Database Operations", db_result)
        return db_result

    async def benchmark_cache_performance(self) -> Dict[str, Any]:
        """Benchmark cache performance."""
        print("⚡ Benchmarking cache performance...")

        # This would test actual cache operations
        # For now, simulate with API calls to endpoints that would use cache

        cache_operations = []

        # Test repeated calls to the same endpoint (should be cached)
        endpoint = "/health"
        for i in range(10):
            start_time = time.time()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.base_url}{endpoint}", timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        duration = time.time() - start_time
                        cache_operations.append(
                            {
                                "operation": f"cache_get_{i}",
                                "duration": duration,
                                "success": response.status == 200,
                            }
                        )
            except Exception as e:
                cache_operations.append(
                    {
                        "operation": f"cache_get_{i}",
                        "duration": time.time() - start_time,
                        "success": False,
                        "error": str(e),
                    }
                )

        # Analyze results (first call should be slower, subsequent calls faster if caching works)
        if cache_operations:
            durations = [op["duration"] for op in cache_operations if op["success"]]
            if durations:
                # First request vs cached requests
                first_request_time = durations[0] if durations else 0
                cached_request_times = durations[1:] if len(durations) > 1 else []

                cache_result = {
                    "total_requests": len(cache_operations),
                    "successful_requests": len([op for op in cache_operations if op["success"]]),
                    "failed_requests": len([op for op in cache_operations if not op["success"]]),
                    "first_request_time": first_request_time,
                    "avg_cached_request_time": (
                        statistics.mean(cached_request_times) if cached_request_times else 0
                    ),
                    "improvement_factor": (
                        first_request_time / statistics.mean(cached_request_times)
                        if cached_request_times and statistics.mean(cached_request_times) > 0
                        else 1
                    ),
                    "cache_working": (
                        statistics.mean(cached_request_times) < first_request_time
                        if cached_request_times
                        else False
                    ),
                }
            else:
                cache_result = {
                    "error": "No successful requests",
                    "total_requests": len(cache_operations),
                }
        else:
            cache_result = {"error": "No cache operations performed"}

        self.log_result("Cache Performance", cache_result)
        return cache_result

    async def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all benchmarks."""
        self.start_time = time.time()
        print("🚀 Starting Performance Benchmark Suite")
        print("=" * 60)

        benchmark_results = {}

        # Run all benchmarks
        benchmark_results["api_endpoints"] = await self.benchmark_api_endpoints()
        benchmark_results["concurrent_requests"] = await self.benchmark_concurrent_requests()
        benchmark_results["memory_usage"] = self.benchmark_memory_usage()
        benchmark_results["cpu_usage"] = self.benchmark_cpu_usage()
        benchmark_results["database_operations"] = await self.benchmark_database_operations()
        benchmark_results["cache_performance"] = await self.benchmark_cache_performance()

        # Add metadata
        benchmark_results["metadata"] = {
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": time.time() - self.start_time,
            "base_url": self.base_url,
            "version": "1.0.0",
        }

        # Calculate overall score
        overall_score = self._calculate_overall_score(benchmark_results)
        benchmark_results["overall_score"] = overall_score

        # Print summary
        self._print_summary(benchmark_results)

        return benchmark_results

    def _calculate_overall_score(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall performance score."""
        scores = []

        # API performance score
        if "api_endpoints" in results:
            api_result = results["api_endpoints"]
            if "avg_response_time" in list(api_result.values())[0]:
                avg_response_times = [
                    v["avg_response_time"] for v in api_result.values() if "avg_response_time" in v
                ]
                if avg_response_times:
                    avg_api_time = statistics.mean(avg_response_times)
                    # Score based on response time (100ms = 100 points, 1s = 50 points, >2s = 0 points)
                    if avg_api_time < 0.1:
                        api_score = 100
                    elif avg_api_time < 0.5:
                        api_score = 80
                    elif avg_api_time < 1.0:
                        api_score = 60
                    else:
                        api_score = 40
                    scores.append(api_score)

        # Concurrency score
        if "concurrent_requests" in results:
            conc_result = results["concurrent_requests"]
            if "success_rate" in conc_result:
                success_rate = conc_result["success_rate"]
                if success_rate >= 99:
                    conc_score = 100
                elif success_rate >= 95:
                    conc_score = 80
                elif success_rate >= 90:
                    conc_score = 60
                else:
                    conc_score = 40
                scores.append(conc_score)

        # Memory score
        if "memory_usage" in results:
            mem_result = results["memory_usage"]
            if "process_memory_percent" in mem_result:
                memory_percent = mem_result["process_memory_percent"]
                if memory_percent < 50:
                    mem_score = 100
                elif memory_percent < 75:
                    mem_score = 80
                elif memory_percent < 90:
                    mem_score = 60
                else:
                    mem_score = 40
                scores.append(mem_score)

        # Calculate overall score
        overall_score_value = statistics.mean(scores) if scores else 0

        return {
            "score": overall_score_value,
            "grade": self._get_grade(overall_score_value),
            "individual_scores": {
                "api_performance": scores[0] if len(scores) > 0 else 0,
                "concurrency": scores[1] if len(scores) > 1 else 0,
                "memory_efficiency": scores[2] if len(scores) > 2 else 0,
            },
        }

    def _get_grade(self, score: float) -> str:
        """Get letter grade from score."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def _print_summary(self, results: Dict[str, Any]):
        """Print benchmark summary."""
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 60)

        if "overall_score" in results:
            score_info = results["overall_score"]
            print(f"🎯 Overall Score: {score_info['score']:.1f} ({score_info['grade']})")

        print(f"⏱️  Total Duration: {results['metadata']['duration_seconds']:.2f}s")
        print(f"🌐 Test URL: {results['metadata']['base_url']}")

        # Performance highlights
        if "concurrent_requests" in results:
            conc_result = results["concurrent_requests"]
            if "requests_per_second" in conc_result:
                print(f"⚡ Throughput: {conc_result['requests_per_second']:.1f} req/s")

        if "cache_performance" in results:
            cache_result = results["cache_performance"]
            if "cache_working" in cache_result and cache_result["cache_working"]:
                print("🚀 Cache: Working (subsequent requests faster)")

        print("=" * 60)

        # Grade interpretation
        score_info = results.get("overall_score", {})
        if score_info.get("score", 0) >= 90:
            print("🎉 EXCELLENT: Production ready with outstanding performance!")
        elif score_info.get("score", 0) >= 80:
            print("✅ GOOD: Production ready with good performance")
        elif score_info.get("score", 0) >= 70:
            print("⚠️  ACCEPTABLE: Needs optimization before production")
        else:
            print("❌ POOR: Significant performance issues need resolution")

    def save_results(self, filename: str = "benchmark-results.json"):
        """Save benchmark results to file."""
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"💾 Results saved to {filename}")


async def main():
    """Main benchmark execution."""
    import os

    # Get API base URL from environment or use default
    base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")

    benchmark = PerformanceBenchmark(base_url)

    try:
        results = await benchmark.run_all_benchmarks()
        benchmark.save_results("benchmark-results.json")

        # Return exit code based on performance
        if results.get("overall_score", {}).get("score", 0) >= 80:
            return 0
        else:
            return 1

    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        return 1


if __name__ == "__main__":
    import asyncio

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
