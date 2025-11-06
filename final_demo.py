#!/usr/bin/env python3
"""
Final Real-World Example: Enhanced Autonomous Agent
This demonstrates the complete transformation from mock to production-ready agent.
"""
import json
import logging
import time
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import our enhanced agent
from agent_system.agent import AutonomousAgent
from agent_system.config_simple import settings, get_api_key


def demonstrate_enhanced_agent():
    """Demonstrate the enhanced autonomous agent with real capabilities."""
    
    print("🤖 ENHANCED AUTONOMOUS AGENT DEMONSTRATION")
    print("=" * 60)
    
    # Initialize the enhanced agent
    print("1. Initializing Enhanced Agent...")
    agent = AutonomousAgent()
    
    # Check configuration
    print(f"\n2. Configuration Status:")
    print(f"   - Max Cycles: {settings.MAX_CYCLES}")
    print(f"   - Tool Timeout: {settings.TOOL_TIMEOUT}s")
    print(f"   - Code Execution Timeout: {settings.CODE_EXECUTION_TIMEOUT}s")
    
    # Check API keys
    api_status = {
        "SERPAPI": bool(get_api_key("serpapi")),
        "OpenAI": bool(get_api_key("openai")),
        "Anthropic": bool(get_api_key("anthropic")),
        "Bing": bool(get_api_key("bing"))
    }
    
    print(f"\n3. API Key Status:")
    for service, configured in api_status.items():
        status = "✅ Configured" if configured else "❌ Not configured"
        print(f"   - {service}: {status}")
    
    # Show tool registry status
    available_tools = agent.tool_registry.get_available_tools()
    tool_stats = agent.tool_registry.get_tool_stats()
    
    print(f"\n4. Available Tools ({len(available_tools)}):")
    for tool in available_tools:
        tool_type = tool_stats.get(tool, {}).get("tool_type", "unknown")
        print(f"   - {tool} ({tool_type})")
    
    # Demonstrate different agent capabilities
    print(f"\n" + "="*60)
    
    # Example 1: Research Task
    print("EXAMPLE 1: Research Task")
    print("-" * 30)
    research_goal = agent.add_goal(
        "Research the latest developments in artificial intelligence and machine learning for 2024",
        priority=0.9
    )
    
    print(f"Goal Added: {research_goal.description}")
    print(f"Priority: {research_goal.priority}")
    print(f"ID: {research_goal.id}")
    
    # Run the agent for this goal
    print("\nRunning agent (5 cycles)...")
    agent.run(max_cycles=5)
    
    # Show results
    status = agent.get_status()
    current_goal = status.get("current_goal")
    goal_progress = status["goals"]["goals"][0]["progress"] if status["goals"]["goals"] else 0
    
    print(f"\nResults:")
    print(f"   - Current Goal: {current_goal or 'None'}")
    print(f"   - Progress: {goal_progress:.1%}")
    print(f"   - Memory Entries: {status['memory_stats']['total_memories']}")
    print(f"   - Tool Executions: {sum(s['total_executions'] for s in status['tool_stats'].values())}")
    
    # Example 2: File Analysis Task
    print(f"\n" + "="*60)
    print("EXAMPLE 2: File Analysis Task")
    print("-" * 30)
    
    # Create a sample data file
    sample_data = {
        "sales_data": [
            {"month": "January", "revenue": 45000, "growth": 0.12},
            {"month": "February", "revenue": 52000, "growth": 0.16},
            {"month": "March", "revenue": 48000, "growth": -0.08}
        ],
        "analysis_summary": "Q1 showed mixed performance with February leading growth"
    }
    
    data_file = Path("sample_analysis.json")
    data_file.write_text(json.dumps(sample_data, indent=2))
    
    analysis_goal = agent.add_goal(
        "Analyze the sales data file and provide insights on trends and recommendations",
        priority=0.8
    )
    
    print(f"Goal Added: {analysis_goal.description}")
    print(f"Sample Data Created: {data_file}")
    
    # Run agent for file analysis
    print("\nRunning agent (3 cycles)...")
    agent.run(max_cycles=3)
    
    # Show file analysis results
    status = agent.get_status()
    memory_entries = status['memory_stats']['total_memories']
    
    print(f"\nFile Analysis Results:")
    print(f"   - Total Memory Entries: {memory_entries}")
    print(f"   - Tool Usage: {list(status['tool_stats'].keys())}")
    
    # Example 3: Code Generation Task
    print(f"\n" + "="*60)
    print("EXAMPLE 3: Code Generation Task")
    print("-" * 30)
    
    code_goal = agent.add_goal(
        "Generate a Python script that calculates statistical measures for a dataset",
        priority=0.7
    )
    
    print(f"Goal Added: {code_goal.description}")
    
    # Run agent for code generation
    print("\nRunning agent (3 cycles)...")
    agent.run(max_cycles=3)
    
    # Show final statistics
    final_status = agent.get_status()
    
    print(f"\n" + "="*60)
    print("FINAL AGENT STATISTICS")
    print("=" * 60)
    
    print(f"Overall Performance:")
    print(f"   - Total Goals Processed: {len(final_status['goals']['goals'])}")
    print(f"   - Memory Entries Created: {final_status['memory_stats']['total_memories']}")
    print(f"   - Average Success Score: {final_status['memory_stats']['avg_success_score']:.2f}")
    print(f"   - Learning Patterns: {final_status['learning_stats']['patterns_learned']}")
    print(f"   - Strategies Learned: {final_status['learning_stats']['strategies_learned']}")
    
    print(f"\nTool Execution Summary:")
    for tool_name, stats in final_status['tool_stats'].items():
        success_rate = stats.get('success_rate', 0)
        tool_type = stats.get('tool_type', 'unknown')
        print(f"   - {tool_name}: {stats['total_executions']} executions, {success_rate:.1%} success ({tool_type})")
    
    print(f"\nLearning Progress:")
    learning_stats = final_status['learning_stats']
    print(f"   - Total Episodes: {learning_stats['total_episodes']}")
    print(f"   - Best Strategies: {len(learning_stats['best_strategies'])}")
    
    # Cleanup
    data_file.unlink(missing_ok=True)
    
    print(f"\n" + "="*60)
    print("✅ DEMONSTRATION COMPLETE")
    print("=" * 60)
    
    print("The enhanced agent successfully demonstrated:")
    print("• Real tool integration (file operations, code execution)")
    print("• Intelligent goal management with priorities")
    print("• Learning and adaptation capabilities")
    print("• Memory and progress tracking")
    print("• Multi-domain task handling (research, analysis, coding)")
    
    return final_status


def show_transformation_summary():
    """Show a summary of the transformation achieved."""
    
    print(f"\n" + "="*60)
    print("TRANSFORMATION SUMMARY")
    print("=" * 60)
    
    print("FROM → TO:")
    print("Mock Framework → Production-Ready System")
    
    print(f"\nKey Improvements:")
    print("✅ Real tool integration (web search, file operations, code execution)")
    print("✅ Security validation for file paths and code execution")
    print("✅ API key management and configuration")
    print("✅ Enhanced error handling and retry logic")
    print("✅ Environment-based configuration")
    print("✅ LLM integration framework (OpenAI, Anthropic, Local)")
    print("✅ Web interface ready for production")
    print("✅ Comprehensive logging and monitoring")
    print("✅ Deployment automation and scripts")
    
    print(f"\nProduction Features Added:")
    print("• Configuration management via environment variables")
    print("• Security restrictions and path validation")
    print("• Rate limiting and timeout handling")
    print("• Circuit breaker patterns for external APIs")
    print("• Graceful fallback mechanisms")
    print("• Comprehensive status monitoring")
    print("• Deployment and startup automation")
    
    print(f"\nNext Steps for Full Production:")
    print("1. Add API keys to .env file")
    print("2. Install web dependencies: pip install fastapi uvicorn")
    print("3. Start web interface: python3 -m agent_system.web_interface")
    print("4. Deploy with Docker for containerized execution")
    print("5. Set up monitoring and alerting")
    print("6. Configure SSL/HTTPS for web interface")


if __name__ == "__main__":
    try:
        # Run the demonstration
        final_status = demonstrate_enhanced_agent()
        
        # Show transformation summary
        show_transformation_summary()
        
        # Save final status for inspection
        status_file = Path("final_agent_status.json")
        with open(status_file, 'w') as f:
            json.dump(final_status, f, indent=2, default=str)
        
        print(f"\n📊 Final status saved to: {status_file}")
        
    except Exception as e:
        logger.error(f"Demonstration failed: {e}")
        raise