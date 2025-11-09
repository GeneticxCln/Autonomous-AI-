#!/usr/bin/env python3
"""
Enterprise Infrastructure Test Suite
Comprehensive testing for Redis caching, task queues, and monitoring
"""
import asyncio
import os
import sys
import time
from datetime import datetime

# Add the source directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_system.cache_manager import cache_manager
from agent_system.infrastructure_manager import (
    cache_response,
    get_cached_response,
    get_infrastructure_health,
    get_performance_stats,
    infrastructure_manager,
)
from agent_system.task_queue import (
    task_queue_manager,
)


class InfrastructureTester:
    """Comprehensive infrastructure testing suite."""

    def __init__(self):
        self.test_results = []
        self.start_time = None
        self.redis_available = False

    def log_test(self, test_name: str, status: str, message: str = "", duration: float = 0):
        """Log test result."""
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "duration": duration,
            "timestamp": datetime.now().isoformat(),
        }
        self.test_results.append(result)

        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        duration_str = f" ({duration:.2f}s)" if duration > 0 else ""
        print(f"{status_emoji} {test_name}: {status}{duration_str}")
        if message:
            print(f"   {message}")

    async def test_redis_connection(self) -> bool:
        """Test Redis connection and basic operations."""
        start_time = time.time()

        try:
            # Test connection
            connected = await cache_manager.connect()
            if not connected:
                self.log_test("Redis Connection", "FAIL", "Could not connect to Redis")
                return False

            # Test basic operations
            test_key = "test:infrastructure"
            test_value = {"timestamp": datetime.now().isoformat(), "test": True}

            # Set operation
            set_result = await cache_manager.set("test", test_key, test_value, ttl=60)
            if not set_result:
                self.log_test("Redis SET", "FAIL", "SET operation failed")
                return False

            # Get operation
            get_result = await cache_manager.get("test", test_key)
            if get_result != test_value:
                self.log_test("Redis GET", "FAIL", "Value mismatch")
                return False

            # Exists operation
            exists_result = await cache_manager.exists("test", test_key)
            if not exists_result:
                self.log_test("Redis EXISTS", "FAIL", "Key should exist")
                return False

            # Delete operation
            delete_result = await cache_manager.delete("test", test_key)
            if not delete_result:
                self.log_test("Redis DELETE", "FAIL", "DELETE operation failed")
                return False

            self.redis_available = True
            duration = time.time() - start_time
            self.log_test(
                "Redis Connection & Operations", "PASS", "All Redis operations successful", duration
            )
            return True

        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Redis Connection", "FAIL", f"Exception: {str(e)}", duration)
            return False

    async def test_cache_functionality(self) -> bool:
        """Test advanced cache functionality."""
        if not self.redis_available:
            self.log_test("Cache Functionality", "SKIP", "Redis not available")
            return False

        start_time = time.time()

        try:
            # Test session management
            session_id = "test-session-123"
            session_data = {
                "user_id": "user456",
                "login_time": datetime.now().isoformat(),
                "permissions": ["read", "write"],
            }

            session_set = await cache_manager.set_session(session_id, session_data, ttl=300)
            if not session_set:
                self.log_test("Session Cache SET", "FAIL", "Session storage failed")
                return False

            session_get = await cache_manager.get_session(session_id)
            if session_get != session_data:
                self.log_test("Session Cache GET", "FAIL", "Session data mismatch")
                return False

            # Test API response caching
            endpoint = "/api/test"
            params = {"user_id": "123", "format": "json"}
            api_response = {"data": [1, 2, 3], "status": "success"}

            cache_result = await cache_manager.cache_api_response(
                endpoint, params, api_response, ttl=60
            )
            if not cache_result:
                self.log_test("API Response Cache", "FAIL", "API response caching failed")
                return False

            cached_response = await cache_manager.get_cached_api_response(endpoint, params)
            if cached_response != api_response:
                self.log_test("API Response Cache GET", "FAIL", "Cached response mismatch")
                return False

            # Test TTL functionality
            ttl_key = "test:ttl"
            await cache_manager.set("test", ttl_key, "short-lived", ttl=1)
            time.sleep(2)  # Wait for expiration
            expired_value = await cache_manager.get("test", ttl_key)

            if expired_value is not None:
                self.log_test("Cache TTL", "FAIL", "Expired value should be None")
                return False

            duration = time.time() - start_time
            self.log_test(
                "Cache Functionality", "PASS", "All cache operations successful", duration
            )
            return True

        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Cache Functionality", "FAIL", f"Exception: {str(e)}", duration)
            return False

    async def test_task_queue(self) -> bool:
        """Test Redis Queue functionality."""
        if not self.redis_available:
            self.log_test("Task Queue", "SKIP", "Redis not available")
            return False

        start_time = time.time()

        try:
            # Initialize task queue
            if not task_queue_manager._is_initialized:
                queue_init = task_queue_manager.initialize()
                if not queue_init:
                    self.log_test("Task Queue Init", "FAIL", "Queue initialization failed")
                    return False

            # Test job enqueue
            def test_task(x: int, y: int) -> int:
                return x + y

            job = task_queue_manager.enqueue_job(test_task, 5, 3, timeout=30)
            if not job or not job.id:
                self.log_test("Task Enqueue", "FAIL", "Job enqueue failed")
                return False

            # Wait for job completion
            max_wait = 10
            wait_time = 0
            result = None

            while wait_time < max_wait:
                result = task_queue_manager.get_job_result(job.id, timeout=1)
                if result is not None:
                    break
                await asyncio.sleep(0.5)
                wait_time += 0.5

            if result != 8:  # 5 + 3 = 8
                self.log_test("Task Execution", "FAIL", f"Expected 8, got {result}")
                return False

            # Test queue statistics
            stats = task_queue_manager.get_overall_stats()
            if "error" in stats:
                self.log_test("Queue Statistics", "FAIL", f"Stats error: {stats['error']}")
                return False

            duration = time.time() - start_time
            self.log_test("Task Queue", "PASS", "Task queue operations successful", duration)
            return True

        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Task Queue", "FAIL", f"Exception: {str(e)}", duration)
            return False

    async def test_integration(self) -> bool:
        """Test infrastructure manager integration."""
        if not self.redis_available:
            self.log_test("Infrastructure Integration", "SKIP", "Redis not available")
            return False

        start_time = time.time()

        try:
            # Test infrastructure initialization
            init_result = await infrastructure_manager.initialize()
            if not init_result:
                self.log_test("Infrastructure Init", "FAIL", "Infrastructure init failed")
                return False

            # Test health check
            health = await get_infrastructure_health()
            if not health.get("overall", False):
                self.log_test("Health Check", "FAIL", "Infrastructure health check failed")
                return False

            # Test performance metrics
            metrics = await get_performance_stats()
            if "error" in metrics:
                self.log_test("Performance Metrics", "FAIL", f"Metrics error: {metrics['error']}")
                return False

            # Test cache response functionality
            endpoint = "/api/test/endpoint"
            params = {"param1": "value1", "param2": "value2"}
            test_response = {"result": "success", "data": [1, 2, 3]}

            cache_set = await cache_response(endpoint, params, test_response, ttl=60)
            if not cache_set:
                self.log_test("Response Caching", "FAIL", "Response caching failed")
                return False

            cached_response = await get_cached_response(endpoint, params)
            if cached_response != test_response:
                self.log_test("Response Retrieval", "FAIL", "Cached response retrieval failed")
                return False

            duration = time.time() - start_time
            self.log_test(
                "Infrastructure Integration", "PASS", "Integration tests successful", duration
            )
            return True

        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Infrastructure Integration", "FAIL", f"Exception: {str(e)}", duration)
            return False

    async def test_performance(self) -> bool:
        """Test infrastructure performance."""
        if not self.redis_available:
            self.log_test("Performance", "SKIP", "Redis not available")
            return False

        start_time = time.time()

        try:
            # Test cache performance
            num_operations = 100
            cache_times = []

            for i in range(num_operations):
                op_start = time.time()
                await cache_manager.set("perf", f"key{i}", f"value{i}", ttl=60)
                await cache_manager.get("perf", f"key{i}")
                cache_times.append(time.time() - op_start)

            avg_cache_time = sum(cache_times) / len(cache_times)

            if avg_cache_time > 0.01:  # 10ms threshold
                self.log_test(
                    "Cache Performance", "WARN", f"Average cache time: {avg_cache_time*1000:.2f}ms"
                )
            else:
                self.log_test(
                    "Cache Performance", "PASS", f"Average cache time: {avg_cache_time*1000:.2f}ms"
                )

            # Test queue performance
            def quick_task():
                return "done"

            queue_times = []
            for i in range(10):
                op_start = time.time()
                task_queue_manager.enqueue_job(quick_task, timeout=5)
                queue_times.append(time.time() - op_start)

            avg_queue_time = sum(queue_times) / len(queue_times)

            if avg_queue_time > 0.1:  # 100ms threshold
                self.log_test(
                    "Queue Performance", "WARN", f"Average queue time: {avg_queue_time*1000:.2f}ms"
                )
            else:
                self.log_test(
                    "Queue Performance", "PASS", f"Average queue time: {avg_queue_time*1000:.2f}ms"
                )

            # Test concurrent operations
            concurrent_tasks = []
            for i in range(20):
                task = cache_manager.set("concurrent", f"key{i}", f"value{i}", ttl=60)
                concurrent_tasks.append(task)

            await asyncio.gather(*concurrent_tasks)

            duration = time.time() - start_time
            self.log_test(
                "Performance", "PASS", f"Performance tests completed in {duration:.2f}s", duration
            )
            return True

        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Performance", "FAIL", f"Exception: {str(e)}", duration)
            return False

    async def test_error_handling(self) -> bool:
        """Test error handling and resilience."""
        start_time = time.time()

        try:
            # Test operations when Redis is disconnected
            if self.redis_available:
                await cache_manager.disconnect()

            # These should gracefully fail
            result = await cache_manager.set("test", "key", "value")
            if result is not False:
                self.log_test("Error Handling", "FAIL", "Should fail when Redis disconnected")
                return False

            result = await cache_manager.get("test", "key")
            if result is not None:
                self.log_test(
                    "Error Handling", "FAIL", "Should return None when Redis disconnected"
                )
                return False

            # Reconnect for other tests
            if not self.redis_available:
                await cache_manager.connect()
                self.redis_available = True

            duration = time.time() - start_time
            self.log_test("Error Handling", "PASS", "Error handling works correctly", duration)
            return True

        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Error Handling", "FAIL", f"Exception: {str(e)}", duration)
            return False

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("🏁 INFRASTRUCTURE TEST SUMMARY")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "PASS"])
        failed_tests = len([r for r in self.test_results if r["status"] == "FAIL"])
        skipped_tests = len([r for r in self.test_results if r["status"] == "SKIP"])

        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        print(f"📊 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⏭️  Skipped: {skipped_tests}")
        print(f"📈 Success Rate: {success_rate:.1f}%")

        if self.start_time:
            total_duration = time.time() - self.start_time
            print(f"⏱️  Total Duration: {total_duration:.2f}s")

        # Print failed tests
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"   • {result['test']}: {result['message']}")

        # Overall status
        if success_rate >= 90:
            print(f"\n🎉 INFRASTRUCTURE TESTING: EXCELLENT ({success_rate:.1f}%)")
        elif success_rate >= 75:
            print(f"\n✅ INFRASTRUCTURE TESTING: GOOD ({success_rate:.1f}%)")
        elif success_rate >= 50:
            print(f"\n⚠️  INFRASTRUCTURE TESTING: NEEDS IMPROVEMENT ({success_rate:.1f}%)")
        else:
            print(f"\n🚨 INFRASTRUCTURE TESTING: FAILED ({success_rate:.1f}%)")

        print("=" * 60)

    async def run_all_tests(self) -> bool:
        """Run all infrastructure tests."""
        self.start_time = time.time()
        print("🚀 Starting Enterprise Infrastructure Tests")
        print("=" * 60)

        # Run tests in logical order
        tests = [
            self.test_redis_connection,
            self.test_cache_functionality,
            self.test_task_queue,
            self.test_integration,
            self.test_performance,
            self.test_error_handling,
        ]

        for test in tests:
            try:
                await test()
            except Exception as e:
                print(f"❌ Test {test.__name__} crashed: {e}")

        self.print_summary()

        # Return overall success
        failed = len([r for r in self.test_results if r["status"] == "FAIL"])
        return failed == 0


async def main():
    """Main test execution."""
    tester = InfrastructureTester()
    success = await tester.run_all_tests()

    # Cleanup
    if infrastructure_manager.is_initialized:
        await infrastructure_manager.shutdown()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
