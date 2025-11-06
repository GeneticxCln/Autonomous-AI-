#!/usr/bin/env python3
"""
Demonstration script showing the difference between mock and real tools.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from agent_system.agent import AutonomousAgent
from agent_system.config_simple import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def demo_mock_tools():
    """Demonstrate agent with mock tools."""
    logger.info("=== DEMO: Agent with Mock Tools ===")
    
    agent = AutonomousAgent()
    agent.tool_registry.disable_real_tools()  # Ensure mock tools are used
    
    # Add a test goal
    agent.add_goal("Find information about Python programming", priority=0.8)
    
    # Run for a few cycles
    agent.run(max_cycles=3)
    
    # Show results
    status = agent.get_status()
    print("\nMOCK TOOLS RESULTS:")
    print(json.dumps(status, indent=2, default=str))
    
    return status


def demo_real_tools():
    """Demonstrate agent with real tools (if API keys available)."""
    logger.info("=== DEMO: Agent with Real Tools ===")
    
    from agent_system.config_simple import get_api_key
    
    # Check if we have API keys
    has_api_keys = bool(
        get_api_key("serpapi") or 
        get_api_key("bing") or 
        get_api_key("google")
    )
    
    if not has_api_keys:
        print("\nNo search API keys found in environment.")
        print("To test real tools, set one of:")
        print("  - SERPAPI_KEY")
        print("  - BING_SEARCH_KEY") 
        print("  - GOOGLE_SEARCH_KEY")
        print("\nFalling back to mock tools demo...")
        return demo_mock_tools()
    
    agent = AutonomousAgent()
    agent.tool_registry.enable_real_tools()
    
    # Add a test goal
    agent.add_goal("Search for latest AI trends in 2024", priority=0.9)
    
    # Run for a few cycles
    agent.run(max_cycles=5)
    
    # Show results
    status = agent.get_status()
    print("\nREAL TOOLS RESULTS:")
    print(json.dumps(status, indent=2, default=str))
    
    return status


def demo_file_operations():
    """Demonstrate real file operations."""
    logger.info("=== DEMO: Real File Operations ===")
    
    # Create a test file
    test_file = Path("test_file.txt")
    test_file.write_text("Hello, this is a test file for the agent!\nIt contains multiple lines.\nLine 3 is here.")
    
    agent = AutonomousAgent()
    
    # Create a goal that requires file operations
    agent.add_goal("Read and analyze the test file", priority=0.7)
    
    # Run until file operation is needed
    agent.run(max_cycles=2)
    
    # Clean up
    test_file.unlink(missing_ok=True)
    
    status = agent.get_status()
    print("\nFILE OPERATIONS RESULTS:")
    print(json.dumps(status, indent=2, default=str))


def demo_code_execution():
    """Demonstrate real code execution."""
    logger.info("=== DEMO: Real Code Execution ===")
    
    agent = AutonomousAgent()
    
    # Create a goal that requires code execution
    agent.add_goal("Execute a simple Python calculation", priority=0.6)
    
    agent.run(max_cycles=2)
    
    status = agent.get_status()
    print("\nCODE EXECUTION RESULTS:")
    print(json.dumps(status, indent=2, default=str))


def main():
    """Main demo function."""
    print("Autonomous Agent System - Real Tools Demo")
    print("=" * 50)
    
    # Show configuration
    print(f"\nConfiguration:")
    print(f"  - Max Cycles: {settings.MAX_CYCLES}")
    print(f"  - Tool Timeout: {settings.TOOL_TIMEOUT}s")
    print(f"  - Log Level: {settings.LOG_LEVEL}")
    
    # Check API keys
    from agent_system.config_simple import get_api_key
    api_keys = {
        "SERPAPI": get_api_key("serpapi"),
        "BING": get_api_key("bing"),
        "GOOGLE": get_api_key("google"),
        "OPENAI": get_api_key("openai"),
        "ANTHROPIC": get_api_key("anthropic")
    }
    
    print(f"\nAPI Keys Status:")
    for service, key in api_keys.items():
        status = "✓ Configured" if key else "✗ Not configured"
        print(f"  - {service}: {status}")
    
    print("\n" + "=" * 50)
    
    try:
        # Demo mock tools
        demo_mock_tools()
        
        print("\n" + "=" * 50)
        
        # Demo real tools (if available)
        demo_real_tools()
        
        print("\n" + "=" * 50)
        
        # Demo file operations
        demo_file_operations()
        
        print("\n" + "=" * 50)
        
        # Demo code execution
        demo_code_execution()
        
        print("\n" + "=" * 50)
        print("Demo completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    main()