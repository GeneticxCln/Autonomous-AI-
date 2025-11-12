# 🔧 Terminal Embedding Guide: Integrate Your Agent Anywhere

**Date**: 2025-11-12  
**Topic**: Embedding Your Agent in Custom Terminal Applications  
**Use Case**: Your terminal, your way!

---

## 🎯 **Embedding Options Available**

Your agent can be embedded in **4 different ways** depending on your terminal design:

### 1. **📦 Library Integration** (Direct Embedding)
### 2. **🌐 API Server** (Network-Based)
### 3. **⚡ Subprocess Call** (Command-Line Integration)
### 4. **🔌 Plugin System** (Extensible Framework)

---

## 📦 **Option 1: Library Integration (Direct Embedding)**

### **Perfect for**: Full integration, custom UIs, advanced control

```python
# In your custom terminal application
from src.agent_system import AutonomousAgent, create_enterprise_system
from src.agent_system.enterprise_integration import EnterpriseIntegrationConfig

class MyCustomTerminal:
    def __init__(self):
        # Initialize the agent directly in your terminal
        self.agent = AutonomousAgent()
        self.is_running = False
        
    def start_agent(self):
        """Start the AI agent as part of your terminal"""
        self.is_running = True
        self.agent.add_goal("Initialize terminal environment", priority=1.0)
        return self.agent
    
    async def process_user_input(self, user_command: str):
        """Process user commands through the agent"""
        if user_command.startswith("agent:"):
            # Forward agent-specific commands
            agent_task = user_command[6:]  # Remove "agent:" prefix
            self.agent.add_goal(agent_task, priority=0.9)
            
            # Run agent cycles
            await self.agent.run_cycle_async()
            
            # Get results
            status = self.agent.get_status()
            return status.get("current_goal", "Processing...")
        else:
            # Handle regular terminal commands
            return self.execute_terminal_command(user_command)
    
    def embed_agent_features(self):
        """Add agent capabilities to your terminal"""
        commands = {
            "debug": self.debug_code,
            "analyze": self.analyze_code, 
            "optimize": self.optimize_code,
            "test": self.generate_tests,
            "explain": self.explain_code,
            "refactor": self.refactor_code
        }
        return commands

# Usage in your terminal
terminal = MyCustomTerminal()
terminal.start_agent()

# Your terminal now has AI superpowers!
```

### **Advanced Library Integration**
```python
# Create a custom terminal with enterprise features
from src.agent_system.enterprise_integration import create_enterprise_system

class EnterpriseTerminal(MyCustomTerminal):
    def __init__(self):
        super().__init__()
        # Add enterprise features for your terminal
        self.enterprise_agent = None
    
    async def initialize_enterprise_features(self):
        """Initialize enterprise-level features"""
        config = EnterpriseIntegrationConfig(
            enable_all_features=False,  # Just the core features
            environment="terminal",
            performance_monitoring=True,
            security_enhanced=True
        )
        self.enterprise_agent = await create_enterprise_system(config)
    
    def add_enterprise_commands(self):
        """Add enterprise-specific commands to your terminal"""
        commands = {
            "security": self.security_scan,
            "performance": self.performance_analysis,
            "compliance": self.compliance_check,
            "monitor": self.start_monitoring
        }
        # Merge with regular commands
        regular_commands = self.embed_agent_features()
        return {**regular_commands, **commands}
```

---

## 🌐 **Option 2: API Server Integration**

### **Perfect for**: Separated architecture, multiple interfaces, language-agnostic

```python
# Your agent already has FastAPI integration!
from src.agent_system.fastapi_app import app
import uvicorn
import requests

class NetworkTerminal:
    def __init__(self, agent_server_url="http://localhost:8000"):
        self.agent_url = agent_server_url
        self.agent_active = False
    
    async def start_agent_server(self):
        """Start the agent API server"""
        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    async def send_agent_command(self, command: str):
        """Send commands to the agent via API"""
        if not self.agent_active:
            await self.start_agent_server()
            self.agent_active = True
        
        # Send command to agent API
        response = requests.post(
            f"{self.agent_url}/api/v1/agents/execute",
            json={
                "command": command,
                "priority": 0.9
            }
        )
        return response.json()
    
    def get_agent_status(self):
        """Get current agent status"""
        response = requests.get(f"{self.agent_url}/api/v1/agents/status")
        return response.json()

# Alternative: Connect to external agent server
class RemoteAgentTerminal:
    def __init__(self, server_url="http://your-agent-server.com"):
        self.agent_url = server_url
    
    def code_assist(self, code: str, request_type: str = "analyze"):
        """Send code to agent for assistance"""
        payload = {
            "code": code,
            "request_type": request_type,  # analyze, debug, optimize, explain
            "language": "python"  # or auto-detect
        }
        
        response = requests.post(
            f"{self.agent_url}/api/v1/assistant/code",
            json=payload
        )
        return response.json()
```

---

## ⚡ **Option 3: Subprocess Integration**

### **Perfect for**: Simple integration, quick setup, backward compatibility

```python
import subprocess
import json
import threading
from typing import Optional

class SubprocessTerminal:
    def __init__(self):
        self.agent_process = None
        self.agent_ready = False
    
    def start_agent_process(self):
        """Start agent as a subprocess"""
        cmd = [
            "python", "-m", "src.agent_system", 
            "--interactive",  # Interactive mode
            "--agent-mode",   # Enable agent features
            "--max-cycles", "10"
        ]
        
        self.agent_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0  # Unbuffered
        )
        
        # Start monitoring thread
        threading.Thread(
            target=self.monitor_agent_output,
            daemon=True
        ).start()
    
    async def agent_call(self, command: str) -> Optional[str]:
        """Call agent via subprocess"""
        if not self.agent_process:
            self.start_agent_process()
        
        # Send command to agent
        self.agent_process.stdin.write(f"{command}\n")
        self.agent_process.stdin.flush()
        
        # Wait for response (simplified)
        line = self.agent_process.stdout.readline()
        return line.strip() if line else None
    
    def monitor_agent_output(self):
        """Monitor agent output in background"""
        while self.agent_process and self.agent_process.poll() is None:
            try:
                line = self.agent_process.stdout.readline()
                if line:
                    print(f"[AGENT] {line.strip()}")
            except:
                break

# Usage in your terminal
terminal = SubprocessTerminal()

# Your terminal can now call the agent!
while True:
    user_input = input("> ")
    
    if user_input.startswith("!"):
        # Agent commands
        response = terminal.agent_call(user_input[1:])
        print(f"Agent: {response}")
    else:
        # Regular terminal commands
        os.system(user_input)
```

---

## 🔌 **Option 4: Plugin System Integration**

### **Perfect for**: Extensible terminals, modular design, third-party plugins

```python
# Your agent has a built-in plugin system!
from src.agent_system.plugin_loader import PluginManager
from src.agent_system.tools import ToolRegistry

class PluginTerminal:
    def __init__(self):
        self.plugin_manager = PluginManager()
        self.tool_registry = ToolRegistry()
        self.agent = AutonomousAgent()
    
    def load_agent_plugins(self):
        """Load agent capabilities as terminal plugins"""
        # Load coding tools as terminal plugins
        coding_plugin = {
            "name": "code_assistant",
            "commands": {
                "debug": self.debug_code_plugin,
                "analyze": self.analyze_code_plugin,
                "optimize": self.optimize_code_plugin,
                "explain": self.explain_code_plugin
            },
            "description": "AI-powered code assistance"
        }
        
        # Load other agent features
        planning_plugin = {
            "name": "task_planner",
            "commands": {
                "plan": self.plan_task_plugin,
                "goal": self.set_goal_plugin,
                "status": self.get_status_plugin
            },
            "description": "Task planning and goal management"
        }
        
        self.plugin_manager.register_plugin(coding_plugin)
        self.plugin_manager.register_plugin(planning_plugin)
    
    async def handle_command(self, command: str, args: list):
        """Handle commands through the plugin system"""
        if command in self.plugin_manager:
            plugin = self.plugin_manager[command]
            return await plugin.execute(args)
        else:
            return self.handle_regular_command(command, args)
    
    async def debug_code_plugin(self, code_file: str):
        """Plugin for code debugging"""
        self.agent.add_goal(f"Debug and fix issues in {code_file}", priority=1.0)
        await self.agent.run_cycle_async()
        return f"Debugged {code_file} - Check output for results"
    
    async def analyze_code_plugin(self, code_file: str):
        """Plugin for code analysis"""
        self.agent.add_goal(f"Analyze code quality in {code_file}", priority=0.8)
        await self.agent.run_cycle_async()
        return f"Analyzed {code_file} - Review suggestions in output"

# Usage in your terminal
terminal = PluginTerminal()
terminal.load_agent_plugins()

# Plugin-based terminal commands:
# terminal> debug my_script.py
# terminal> analyze code_quality.py  
# terminal> plan "refactor this module"
```

---

## 🎨 **Custom Terminal UI Integration**

### **Terminal-Specific Integration Examples**

#### **1. Rich Terminal (Python)**
```python
from rich.console import Console
from rich.panel import Panel
from src.agent_system import AutonomousAgent

class RichAgentTerminal:
    def __init__(self):
        self.console = Console()
        self.agent = AutonomousAgent()
    
    async def display_agent_status(self):
        """Display agent status in a rich panel"""
        status = self.agent.get_status()
        
        panel = Panel(
            f"Current Task: {status.get('current_goal', 'None')}\n"
            f"Active Goals: {len(status.get('active_goals', []))}\n"
            f"Memory Items: {status.get('memory_stats', {}).get('total_memories', 0)}",
            title="🤖 AI Agent Status",
            border_style="blue"
        )
        
        self.console.print(panel)
```

#### **2. Textual Terminal**
```python
from textual.app import App, ComposeResult
from textual.widgets import Input, Static
from src.agent_system import AutonomousAgent

class TextualAgentTerminal(App):
    def __init__(self):
        super().__init__()
        self.agent = AutonomousAgent()
    
    def compose(self) -> ComposeResult:
        yield Static("🤖 AI Agent Terminal", id="header")
        yield Input(placeholder="Enter command...", id="input")
        yield Static("Agent output will appear here", id="output")
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input"""
        command = event.value
        
        if command.startswith("agent:"):
            # Process agent command
            self.agent.add_goal(command[6:], priority=0.9)
            await self.agent.run_cycle_async()
            
            status = self.agent.get_status()
            self.query_one("#output", Static).update(
                f"Agent processed: {command}\n"
                f"Status: {status.get('current_goal', 'Complete')}"
            )
        else:
            # Regular command
            self.query_one("#output", Static).update(
                f"Executed: {command}"
            )
```

#### **3. Custom C++ Terminal**
```cpp
// C++ integration via Python bindings or HTTP API
class CppAgentTerminal {
private:
    std::string agent_server_url = "http://localhost:8000";
    
public:
    void sendAgentCommand(const std::string& command) {
        // Use libcurl or similar to call agent API
        std::string endpoint = agent_server_url + "/api/v1/assistant/command";
        std::string payload = R"({"command": ")" + command + R"("})";
        
        // Make HTTP request to agent
        // Process response and display in terminal
    }
    
    void displayAgentOutput(const std::string& output) {
        std::cout << "\033[1;34m🤖 Agent:\033[0m " << output << std::endl;
    }
};
```

---

## 🚀 **Integration Best Practices**

### **1. Choose Your Integration Method**

| Scenario | Best Method |
|----------|-------------|
| **Full control needed** | Library Integration |
| **Multiple interfaces** | API Server |
| **Quick prototype** | Subprocess |
| **Extensible design** | Plugin System |

### **2. Performance Considerations**

```python
# Optimize for terminal responsiveness
class OptimizedTerminal:
    def __init__(self):
        self.agent = AutonomousAgent()
        self.use_async = True  # Non-blocking operations
    
    async def non_blocking_agent_call(self, command: str):
        """Non-blocking agent calls for responsive terminal"""
        if self.use_async:
            # Run agent operations in background
            asyncio.create_task(self.agent.run_async(max_cycles=5))
        else:
            # Synchronous for simpler use cases
            self.agent.add_goal(command)
            self.agent.run(max_cycles=5)
```

### **3. Error Handling**

```python
class RobustTerminal:
    def __init__(self):
        self.agent = AutonomousAgent()
        self.fallback_mode = False
    
    async def safe_agent_call(self, command: str):
        """Safe agent calls with fallback"""
        try:
            self.agent.add_goal(command, priority=0.9)
            await self.agent.run_cycle_async()
            return True
        except Exception as e:
            print(f"Agent error: {e}")
            self.fallback_mode = True
            return False
    
    def fallback_command_handler(self, command: str):
        """Fallback when agent is unavailable"""
        if self.fallback_mode:
            # Use basic shell commands or local processing
            return f"Fallback: {command}"
```

---

## 🎯 **Quick Start Templates**

### **Minimal Integration (5 minutes)**
```python
from src.agent_system import AutonomousAgent

class QuickTerminal:
    def __init__(self):
        self.agent = AutonomousAgent()
    
    def agent_help(self):
        return "Commands: agent:debug, agent:analyze, agent:optimize"
    
    async def process(self, command: str):
        if command.startswith("agent:"):
            self.agent.add_goal(command[6:])
            await self.agent.run_cycle_async()
            return "Agent processed your request"
        return f"Regular command: {command}"

# Use it!
terminal = QuickTerminal()
# terminal> agent:debug my_script.py
# terminal> Regular bash command here
```

### **Complete Integration (30 minutes)**
```python
# See the full examples above for complete implementation
# Choose your preferred method (Library, API, Subprocess, or Plugin)
```

---

## 🔧 **Debugging Your Integration**

### **Common Issues & Solutions**

#### **1. Import Errors**
```python
# Solution: Ensure proper Python path
import sys
sys.path.append('/path/to/your/agent/project')

from src.agent_system import AutonomousAgent
```

#### **2. Async/Sync Conflicts**
```python
# Solution: Match your terminal's async model
# If your terminal is async:
await self.agent.run_async()
# If your terminal is sync:
self.agent.run()
```

#### **3. Performance Issues**
```python
# Solution: Use lighter configurations for terminals
light_agent = AutonomousAgent()
light_agent.max_concurrent_goals = 1  # Reduce concurrency
```

---

## 🎉 **Your Terminal, Supercharged!**

Your agent is **perfectly designed for embedding** in any custom terminal! 

**Choose your integration method**, follow the examples, and **your terminal will have AI superpowers!**

---

**Ready to embed? Pick your method and start coding! 🚀💻**
**Date**: 2025-11-12  
**Topic**: Embedding Your Agent in Custom Terminal Applications  
**Use Case**: Your terminal, your way!

---

## 🎯 **Embedding Options Available**

Your agent can be embedded in **4 different ways** depending on your terminal design:

### 1. **📦 Library Integration** (Direct Embedding)
### 2. **🌐 API Server** (Network-Based)
### 3. **⚡ Subprocess Call** (Command-Line Integration)
### 4. **🔌 Plugin System** (Extensible Framework)

---

## 📦 **Option 1: Library Integration (Direct Embedding)**

### **Perfect for**: Full integration, custom UIs, advanced control

```python
# In your custom terminal application
from src.agent_system import AutonomousAgent, create_enterprise_system
from src.agent_system.enterprise_integration import EnterpriseIntegrationConfig

class MyCustomTerminal:
    def __init__(self):
        # Initialize the agent directly in your terminal
        self.agent = AutonomousAgent()
        self.is_running = False
        
    def start_agent(self):
        """Start the AI agent as part of your terminal"""
        self.is_running = True
        self.agent.add_goal("Initialize terminal environment", priority=1.0)
        return self.agent
    
    async def process_user_input(self, user_command: str):
        """Process user commands through the agent"""
        if user_command.startswith("agent:"):
            # Forward agent-specific commands
            agent_task = user_command[6:]  # Remove "agent:" prefix
            self.agent.add_goal(agent_task, priority=0.9)
            
            # Run agent cycles
            await self.agent.run_cycle_async()
            
            # Get results
            status = self.agent.get_status()
            return status.get("current_goal", "Processing...")
        else:
            # Handle regular terminal commands
            return self.execute_terminal_command(user_command)
    
    def embed_agent_features(self):
        """Add agent capabilities to your terminal"""
        commands = {
            "debug": self.debug_code,
            "analyze": self.analyze_code, 
            "optimize": self.optimize_code,
            "test": self.generate_tests,
            "explain": self.explain_code,
            "refactor": self.refactor_code
        }
        return commands

# Usage in your terminal
terminal = MyCustomTerminal()
terminal.start_agent()

# Your terminal now has AI superpowers!
```

### **Advanced Library Integration**
```python
# Create a custom terminal with enterprise features
from src.agent_system.enterprise_integration import create_enterprise_system

class EnterpriseTerminal(MyCustomTerminal):
    def __init__(self):
        super().__init__()
        # Add enterprise features for your terminal
        self.enterprise_agent = None
    
    async def initialize_enterprise_features(self):
        """Initialize enterprise-level features"""
        config = EnterpriseIntegrationConfig(
            enable_all_features=False,  # Just the core features
            environment="terminal",
            performance_monitoring=True,
            security_enhanced=True
        )
        self.enterprise_agent = await create_enterprise_system(config)
    
    def add_enterprise_commands(self):
        """Add enterprise-specific commands to your terminal"""
        commands = {
            "security": self.security_scan,
            "performance": self.performance_analysis,
            "compliance": self.compliance_check,
            "monitor": self.start_monitoring
        }
        # Merge with regular commands
        regular_commands = self.embed_agent_features()
        return {**regular_commands, **commands}
```

---

## 🌐 **Option 2: API Server Integration**

### **Perfect for**: Separated architecture, multiple interfaces, language-agnostic

```python
# Your agent already has FastAPI integration!
from src.agent_system.fastapi_app import app
import uvicorn
import requests

class NetworkTerminal:
    def __init__(self, agent_server_url="http://localhost:8000"):
        self.agent_url = agent_server_url
        self.agent_active = False
    
    async def start_agent_server(self):
        """Start the agent API server"""
        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    async def send_agent_command(self, command: str):
        """Send commands to the agent via API"""
        if not self.agent_active:
            await self.start_agent_server()
            self.agent_active = True
        
        # Send command to agent API
        response = requests.post(
            f"{self.agent_url}/api/v1/agents/execute",
            json={
                "command": command,
                "priority": 0.9
            }
        )
        return response.json()
    
    def get_agent_status(self):
        """Get current agent status"""
        response = requests.get(f"{self.agent_url}/api/v1/agents/status")
        return response.json()

# Alternative: Connect to external agent server
class RemoteAgentTerminal:
    def __init__(self, server_url="http://your-agent-server.com"):
        self.agent_url = server_url
    
    def code_assist(self, code: str, request_type: str = "analyze"):
        """Send code to agent for assistance"""
        payload = {
            "code": code,
            "request_type": request_type,  # analyze, debug, optimize, explain
            "language": "python"  # or auto-detect
        }
        
        response = requests.post(
            f"{self.agent_url}/api/v1/assistant/code",
            json=payload
        )
        return response.json()
```

---

## ⚡ **Option 3: Subprocess Integration**

### **Perfect for**: Simple integration, quick setup, backward compatibility

```python
import subprocess
import json
import threading
from typing import Optional

class SubprocessTerminal:
    def __init__(self):
        self.agent_process = None
        self.agent_ready = False
    
    def start_agent_process(self):
        """Start agent as a subprocess"""
        cmd = [
            "python", "-m", "src.agent_system", 
            "--interactive",  # Interactive mode
            "--agent-mode",   # Enable agent features
            "--max-cycles", "10"
        ]
        
        self.agent_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0  # Unbuffered
        )
        
        # Start monitoring thread
        threading.Thread(
            target=self.monitor_agent_output,
            daemon=True
        ).start()
    
    async def agent_call(self, command: str) -> Optional[str]:
        """Call agent via subprocess"""
        if not self.agent_process:
            self.start_agent_process()
        
        # Send command to agent
        self.agent_process.stdin.write(f"{command}\n")
        self.agent_process.stdin.flush()
        
        # Wait for response (simplified)
        line = self.agent_process.stdout.readline()
        return line.strip() if line else None
    
    def monitor_agent_output(self):
        """Monitor agent output in background"""
        while self.agent_process and self.agent_process.poll() is None:
            try:
                line = self.agent_process.stdout.readline()
                if line:
                    print(f"[AGENT] {line.strip()}")
            except:
                break

# Usage in your terminal
terminal = SubprocessTerminal()

# Your terminal can now call the agent!
while True:
    user_input = input("> ")
    
    if user_input.startswith("!"):
        # Agent commands
        response = terminal.agent_call(user_input[1:])
        print(f"Agent: {response}")
    else:
        # Regular terminal commands
        os.system(user_input)
```

---

## 🔌 **Option 4: Plugin System Integration**

### **Perfect for**: Extensible terminals, modular design, third-party plugins

```python
# Your agent has a built-in plugin system!
from src.agent_system.plugin_loader import PluginManager
from src.agent_system.tools import ToolRegistry

class PluginTerminal:
    def __init__(self):
        self.plugin_manager = PluginManager()
        self.tool_registry = ToolRegistry()
        self.agent = AutonomousAgent()
    
    def load_agent_plugins(self):
        """Load agent capabilities as terminal plugins"""
        # Load coding tools as terminal plugins
        coding_plugin = {
            "name": "code_assistant",
            "commands": {
                "debug": self.debug_code_plugin,
                "analyze": self.analyze_code_plugin,
                "optimize": self.optimize_code_plugin,
                "explain": self.explain_code_plugin
            },
            "description": "AI-powered code assistance"
        }
        
        # Load other agent features
        planning_plugin = {
            "name": "task_planner",
            "commands": {
                "plan": self.plan_task_plugin,
                "goal": self.set_goal_plugin,
                "status": self.get_status_plugin
            },
            "description": "Task planning and goal management"
        }
        
        self.plugin_manager.register_plugin(coding_plugin)
        self.plugin_manager.register_plugin(planning_plugin)
    
    async def handle_command(self, command: str, args: list):
        """Handle commands through the plugin system"""
        if command in self.plugin_manager:
            plugin = self.plugin_manager[command]
            return await plugin.execute(args)
        else:
            return self.handle_regular_command(command, args)
    
    async def debug_code_plugin(self, code_file: str):
        """Plugin for code debugging"""
        self.agent.add_goal(f"Debug and fix issues in {code_file}", priority=1.0)
        await self.agent.run_cycle_async()
        return f"Debugged {code_file} - Check output for results"
    
    async def analyze_code_plugin(self, code_file: str):
        """Plugin for code analysis"""
        self.agent.add_goal(f"Analyze code quality in {code_file}", priority=0.8)
        await self.agent.run_cycle_async()
        return f"Analyzed {code_file} - Review suggestions in output"

# Usage in your terminal
terminal = PluginTerminal()
terminal.load_agent_plugins()

# Plugin-based terminal commands:
# terminal> debug my_script.py
# terminal> analyze code_quality.py  
# terminal> plan "refactor this module"
```

---

## 🎨 **Custom Terminal UI Integration**

### **Terminal-Specific Integration Examples**

#### **1. Rich Terminal (Python)**
```python
from rich.console import Console
from rich.panel import Panel
from src.agent_system import AutonomousAgent

class RichAgentTerminal:
    def __init__(self):
        self.console = Console()
        self.agent = AutonomousAgent()
    
    async def display_agent_status(self):
        """Display agent status in a rich panel"""
        status = self.agent.get_status()
        
        panel = Panel(
            f"Current Task: {status.get('current_goal', 'None')}\n"
            f"Active Goals: {len(status.get('active_goals', []))}\n"
            f"Memory Items: {status.get('memory_stats', {}).get('total_memories', 0)}",
            title="🤖 AI Agent Status",
            border_style="blue"
        )
        
        self.console.print(panel)
```

#### **2. Textual Terminal**
```python
from textual.app import App, ComposeResult
from textual.widgets import Input, Static
from src.agent_system import AutonomousAgent

class TextualAgentTerminal(App):
    def __init__(self):
        super().__init__()
        self.agent = AutonomousAgent()
    
    def compose(self) -> ComposeResult:
        yield Static("🤖 AI Agent Terminal", id="header")
        yield Input(placeholder="Enter command...", id="input")
        yield Static("Agent output will appear here", id="output")
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input"""
        command = event.value
        
        if command.startswith("agent:"):
            # Process agent command
            self.agent.add_goal(command[6:], priority=0.9)
            await self.agent.run_cycle_async()
            
            status = self.agent.get_status()
            self.query_one("#output", Static).update(
                f"Agent processed: {command}\n"
                f"Status: {status.get('current_goal', 'Complete')}"
            )
        else:
            # Regular command
            self.query_one("#output", Static).update(
                f"Executed: {command}"
            )
```

#### **3. Custom C++ Terminal**
```cpp
// C++ integration via Python bindings or HTTP API
class CppAgentTerminal {
private:
    std::string agent_server_url = "http://localhost:8000";
    
public:
    void sendAgentCommand(const std::string& command) {
        // Use libcurl or similar to call agent API
        std::string endpoint = agent_server_url + "/api/v1/assistant/command";
        std::string payload = R"({"command": ")" + command + R"("})";
        
        // Make HTTP request to agent
        // Process response and display in terminal
    }
    
    void displayAgentOutput(const std::string& output) {
        std::cout << "\033[1;34m🤖 Agent:\033[0m " << output << std::endl;
    }
};
```

---

## 🚀 **Integration Best Practices**

### **1. Choose Your Integration Method**

| Scenario | Best Method |
|----------|-------------|
| **Full control needed** | Library Integration |
| **Multiple interfaces** | API Server |
| **Quick prototype** | Subprocess |
| **Extensible design** | Plugin System |

### **2. Performance Considerations**

```python
# Optimize for terminal responsiveness
class OptimizedTerminal:
    def __init__(self):
        self.agent = AutonomousAgent()
        self.use_async = True  # Non-blocking operations
    
    async def non_blocking_agent_call(self, command: str):
        """Non-blocking agent calls for responsive terminal"""
        if self.use_async:
            # Run agent operations in background
            asyncio.create_task(self.agent.run_async(max_cycles=5))
        else:
            # Synchronous for simpler use cases
            self.agent.add_goal(command)
            self.agent.run(max_cycles=5)
```

### **3. Error Handling**

```python
class RobustTerminal:
    def __init__(self):
        self.agent = AutonomousAgent()
        self.fallback_mode = False
    
    async def safe_agent_call(self, command: str):
        """Safe agent calls with fallback"""
        try:
            self.agent.add_goal(command, priority=0.9)
            await self.agent.run_cycle_async()
            return True
        except Exception as e:
            print(f"Agent error: {e}")
            self.fallback_mode = True
            return False
    
    def fallback_command_handler(self, command: str):
        """Fallback when agent is unavailable"""
        if self.fallback_mode:
            # Use basic shell commands or local processing
            return f"Fallback: {command}"
```

---

## 🎯 **Quick Start Templates**

### **Minimal Integration (5 minutes)**
```python
from src.agent_system import AutonomousAgent

class QuickTerminal:
    def __init__(self):
        self.agent = AutonomousAgent()
    
    def agent_help(self):
        return "Commands: agent:debug, agent:analyze, agent:optimize"
    
    async def process(self, command: str):
        if command.startswith("agent:"):
            self.agent.add_goal(command[6:])
            await self.agent.run_cycle_async()
            return "Agent processed your request"
        return f"Regular command: {command}"

# Use it!
terminal = QuickTerminal()
# terminal> agent:debug my_script.py
# terminal> Regular bash command here
```

### **Complete Integration (30 minutes)**
```python
# See the full examples above for complete implementation
# Choose your preferred method (Library, API, Subprocess, or Plugin)
```

---

## 🔧 **Debugging Your Integration**

### **Common Issues & Solutions**

#### **1. Import Errors**
```python
# Solution: Ensure proper Python path
import sys
sys.path.append('/path/to/your/agent/project')

from src.agent_system import AutonomousAgent
```

#### **2. Async/Sync Conflicts**
```python
# Solution: Match your terminal's async model
# If your terminal is async:
await self.agent.run_async()
# If your terminal is sync:
self.agent.run()
```

#### **3. Performance Issues**
```python
# Solution: Use lighter configurations for terminals
light_agent = AutonomousAgent()
light_agent.max_concurrent_goals = 1  # Reduce concurrency
```

---

## 🎉 **Your Terminal, Supercharged!**

Your agent is **perfectly designed for embedding** in any custom terminal! 

**Choose your integration method**, follow the examples, and **your terminal will have AI superpowers!**

---

**Ready to embed? Pick your method and start coding! 🚀💻**
