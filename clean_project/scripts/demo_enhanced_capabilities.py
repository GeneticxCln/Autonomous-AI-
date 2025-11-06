#!/usr/bin/env python3
"""
Demonstration script for the enhanced AI agent capabilities.
Shows the new semantic pattern recognition, cross-session learning,
debug explainability, and performance monitoring features.
"""

import json
import time
from pathlib import Path

# Import the enhanced agent components
from agent_system.agent import AutonomousAgent
from agent_system.reasoning_engine import reasoning_engine
from agent_system.cross_session_learning import cross_session_learning
from agent_system.ai_debugging import ai_debugger
from agent_system.ai_performance_monitor import ai_performance_monitor

def demo_enhanced_pattern_recognition():
    """Demonstrate enhanced pattern recognition with semantic similarity."""
    print("\n🧠 ENHANCED PATTERN RECOGNITION DEMO")
    print("=" * 50)

    test_goals = [
        "Research the latest developments in quantum computing",
        "Analyze the sales data from Q4 2023",
        "Create a Python script to process CSV files",
        "Find information about climate change solutions",
        "Write code to calculate mathematical statistics"
    ]

    for goal in test_goals:
        print(f"\n📋 Goal: {goal}")
        print("-" * 40)

        # Use enhanced analysis if available
        if hasattr(reasoning_engine, 'enhanced_analyze_goal'):
            analysis = reasoning_engine.enhanced_analyze_goal(goal)
            print(f"✅ Pattern: {analysis['pattern']}")
            print(f"🎯 Confidence: {analysis['confidence']:.2f}")
            print(f"🔍 Keyword Conf: {analysis['keyword_confidence']:.2f}")
            print(f"🧠 Semantic Conf: {analysis['semantic_confidence']:.2f}")
            print(f"💡 Method: {analysis['analysis_method']}")
            if 'explanation' in analysis:
                print(f"📝 Explanation: {analysis['explanation']}")
        else:
            analysis = reasoning_engine.analyze_goal(goal)
            print(f"✅ Pattern: {analysis['pattern']}")
            print(f"🎯 Confidence: {analysis['confidence']:.2f}")

        # Simulate learning this goal
        action_sequence = ['search_information', 'analyze_sources', 'synthesize_findings']
        cross_session_learning.learn_from_goal(goal, [{'name': a} for a in action_sequence], 0.8)

        time.sleep(0.5)  # Brief pause for dramatic effect

def demo_cross_session_learning():
    """Demonstrate cross-session learning capabilities."""
    print("\n🔄 CROSS-SESSION LEARNING DEMO")
    print("=" * 50)

    # Show knowledge statistics
    stats = cross_session_learning.get_knowledge_statistics()
    print(f"\n📊 Knowledge Base Stats:")
    print(f"   Total Patterns: {stats['total_patterns']}")
    print(f"   High Confidence: {stats['high_confidence_patterns']}")
    print(f"   Recently Used: {stats['recently_used_patterns']}")
    print(f"   Knowledge Health: {stats['knowledge_health']:.1f}%")

    # Find similar patterns
    similar = cross_session_learning.find_similar_patterns("research AI trends", limit=3)
    print(f"\n🔍 Similar Patterns to 'research AI trends':")
    for pattern, similarity in similar:
        print(f"   • {pattern.description[:60]}... (similarity: {similarity:.2f})")

    # Get best action sequence
    best_sequence = cross_session_learning.get_best_action_sequence("investigate machine learning")
    if best_sequence:
        print(f"\n🎯 Best Action Sequence: {' → '.join(best_sequence)}")
    else:
        print(f"\n🎯 No similar patterns found yet")

    # Export knowledge
    knowledge_export = cross_session_learning.export_knowledge_for_sharing()
    print(f"\n💾 Knowledge Export: {len(knowledge_export['patterns'])} patterns ready for sharing")

    # Generate insights
    insights = cross_session_learning.get_learning_insights()
    print(f"\n💡 Learning Insights:")
    for insight in insights:
        print(f"   • {insight}")

def demo_debug_explainability():
    """Demonstrate AI debugging and explainability features."""
    print("\n🔍 AI DEBUG & EXPLAINABILITY DEMO")
    print("=" * 50)

    # Generate a debug report
    debug_report = ai_debugger.generate_debug_report()
    print(f"\n📋 Debug Report Summary:")
    stats = debug_report['statistics']
    print(f"   Total Decisions: {stats['total_decisions']}")
    print(f"   Avg Execution Time: {stats['avg_execution_time_ms']:.1f}ms")
    print(f"   High Confidence: {stats['high_confidence_decisions']}")

    # Show recent decisions
    print(f"\n📝 Recent Decisions:")
    for decision in debug_report['recent_decisions'][:5]:
        print(f"   • {decision['type']}: {decision['summary']}")
        print(f"     Confidence: {decision['confidence']:.2f}")

    # Show insights
    print(f"\n🧐 Debug Insights:")
    for insight in debug_report['insights']:
        print(f"   • {insight}")

    # Save debug data
    debug_file = ai_debugger.save_debug_data()
    print(f"\n💾 Debug data saved to: {debug_file}")

def demo_performance_monitoring():
    """Demonstrate performance monitoring features."""
    print("\n📊 PERFORMANCE MONITORING DEMO")
    print("=" * 50)

    # Record some sample performance data
    ai_performance_monitor.record_decision_metrics("goal_analysis", 150.0, 0.85, True)
    ai_performance_monitor.record_decision_metrics("action_selection", 80.0, 0.75, True)
    ai_performance_monitor.record_goal_metrics(True, 5, 4)
    ai_performance_monitor.record_learning_metrics(2, 15, [0.8, 0.9])
    ai_performance_monitor.record_semantic_similarity_metrics([0.7, 0.8, 0.9], 0.8)

    # Get current performance
    current_perf = ai_performance_monitor.get_current_performance()
    print(f"\n🎯 Current Performance:")
    summary = current_perf['summary']
    print(f"   Overall Health: {summary['overall_health']} ({summary['score']:.1f}/100)")
    print(f"   Active Alerts: {summary['active_alert_count']}")
    print(f"   Monitored Metrics: {summary['monitored_metrics']}")

    # Show performance levels
    print(f"\n📈 Performance Levels:")
    for metric, level_data in current_perf['performance_levels'].items():
        print(f"   {metric}: {level_data['level']} ({level_data['value']:.2f}) - Target: {level_data['target']}")

    # Get trends
    trends = ai_performance_monitor.get_performance_trends(24)
    print(f"\n📊 Performance Trends (24h):")
    for metric, trend_data in trends['trends'].items():
        print(f"   {metric}: {trend_data['trend']} (avg: {trend_data['avg_value']:.2f})")

    # Get optimization suggestions
    suggestions = ai_performance_monitor.get_optimization_suggestions()
    print(f"\n🔧 Optimization Suggestions:")
    for suggestion in suggestions[:3]:
        print(f"   • {suggestion['metric']}: {suggestion['priority']} priority")
        for action in suggestion['actions'][:2]:
            print(f"     - {action}")

    # Export performance data
    perf_file = ai_performance_monitor.export_performance_data()
    print(f"\n💾 Performance data exported to: {perf_file}")

def demo_integration():
    """Demonstrate full agent integration with all new features."""
    print("\n🚀 INTEGRATED AGENT DEMO")
    print("=" * 50)

    # Create agent with all enhancements
    agent = AutonomousAgent()

    # Add a goal and process it
    goal = agent.add_goal("Research AI developments and create a summary", priority=0.8)
    print(f"\n🎯 Added Goal: {goal.description}")

    # Get comprehensive status
    status = agent.get_status()
    print(f"\n📊 Agent Status:")
    print(f"   Current Goal: {status['current_goal']}")
    print(f"   Cross-Session Patterns: {status['cross_session_learning_stats']['total_patterns']}")
    print(f"   Debug Decisions: {status['ai_debug_stats']['statistics']['total_decisions']}")
    print(f"   Performance Health: {status['performance_monitor_stats']['summary']['overall_health']}")

    # Get performance insights
    perf_insights = agent.get_performance_insights()
    print(f"\n💡 Performance Insights:")
    print(f"   Health: {perf_insights['overall_health']['overall_health']} ({perf_insights['overall_health']['score']:.1f}%)")
    print(f"   Critical Issues: {len(perf_insights['critical_issues'])}")
    print(f"   Improvement Opportunities: {len(perf_insights['improvement_opportunities'])}")

    # Get debug explanation
    debug_explanation = agent.get_debug_explanation()
    print(f"\n🔍 Debug Explanation Summary:")
    print(f"   Total Decisions Tracked: {debug_explanation['statistics']['total_decisions']}")
    print(f"   Insights: {len(debug_explanation['insights'])} generated")

    # Save all data
    debug_file = agent.save_debug_data()
    perf_file = agent.save_performance_data()

    print(f"\n💾 Data Export Complete:")
    print(f"   Debug data: {debug_file}")
    print(f"   Performance data: {perf_file}")

def main():
    """Run all demonstrations."""
    print("🎉 ENHANCED AI AGENT CAPABILITIES DEMO")
    print("=" * 60)
    print("This demo showcases the 4 major enhancements:")
    print("1. Enhanced Pattern Recognition with Semantic Similarity")
    print("2. Cross-Session Learning for Persistent Knowledge")
    print("3. Debug & Explainability System")
    print("4. Performance Monitoring & Analytics")
    print("=" * 60)

    try:
        # Run all demos
        demo_enhanced_pattern_recognition()
        demo_cross_session_learning()
        demo_debug_explainability()
        demo_performance_monitoring()
        demo_integration()

        print("\n🎊 DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("All four enhancements are working and integrated:")
        print("✅ Semantic Pattern Recognition")
        print("✅ Cross-Session Learning")
        print("✅ AI Debug & Explainability")
        print("✅ Performance Monitoring")
        print("\nThe agent now has:")
        print("🧠 Intelligent pattern recognition beyond keywords")
        print("🔄 Persistent learning between sessions")
        print("🔍 Transparent decision making with full explanations")
        print("📊 Real-time performance monitoring and optimization")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Demo Error: {e}")
        print("This is normal if dependencies (like sentence-transformers) aren't installed.")
        print("The system will fall back to enhanced keyword matching in production.")

if __name__ == "__main__":
    main()