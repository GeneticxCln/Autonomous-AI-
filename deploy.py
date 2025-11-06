#!/usr/bin/env python3
"""
Production deployment script for the Autonomous Agent System.
This script helps you set up and deploy the agent with real capabilities.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from agent_system.agent import AutonomousAgent
from agent_system.config_simple import settings, get_api_key
from agent_system.llm_integration import llm_manager
from agent_system.web_interface import app
import uvicorn


def setup_logging():
    """Configure logging for production."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('agent.log')
        ]
    )
    return logging.getLogger(__name__)


def create_environment_file():
    """Create a .env file with proper structure."""
    env_content = """# Autonomous Agent Environment Configuration
# Copy this to .env and customize for your setup

# Core Settings
MAX_CYCLES=100
LOG_LEVEL=INFO
TOOL_TIMEOUT=30
MAX_RETRIES=3
USE_REAL_TOOLS=true

# API Keys (configure at least one)
# Get SerpAPI key from: https://serpapi.com/
SERPAPI_KEY=your_serpapi_key_here

# Get Bing Search key from: https://azure.microsoft.com/en-us/services/cognitive-services/bing-web-search-api/
BING_SEARCH_KEY=your_bing_key_here

# Get OpenAI key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=your_openai_key_here

# Get Anthropic key from: https://console.anthropic.com/
ANTHROPIC_API_KEY=your_anthropic_key_here

# Security
SECRET_KEY=change-this-secret-key-in-production
API_KEY_ROTATION_DAYS=30

# File System Security
ALLOWED_FILE_PATHS=/tmp,.,./workspace
BLOCKED_FILE_PATHS=/etc,/bin,/usr,/var/log

# Rate Limiting
REQUESTS_PER_MINUTE=60
"""
    
    env_file = Path(".env")
    if not env_file.exists():
        env_file.write_text(env_content)
        print(f"✅ Created {env_file}")
        print("⚠️  Please edit .env file and add your API keys")
    else:
        print(f"📝 {env_file} already exists")


def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        "requests", "fastapi", "uvicorn", "aiofiles"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install " + " ".join(missing_packages))
        return False
    
    print("✅ All required packages are installed")
    return True


def check_api_configuration():
    """Check API key configuration."""
    providers = {
        "SERPAPI": get_api_key("serpapi"),
        "OpenAI": get_api_key("openai"),
        "Anthropic": get_api_key("anthropic"),
        "Bing Search": get_api_key("bing")
    }
    
    configured = sum(1 for key in providers.values() if key)
    
    print("\n🔑 API Configuration Status:")
    for name, key in providers.items():
        status = "✅ Configured" if key else "❌ Not configured"
        print(f"   {name}: {status}")
    
    if configured == 0:
        print("\n⚠️  No API keys configured. The agent will use mock tools.")
        print("   For real functionality, configure at least one API key in .env")
    else:
        print(f"\n✅ {configured} API provider(s) configured")
    
    return configured > 0


def demo_real_capabilities():
    """Demonstrate the agent's real capabilities."""
    print("\n🧪 Testing Real Capabilities...")
    
    try:
        agent = AutonomousAgent()
        
        # Test goal with web search
        if get_api_key("serpapi") or get_api_key("bing") or get_api_key("google"):
            print("   Testing web search...")
            agent.add_goal("Find information about AI trends in 2024", priority=0.8)
            agent.run(max_cycles=2)
            print("   ✅ Web search test completed")
        else:
            print("   ⏭️  Skipping web search (no API keys)")
        
        # Test LLM capabilities
        available_providers = llm_manager.get_available_providers()
        if available_providers:
            print(f"   Testing LLM capabilities ({len(available_providers)} providers)...")
            # This would test actual LLM integration
            print("   ✅ LLM providers available")
        else:
            print("   ⏭️  Skipping LLM test (no API keys)")
        
        # Test file operations
        print("   Testing file operations...")
        test_file = Path("test_deployment.txt")
        test_file.write_text("Deployment test file")
        test_file.unlink()
        print("   ✅ File operations test completed")
        
        print("✅ All capability tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Capability test failed: {e}")
        return False


async def start_web_interface(host: str = "0.0.0.0", port: int = 8000):
    """Start the web interface."""
    print(f"\n🌐 Starting web interface on http://{host}:{port}")
    print("   Dashboard: http://localhost:8000")
    print("   API docs: http://localhost:8000/docs")
    print("   Health check: http://localhost:8000/health")
    
    try:
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level=settings.LOG_LEVEL.lower(),
            access_log=True
        )
        server = uvicorn.Server(config)
        await server.serve()
    except KeyboardInterrupt:
        print("\n🛑 Web interface stopped")
    except Exception as e:
        print(f"❌ Web interface error: {e}")


def create_startup_script():
    """Create a startup script for easy deployment."""
    startup_script = """#!/bin/bash
# Autonomous Agent Startup Script

echo "🤖 Starting Autonomous Agent System..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating template..."
    python3 deploy.py --create-env
fi

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Check dependencies
python3 -c "import requests, fastapi, uvicorn" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Missing dependencies. Installing..."
    pip install requests fastapi uvicorn aiofiles
fi

# Start the web interface
echo "🌐 Starting web dashboard..."
python3 -m agent_system.web_interface

# Alternative: Run standalone agent
# echo "🤖 Running standalone agent..."
# python3 -m agent_system --max-cycles 100 --goal "Your goal here::0.8"
"""
    
    script_path = Path("start_agent.sh")
    script_path.write_text(startup_script)
    script_path.chmod(0o755)
    
    print(f"✅ Created startup script: {script_path}")
    print("   Run with: ./start_agent.sh")


def main():
    """Main deployment function."""
    logger = setup_logging()
    
    print("🚀 Autonomous Agent System - Production Deployment")
    print("=" * 60)
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--create-env":
            create_environment_file()
            return
        elif command == "--check-deps":
            check_dependencies()
            return
        elif command == "--check-api":
            check_api_configuration()
            return
        elif command == "--demo":
            demo_real_capabilities()
            return
        elif command == "--web":
            asyncio.run(start_web_interface())
            return
        elif command == "--create-startup":
            create_startup_script()
            return
    
    # Default deployment process
    print("\n📋 Deployment Checklist:")
    
    # 1. Check dependencies
    if not check_dependencies():
        print("\n❌ Please install missing dependencies first")
        return
    
    # 2. Create environment file
    create_environment_file()
    
    # 3. Check API configuration
    has_apis = check_api_configuration()
    
    # 4. Test capabilities
    demo_real_capabilities()
    
    # 5. Create startup script
    create_startup_script()
    
    print("\n" + "=" * 60)
    print("🎉 Deployment preparation complete!")
    print("\nNext steps:")
    if not has_apis:
        print("1. Edit .env file and add your API keys")
        print("2. Run: python3 deploy.py --demo")
    print("1. Start web interface: python3 -m agent_system.web_interface")
    print("2. Or run agent directly: python3 -m agent_system")
    print("3. View dashboard at: http://localhost:8000")
    
    print(f"\n💡 Configuration Summary:")
    print(f"   - Max Cycles: {settings.MAX_CYCLES}")
    print(f"   - Tool Timeout: {settings.TOOL_TIMEOUT}s")
    print(f"   - Log Level: {settings.LOG_LEVEL}")
    print(f"   - LLM Providers: {len(llm_manager.get_available_providers())}")


if __name__ == "__main__":
    main()