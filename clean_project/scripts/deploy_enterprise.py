#!/usr/bin/env python3
"""
Enterprise Deployment Script
Complete infrastructure deployment and management
"""
import asyncio
import sys
import os
import subprocess
import time
from datetime import datetime
from typing import Dict, Any, Optional

# Add the source directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_system.infrastructure_manager import (
    infrastructure_manager,
    initialize_infrastructure,
    get_infrastructure_health,
    get_performance_stats,
    health_check,
)


class EnterpriseDeployer:
    """Enterprise deployment and management system."""

    def __init__(self):
        self.deployment_status = {}
        self.start_time = None

    def log_deployment(self, component: str, status: str, message: str = ""):
        """Log deployment status."""
        self.deployment_status[component] = {
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }

        status_emoji = "✅" if status == "SUCCESS" else "❌" if status == "FAILED" else "⏳"
        print(f"{status_emoji} {component}: {status}")
        if message:
            print(f"   {message}")

    async def check_prerequisites(self) -> bool:
        """Check deployment prerequisites."""
        print("🔍 Checking deployment prerequisites...")

        # Check Docker
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.log_deployment("Docker", "SUCCESS", f"Version: {result.stdout.strip()}")
            else:
                self.log_deployment("Docker", "FAILED", "Docker not found")
                return False
        except FileNotFoundError:
            self.log_deployment("Docker", "FAILED", "Docker not installed")
            return False

        # Check Docker Compose
        try:
            result = subprocess.run(["docker-compose", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.log_deployment(
                    "Docker Compose", "SUCCESS", f"Version: {result.stdout.strip()}"
                )
            else:
                self.log_deployment("Docker Compose", "FAILED", "Docker Compose not found")
                return False
        except FileNotFoundError:
            self.log_deployment("Docker Compose", "FAILED", "Docker Compose not installed")
            return False

        # Check Redis (if running locally)
        try:
            import redis

            r = redis.Redis(host="localhost", port=6379, socket_timeout=1)
            r.ping()
            self.log_deployment("Redis", "SUCCESS", "Local Redis server detected")
        except:
            self.log_deployment("Redis", "INFO", "No local Redis server (will use Docker)")

        return True

    async def deploy_infrastructure(self) -> bool:
        """Deploy infrastructure using Docker Compose."""
        print("🚀 Deploying enterprise infrastructure...")

        try:
            # Create required directories
            directories = ["data", "logs", "backups", "nginx/ssl", "nginx/sites"]
            for directory in directories:
                os.makedirs(directory, exist_ok=True)

            # Start infrastructure
            result = subprocess.run(
                ["docker-compose", "-f", "config/docker-compose.yml", "up", "-d"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                self.log_deployment("Infrastructure", "SUCCESS", "All services started")
                return True
            else:
                self.log_deployment("Infrastructure", "FAILED", result.stderr)
                return False

        except Exception as e:
            self.log_deployment("Infrastructure", "FAILED", str(e))
            return False

    async def wait_for_services(self, timeout: int = 300) -> bool:
        """Wait for all services to be healthy."""
        print("⏳ Waiting for services to be healthy...")

        start_time = time.time()
        services_to_check = [
            ("api", "http://localhost:8000/health"),
            ("redis", "redis://localhost:6379"),
            ("nginx", "http://localhost/health"),
        ]

        while time.time() - start_time < timeout:
            all_healthy = True

            for service_name, health_url in services_to_check:
                try:
                    if service_name == "redis":
                        import redis

                        r = redis.Redis(host="localhost", port=6379, socket_timeout=1)
                        r.ping()
                    elif service_name == "api":
                        import aiohttp

                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                health_url, timeout=aiohttp.ClientTimeout(total=5)
                            ) as response:
                                if response.status != 200:
                                    all_healthy = False
                    elif service_name == "nginx":
                        import aiohttp

                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                health_url, timeout=aiohttp.ClientTimeout(total=5)
                            ) as response:
                                if response.status != 200:
                                    all_healthy = False
                except:
                    all_healthy = False
                    break

            if all_healthy:
                self.log_deployment("Service Health", "SUCCESS", "All services are healthy")
                return True

            await asyncio.sleep(5)

        self.log_deployment("Service Health", "FAILED", f"Services not healthy within {timeout}s")
        return False

    async def initialize_application(self) -> bool:
        """Initialize the application infrastructure."""
        print("🔧 Initializing application infrastructure...")

        try:
            # Initialize infrastructure
            success = await infrastructure_manager.initialize(
                redis_host="localhost", redis_port=6379, redis_db=0
            )

            if success:
                self.log_deployment("Application", "SUCCESS", "Infrastructure initialized")
                return True
            else:
                self.log_deployment("Application", "FAILED", "Infrastructure initialization failed")
                return False

        except Exception as e:
            self.log_deployment("Application", "FAILED", str(e))
            return False

    async def verify_deployment(self) -> Dict[str, Any]:
        """Verify deployment status."""
        print("🔍 Verifying deployment...")

        verification_results = {}

        try:
            # Check infrastructure health
            health = await get_infrastructure_health()
            verification_results["health"] = health

            # Check performance metrics
            metrics = await get_performance_stats()
            verification_results["performance"] = metrics

            # Check overall health
            overall_health = await health_check()
            verification_results["overall"] = overall_health

            return verification_results

        except Exception as e:
            self.log_deployment("Verification", "FAILED", str(e))
            return {"error": str(e)}

    def print_deployment_summary(self, verification_results: Dict[str, Any]):
        """Print deployment summary."""
        print("\n" + "=" * 60)
        print("🎉 ENTERPRISE DEPLOYMENT SUMMARY")
        print("=" * 60)

        print(f"📅 Deployment Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  Total Duration: {time.time() - self.start_time:.2f}s")

        print("\n📊 Component Status:")
        for component, info in self.deployment_status.items():
            status_emoji = (
                "✅"
                if info["status"] == "SUCCESS"
                else "❌" if info["status"] == "FAILED" else "⏳"
            )
            print(f"   {status_emoji} {component}: {info['status']}")
            if info["message"]:
                print(f"      {info['message']}")

        if verification_results:
            print("\n🏥 Health Status:")
            if "overall" in verification_results:
                overall = verification_results["overall"]
                status = "✅ HEALTHY" if overall.get("overall", False) else "❌ UNHEALTHY"
                print(f"   Overall: {status}")

            if "cache" in verification_results:
                cache_healthy = verification_results["health"].get("cache", False)
                status = "✅ HEALTHY" if cache_healthy else "❌ UNHEALTHY"
                print(f"   Cache: {status}")

            if "queue" in verification_results:
                queue_healthy = verification_results["health"].get("queue", False)
                status = "✅ HEALTHY" if queue_healthy else "❌ UNHEALTHY"
                print(f"   Queue: {status}")

        print("\n🌐 Service URLs:")
        print("   • API: http://localhost:8000")
        print("   • API Docs: http://localhost:8000/docs")
        print("   • Prometheus: http://localhost:9090")
        print("   • Grafana: http://localhost:3000 (admin/admin)")

        print("\n🛠️ Management Commands:")
        print("   • View logs: make infra-logs")
        print("   • Check status: make infra-status")
        print("   • Health check: make health")
        print("   • Stop: make infra-down")

        print("\n🎯 Success Metrics:")
        print(
            f"   • Infrastructure: {len([c for c in self.deployment_status.values() if c['status'] == 'SUCCESS'])}/{len(self.deployment_status)} components"
        )
        print(
            f"   • Cache Hit Rate: {verification_results.get('performance', {}).get('cache', {}).get('hit_rate_percent', 'N/A')}%"
        )
        print(
            f"   • Queue Jobs: {verification_results.get('performance', {}).get('queue', {}).get('total_queued', 'N/A')}"
        )

        print("=" * 60)

    async def deploy(self) -> bool:
        """Run complete deployment."""
        self.start_time = time.time()
        print("🚀 Starting Enterprise Deployment")
        print("=" * 60)

        # Check prerequisites
        if not await self.check_prerequisites():
            print("❌ Prerequisites check failed")
            return False

        # Deploy infrastructure
        if not await self.deploy_infrastructure():
            print("❌ Infrastructure deployment failed")
            return False

        # Wait for services
        if not await self.wait_for_services():
            print("❌ Services did not become healthy")
            return False

        # Initialize application
        if not await self.initialize_application():
            print("❌ Application initialization failed")
            return False

        # Verify deployment
        verification_results = await self.verify_deployment()

        # Print summary
        self.print_deployment_summary(verification_results)

        # Check overall success
        failed_components = [
            c for c, info in self.deployment_status.items() if info["status"] == "FAILED"
        ]
        success = len(failed_components) == 0

        if success:
            print("🎉 DEPLOYMENT SUCCESSFUL!")
        else:
            print(f"❌ DEPLOYMENT FAILED! Failed components: {failed_components}")

        return success

    async def shutdown(self):
        """Shutdown deployment."""
        print("🛑 Shutting down deployment...")

        try:
            # Shutdown application infrastructure
            if infrastructure_manager.is_initialized:
                await infrastructure_manager.shutdown()

            # Stop Docker services
            subprocess.run(
                ["docker-compose", "-f", "config/docker-compose.yml", "down"], capture_output=True
            )

            print("✅ Shutdown complete")

        except Exception as e:
            print(f"❌ Shutdown error: {e}")


async def main():
    """Main deployment execution."""
    deployer = EnterpriseDeployer()

    try:
        success = await deployer.deploy()
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n⚠️ Deployment interrupted by user")
        await deployer.shutdown()
        return 1

    except Exception as e:
        print(f"❌ Deployment error: {e}")
        await deployer.shutdown()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
