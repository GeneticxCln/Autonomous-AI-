"""
FastAPI web interface for the autonomous agent.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import AutonomousAgent
from .llm_integration import llm_manager

logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Autonomous Agent System",
    description="A web interface for managing and monitoring the autonomous agent",
    version="2.0.0",
)

# Global agent instance
agent: Optional[AutonomousAgent] = None
agent_lock = asyncio.Lock()


# Pydantic models for API
class GoalRequest(BaseModel):
    description: str = Field(..., description="Goal description")
    priority: float = Field(0.5, ge=0.0, le=1.0, description="Goal priority (0.0-1.0)")
    constraints: Optional[Dict[str, Any]] = Field(default=None, description="Goal constraints")


class AgentStatusResponse(BaseModel):
    current_goal: Optional[str]
    goals: Dict[str, Any]
    memory_stats: Dict[str, Any]
    tool_stats: Dict[str, Any]
    learning_stats: Dict[str, Any]
    is_running: bool
    llm_providers: List[str]


class ActionRequest(BaseModel):
    action: str = Field(..., description="Action to perform")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")


# Mount static files
if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main dashboard page."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autonomous Agent Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .btn { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #0056b3; }
        .btn:disabled { background: #ccc; cursor: not-allowed; }
        .status { padding: 10px; border-radius: 4px; margin: 5px 0; }
        .status.running { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
        .status.stopped { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
        .progress-bar { width: 100%; height: 20px; background: #e9ecef; border-radius: 10px; overflow: hidden; }
        .progress-fill { height: 100%; background: #28a745; transition: width 0.3s ease; }
        .json-display { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 10px; font-family: monospace; font-size: 12px; max-height: 400px; overflow-y: auto; }
        .input-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, textarea, select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        .loading { opacity: 0.6; pointer-events: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Autonomous Agent Dashboard</h1>
            <p>Manage and monitor your AI agent system</p>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Agent Control</h3>
                <div class="status" id="agentStatus">Checking status...</div>
                <button class="btn" onclick="startAgent()">Start Agent</button>
                <button class="btn" onclick="stopAgent()">Stop Agent</button>
                <button class="btn" onclick="refreshStatus()">Refresh Status</button>
            </div>

            <div class="card">
                <h3>LLM Providers</h3>
                <div id="llmProviders">Loading...</div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Add Goal</h3>
                <div class="input-group">
                    <label for="goalDescription">Goal Description:</label>
                    <textarea id="goalDescription" placeholder="Enter goal description..." rows="3"></textarea>
                </div>
                <div class="input-group">
                    <label for="goalPriority">Priority (0.0 - 1.0):</label>
                    <input type="number" id="goalPriority" min="0" max="1" step="0.1" value="0.5">
                </div>
                <button class="btn" onclick="addGoal()">Add Goal</button>
            </div>

            <div class="card">
                <h3>Current Progress</h3>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                </div>
                <div id="currentGoal">No active goal</div>
            </div>
        </div>

        <div class="card">
            <h3>Agent Status Details</h3>
            <div class="json-display" id="statusDetails">Click refresh to load status...</div>
        </div>

        <div class="card">
            <h3>Logs</h3>
            <div class="json-display" id="logs">Ready...</div>
        </div>
    </div>

    <script>
        let agentRunning = false;
        let refreshInterval;

        async function refreshStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                updateStatus(data);
            } catch (error) {
                console.error('Failed to refresh status:', error);
                document.getElementById('statusDetails').textContent = 'Error loading status: ' + error.message;
            }
        }

        function updateStatus(data) {
            // Update agent status
            const statusElement = document.getElementById('agentStatus');
            agentRunning = data.is_running;
            statusElement.textContent = agentRunning ? 'Running' : 'Stopped';
            statusElement.className = 'status ' + (agentRunning ? 'running' : 'stopped');

            // Update current goal
            const currentGoalElement = document.getElementById('currentGoal');
            if (data.current_goal) {
                currentGoalElement.innerHTML = `
                    <strong>Current Goal:</strong> ${data.current_goal}<br>
                    <strong>Progress:</strong> ${(data.goals.goals[0]?.progress * 100 || 0).toFixed(1)}%
                `;
                document.getElementById('progressFill').style.width = (data.goals.goals[0]?.progress * 100 || 0) + '%';
            } else {
                currentGoalElement.textContent = 'No active goal';
                document.getElementById('progressFill').style.width = '0%';
            }

            // Update LLM providers
            document.getElementById('llmProviders').innerHTML = 
                '<strong>Available:</strong> ' + data.llm_providers.join(', ');

            // Update detailed status
            document.getElementById('statusDetails').textContent = JSON.stringify(data, null, 2);
        }

        async function startAgent() {
            if (agentRunning) return;
            
            try {
                document.body.classList.add('loading');
                const response = await fetch('/api/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ max_cycles: 10 })
                });
                
                if (response.ok) {
                    logMessage('Agent started successfully');
                    refreshStatus();
                } else {
                    throw new Error('Failed to start agent');
                }
            } catch (error) {
                logMessage('Error starting agent: ' + error.message);
            } finally {
                document.body.classList.remove('loading');
            }
        }

        async function stopAgent() {
            if (!agentRunning) return;
            
            try {
                const response = await fetch('/api/stop', { method: 'POST' });
                if (response.ok) {
                    logMessage('Agent stopped');
                    refreshStatus();
                }
            } catch (error) {
                logMessage('Error stopping agent: ' + error.message);
            }
        }

        async function addGoal() {
            const description = document.getElementById('goalDescription').value.trim();
            const priority = parseFloat(document.getElementById('goalPriority').value);
            
            if (!description) {
                alert('Please enter a goal description');
                return;
            }

            try {
                const response = await fetch('/api/goals', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ description, priority })
                });
                
                if (response.ok) {
                    logMessage('Goal added successfully');
                    document.getElementById('goalDescription').value = '';
                    refreshStatus();
                }
            } catch (error) {
                logMessage('Error adding goal: ' + error.message);
            }
        }

        function logMessage(message) {
            const logElement = document.getElementById('logs');
            const timestamp = new Date().toLocaleTimeString();
            logElement.textContent = `[${timestamp}] ${message}\n` + logElement.textContent;
        }

        // Auto-refresh status every 5 seconds
        function startAutoRefresh() {
            refreshInterval = setInterval(refreshStatus, 5000);
        }

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            refreshStatus();
            startAutoRefresh();
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.get("/api/status", response_model=AgentStatusResponse)
async def get_status():
    """Get current agent status."""
    async with agent_lock:
        if agent is None:
            raise HTTPException(status_code=503, detail="Agent not initialized")

        try:
            status = agent.get_status()
            status["llm_providers"] = llm_manager.get_available_providers()
            return AgentStatusResponse(**status)
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/start")
async def start_agent(background_tasks: BackgroundTasks, max_cycles: int = 10):
    """Start the agent."""
    async with agent_lock:
        global agent
        if agent is None:
            agent = AutonomousAgent()

        if agent.is_running:
            return JSONResponse(content={"message": "Agent is already running"}, status_code=200)

        # Start agent in background
        background_tasks.add_task(run_agent_background, agent, max_cycles)
        return JSONResponse(content={"message": "Agent started"}, status_code=200)


@app.post("/api/stop")
async def stop_agent():
    """Stop the agent."""
    async with agent_lock:
        global agent
        if agent is None:
            raise HTTPException(status_code=503, detail="Agent not initialized")

        if not agent.is_running:
            return JSONResponse(content={"message": "Agent is not running"}, status_code=200)

        agent.stop()
        return JSONResponse(content={"message": "Agent stopped"}, status_code=200)


@app.post("/api/goals")
async def add_goal_api(goal_request: GoalRequest):
    """Add a new goal."""
    async with agent_lock:
        global agent
        if agent is None:
            agent = AutonomousAgent()

        try:
            goal = agent.add_goal(
                description=goal_request.description,
                priority=goal_request.priority,
                constraints=goal_request.constraints,
            )
            return JSONResponse(
                content={
                    "message": "Goal added successfully",
                    "goal_id": goal.id,
                    "description": goal.description,
                },
                status_code=200,
            )
        except Exception as e:
            logger.error(f"Error adding goal: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/goals")
async def get_goals():
    """Get all goals."""
    async with agent_lock:
        if agent is None:
            return JSONResponse(content={"goals": []}, status_code=200)

        try:
            status = agent.get_status()
            return JSONResponse(content=status["goals"], status_code=200)
        except Exception as e:
            logger.error(f"Error getting goals: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, action_request: ActionRequest):
    """Execute a specific tool."""
    async with agent_lock:
        if agent is None:
            raise HTTPException(status_code=503, detail="Agent not initialized")

        try:
            # This would need to be implemented based on your tool structure
            return JSONResponse(
                content={
                    "message": f"Tool {tool_name} execution requested",
                    "action": action_request.action,
                    "parameters": action_request.parameters,
                },
                status_code=200,
            )
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/llm/providers")
async def get_llm_providers():
    """Get available LLM providers."""
    return JSONResponse(
        content={
            "providers": llm_manager.get_available_providers(),
            "available": {name: llm_manager.is_available(name) for name in llm_manager.providers},
        },
        status_code=200,
    )


async def run_agent_background(agent_instance: AutonomousAgent, max_cycles: int):
    """Run agent in background task."""
    try:
        logger.info(f"Starting agent background task with {max_cycles} cycles")
        agent_instance.run(max_cycles=max_cycles)
        logger.info("Agent background task completed")
    except Exception as e:
        logger.error(f"Agent background task failed: {e}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        content={
            "status": "healthy",
            "agent_initialized": agent is not None,
            "llm_providers": len(llm_manager.get_available_providers()),
        },
        status_code=200,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
