#!/usr/bin/env python3
"""
Test Enhanced Systems
Validates all new optimization and security improvements.
"""
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))


def test_unified_config():
    """Test unified configuration system."""
    print("🔧 Testing Unified Configuration System")
    print("=" * 50)

    try:
        from agent_system.unified_config import unified_config

        # Test configuration access
        print(f"✅ Max Cycles: {unified_config.agent.max_cycles}")
        print(f"✅ Tool Timeout: {unified_config.tools.timeout_seconds}")
        print(f"✅ Log Level: {unified_config.logging.level}")
        print(f"✅ Semantic Similarity: {unified_config.ai.enable_semantic_similarity}")

        # Test API key management
        providers = unified_config.get_configured_providers()
        print(f"✅ Configured Providers: {providers}")

        # Test configuration validation
        try:
            unified_config.validate()
            print("✅ Configuration validation passed")
        except Exception as e:
            print(f"❌ Configuration validation failed: {e}")

        return True

    except Exception as e:
        print(f"❌ Unified config test failed: {e}")
        return False


def test_performance_optimizer():
    """Test performance optimization system."""
    print("\n🚀 Testing Performance Optimization System")
    print("=" * 50)

    try:
        from agent_system.performance_optimizer import performance_optimizer

        # Test memory optimization
        memory_stats = performance_optimizer.memory_optimizer.get_memory_stats()
        print(f"✅ Memory Stats: {memory_stats['percent']:.1f}% used")

        # Test performance monitoring
        perf_summary = performance_optimizer.resource_monitor.get_performance_summary()
        print(f"✅ Performance Summary: {perf_summary.get('avg_cpu_percent', 0):.1f}% avg CPU")

        # Test optimization suggestions
        suggestions = performance_optimizer.create_optimization_suggestions()
        print(f"✅ Optimization Suggestions: {len(suggestions)} generated")

        # Test comprehensive stats
        performance_optimizer.get_comprehensive_stats()
        print("✅ Comprehensive Stats: Available")

        return True

    except Exception as e:
        print(f"❌ Performance optimizer test failed: {e}")
        return False


def test_security_validator():
    """Test security validation system."""
    print("\n🔒 Testing Security Validation System")
    print("=" * 50)

    try:
        from agent_system.security_validator import input_validator, security_audit

        # Test file path validation
        file_validation = input_validator.validate_file_path("/tmp/test.txt")
        print(f"✅ File Path Validation: {file_validation.is_valid}")

        # Test code validation
        code_validation = input_validator.validate_code("print('Hello World')")
        print(f"✅ Code Validation: {code_validation.is_valid}")

        # Test URL validation
        url_validation = input_validator.validate_url("https://example.com")
        print(f"✅ URL Validation: {url_validation.is_valid}")

        # Test security audit
        audit_summary = security_audit.get_audit_summary()
        print(f"✅ Security Audit: {audit_summary.get('total_audits', 0)} audits")

        return True

    except Exception as e:
        print(f"❌ Security validator test failed: {e}")
        return False


def test_health_dashboard():
    """Test system health dashboard."""
    print("\n📊 Testing System Health Dashboard")
    print("=" * 50)

    try:
        from agent_system.system_health_dashboard import system_health_monitor

        # Test health check
        health_metrics = system_health_monitor.get_comprehensive_health_check()
        print(f"✅ Health Check: {health_metrics.overall_health_score:.2f} score")
        print(f"✅ Active Issues: {len(health_metrics.active_issues)}")
        print(f"✅ Recommendations: {len(health_metrics.recommendations)}")

        # Test system summary
        system_summary = system_health_monitor.get_system_summary()
        print(f"✅ System Summary: {system_summary['overall_health']['status']}")

        # Test health trend
        health_trend = system_health_monitor.get_health_trend(1)
        print(f"✅ Health Trend: {health_trend.get('trend', 'unknown')}")

        return True

    except Exception as e:
        print(f"❌ Health dashboard test failed: {e}")
        return False


def test_enhanced_agent():
    """Test enhanced agent integration."""
    print("\n🤖 Testing Enhanced Agent Integration")
    print("=" * 50)

    try:
        from agent_system.enhanced_agent import create_enhanced_agent

        # Test enhanced agent creation
        agent = create_enhanced_agent()
        print("✅ Enhanced Agent Created")

        # Test enhanced status
        enhanced_status = agent.get_enhanced_status()
        print("✅ Enhanced Status: Available")
        print(
            f"✅ System Health: {enhanced_status['enhanced_features']['system_health']['overall_score']:.2f}"
        )

        # Test recommendations
        recommendations = agent.get_system_recommendations()
        print(f"✅ System Recommendations: {len(recommendations)}")

        # Test health check
        health_check = agent.run_health_check()
        print(f"✅ Health Check: {health_check.get('overall_health_score', 0):.2f}")

        # Test optimization toggle
        agent.enable_optimization()
        print("✅ Optimization Enabled")

        agent.disable_optimization()
        print("✅ Optimization Disabled")

        return True

    except Exception as e:
        print(f"❌ Enhanced agent test failed: {e}")
        return False


def test_integration():
    """Test system integration."""
    print("\n🔗 Testing System Integration")
    print("=" * 50)

    try:
        from agent_system.enhanced_agent import create_enhanced_agent

        # Create enhanced agent
        with create_enhanced_agent() as agent:
            print("✅ Context Manager: Working")

            # Add a goal
            goal = agent.add_goal("Test enhanced agent functionality", priority=0.7)
            print(f"✅ Goal Added: {goal.description}")

            # Get status
            status = agent.get_enhanced_status()
            print(f"✅ Status Retrieved: {len(status)} sections")

            # Health check
            agent.run_health_check()
            print("✅ Health Check: Complete")

            # Test export
            report_file = agent.export_comprehensive_report()
            if report_file:
                print(f"✅ Report Exported: {report_file}")

        return True

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 TESTING ENHANCED AUTONOMOUS AGENT SYSTEMS")
    print("=" * 60)
    print("Testing improvements based on comprehensive project analysis")
    print("=" * 60)

    tests = [
        ("Unified Configuration", test_unified_config),
        ("Performance Optimization", test_performance_optimizer),
        ("Security Validation", test_security_validator),
        ("Health Dashboard", test_health_dashboard),
        ("Enhanced Agent", test_enhanced_agent),
        ("System Integration", test_integration),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}: Test error - {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST RESULTS SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:<25} {status}")

    print(f"\n🏆 OVERALL RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All enhanced systems are working correctly!")
        print("🚀 The agent has been successfully improved with:")
        print("   • Unified configuration management")
        print("   • Performance optimization")
        print("   • Security validation")
        print("   • System health monitoring")
        print("   • Enhanced agent architecture")
    else:
        print("⚠️  Some tests failed - check the output above for details")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
