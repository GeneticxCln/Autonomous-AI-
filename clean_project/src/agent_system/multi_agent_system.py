"""
Multi-Agent Collaboration Framework
Orchestrates multiple AI agents working together with specialized roles and communication
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, List, Optional, Union, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import queue
import threading

from .config_simple import settings
from .distributed_message_queue import distributed_message_queue, MessagePriority
from .distributed_state_manager import distributed_state_manager
from .infrastructure_manager import infrastructure_manager

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Specialized roles in multi-agent system."""
    PLANNER = "planner"           # Breaks down complex tasks
    EXECUTOR = "executor"         # Performs specific actions
    CHECKER = "checker"          # Validates and quality checks
    COORDINATOR = "coordinator"   # Manages overall workflow
    RESEARCHER = "researcher"     # Gathers information
    ANALYST = "analyst"          # Analyzes data and patterns
    WRITER = "writer"            # Creates content and documentation
    REVISER = "revisor"          # Reviews and improves outputs


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEWED = "reviewed"
    APPROVED = "approved"


class MessageType(Enum):
    """Types of messages in agent communication."""
    TASK_ASSIGNMENT = "task_assignment"
    TASK_COMPLETION = "task_completion"
    STATUS_UPDATE = "status_update"
    REQUEST_HELP = "request_help"
    SHARE_RESULTS = "share_results"
    QUALITY_CHECK = "quality_check"
    COORDINATION = "coordination"


@dataclass
class AgentCapability:
    """Defines what an agent can do."""
    name: str
    description: str
    input_types: List[str] = field(default_factory=list)
    output_types: List[str] = field(default_factory=list)
    complexity_level: str = "medium"  # low, medium, high, expert
    estimated_duration: int = 300  # seconds
    quality_requirements: List[str] = field(default_factory=list)


@dataclass
class AgentIdentity:
    """Unique agent identity and capabilities."""
    agent_id: str
    name: str
    role: AgentRole
    capabilities: List[AgentCapability]
    expertise_domains: List[str]
    max_concurrent_tasks: int = 3
    communication_style: str = "professional"
    quality_standards: List[str] = field(default_factory=list)


@dataclass
class Task:
    """Task definition for agent execution."""
    task_id: str
    title: str
    description: str
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5  # 1-10 scale
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    dependencies: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    quality_score: Optional[float] = None
    feedback: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class AgentMessage:
    """Message for inter-agent communication."""
    message_id: str
    from_agent: str
    to_agent: Optional[str] = None
    message_type: MessageType = MessageType.STATUS_UPDATE
    task_id: Optional[str] = None
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 5
    requires_response: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_transport_dict(self) -> Dict[str, Any]:
        """Serialize message for distributed transport."""
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type.value,
            "task_id": self.task_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority,
            "requires_response": self.requires_response,
            "metadata": self.metadata,
        }

    @classmethod
    def from_transport_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Rehydrate message from distributed transport."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                timestamp = datetime.now()
        message_type_value = data.get("message_type", MessageType.STATUS_UPDATE.value)
        message_type = (
            message_type_value
            if isinstance(message_type_value, MessageType)
            else MessageType(message_type_value)
        )
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            from_agent=data.get("from_agent", "unknown"),
            to_agent=data.get("to_agent"),
            message_type=message_type,
            task_id=data.get("task_id"),
            content=data.get("content", {}),
            timestamp=timestamp or datetime.now(),
            priority=int(data.get("priority", 5)),
            requires_response=bool(data.get("requires_response", False)),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorkflowStep:
    """Individual step in a complex workflow."""
    step_id: str
    step_name: str
    assigned_agent: str
    task: Task
    status: TaskStatus = TaskStatus.PENDING
    order: int = 0
    parallel_group: Optional[int] = None  # Steps that can run in parallel


class AgentRegistry:
    """Registry of available agents and their capabilities."""

    def __init__(self):
        self.agents: Dict[str, AgentIdentity] = {}
        self.role_to_agents: Dict[AgentRole, List[str]] = {}
        self._initialize_default_agents()

    def _initialize_default_agents(self):
        """Initialize with default agent profiles."""
        default_agents = [
            AgentIdentity(
                agent_id="planner_alpha",
                name="Task Planner Alpha",
                role=AgentRole.PLANNER,
                capabilities=[
                    AgentCapability("task_decomposition", "Break down complex tasks into manageable steps"),
                    AgentCapability("workflow_design", "Create efficient task workflows"),
                    AgentCapability("resource_planning", "Estimate resource requirements and timelines")
                ],
                expertise_domains=["project_management", "task_analysis", "workflow_optimization"],
                quality_standards=["clear_task_breakdown", "realistic_estimates", "logical_flow"]
            ),
            AgentIdentity(
                agent_id="executor_beta",
                name="Task Executor Beta",
                role=AgentRole.EXECUTOR,
                capabilities=[
                    AgentCapability("data_processing", "Process and analyze data efficiently"),
                    AgentCapability("content_generation", "Create high-quality content"),
                    AgentCapability("automation", "Automate repetitive tasks")
                ],
                expertise_domains=["content_creation", "data_analysis", "process_automation"],
                quality_standards=["accuracy", "completeness", "timeliness"]
            ),
            AgentIdentity(
                agent_id="checker_gamma",
                name="Quality Checker Gamma",
                role=AgentRole.CHECKER,
                capabilities=[
                    AgentCapability("quality_assessment", "Evaluate output quality against standards"),
                    AgentCapability("error_detection", "Identify errors and inconsistencies"),
                    AgentCapability("compliance_checking", "Ensure outputs meet requirements")
                ],
                expertise_domains=["quality_assurance", "error_detection", "compliance"],
                quality_standards=["accuracy", "completeness", "standards_compliance"]
            ),
            AgentIdentity(
                agent_id="researcher_delta",
                name="Research Specialist Delta",
                role=AgentRole.RESEARCHER,
                capabilities=[
                    AgentCapability("information_gathering", "Collect relevant information efficiently"),
                    AgentCapability("source_verification", "Verify information accuracy and reliability"),
                    AgentCapability("synthesis", "Combine information from multiple sources")
                ],
                expertise_domains=["research", "information_gathering", "analysis"],
                quality_standards=["source_reliability", "information_accuracy", "comprehensive_coverage"]
            ),
            AgentIdentity(
                agent_id="coordinator_epsilon",
                name="Workflow Coordinator Epsilon",
                role=AgentRole.COORDINATOR,
                capabilities=[
                    AgentCapability("task_coordination", "Coordinate multiple agents and tasks"),
                    AgentCapability("resource_allocation", "Optimize resource allocation"),
                    AgentCapability("progress_monitoring", "Track and report on workflow progress")
                ],
                expertise_domains=["project_management", "resource_optimization", "coordination"],
                quality_standards=["efficient_coordination", "optimal_resource_use", "clear_communication"]
            )
        ]

        for agent in default_agents:
            self.register_agent(agent)

    def register_agent(self, agent: AgentIdentity):
        """Register a new agent."""
        self.agents[agent.agent_id] = agent
        if agent.role not in self.role_to_agents:
            self.role_to_agents[agent.role] = []
        self.role_to_agents[agent.role].append(agent.agent_id)
        logger.info(f"Registered agent: {agent.name} ({agent.role.value})")

    def get_agent(self, agent_id: str) -> Optional[AgentIdentity]:
        """Get agent by ID."""
        return self.agents.get(agent_id)

    def get_agents_by_role(self, role: AgentRole) -> List[AgentIdentity]:
        """Get all agents with a specific role."""
        agent_ids = self.role_to_agents.get(role, [])
        return [self.agents[aid] for aid in agent_ids if aid in self.agents]

    def find_best_agent(self, capability_needed: str, context: Dict[str, Any]) -> Optional[AgentIdentity]:
        """Find the best agent for a specific capability."""
        best_agent = None
        best_score = 0

        for agent in self.agents.values():
            score = self._calculate_agent_score(agent, capability_needed, context)
            if score > best_score:
                best_score = score
                best_agent = agent

        return best_agent if best_score > 0.3 else None

    def _calculate_agent_score(self, agent: AgentIdentity, capability: str, context: Dict[str, Any]) -> float:
        """Calculate how well an agent fits the context."""
        score = 0.0

        # Capability match
        for cap in agent.capabilities:
            if capability.lower() in cap.name.lower() or capability.lower() in cap.description.lower():
                score += 0.4

        # Domain expertise match
        for domain in agent.expertise_domains:
            if any(keyword in domain.lower() for keyword in context.get("keywords", [])):
                score += 0.2

        # Current workload (simulated)
        score += 0.2  # Would factor in actual workload in real implementation

        # Quality standards alignment
        for standard in agent.quality_standards:
            if standard in context.get("quality_requirements", []):
                score += 0.2

        return min(score, 1.0)


class MessageBus:
    """Asynchronous message bus for agent communication."""

    def __init__(
        self,
        *,
        use_distributed_backend: bool = False,
        cluster_queue_name: str = "multi-agent-messages",
    ):
        self.message_queue = asyncio.Queue()
        self.subscribers: Dict[str, List[Callable]] = {}
        self.running = False
        self.distributed_enabled = use_distributed_backend and getattr(
            settings, "DISTRIBUTED_ENABLED", False
        )
        self.cluster_queue_name = cluster_queue_name
        self.node_id = getattr(settings, "DISTRIBUTED_NODE_ID", "local-node")
        self._distributed_consumer_task: Optional[asyncio.Task] = None
        self._local_processor_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the message bus."""
        self.running = True
        self._local_processor_task = asyncio.create_task(self._message_processor())
        if self.distributed_enabled:
            await distributed_message_queue.initialize()
            self._distributed_consumer_task = asyncio.create_task(self._distributed_consumer())
        logger.info("Message bus started (distributed=%s)", self.distributed_enabled)

    async def stop(self):
        """Stop the message bus."""
        self.running = False

        if self._distributed_consumer_task:
            self._distributed_consumer_task.cancel()
            try:
                await self._distributed_consumer_task
            except asyncio.CancelledError:
                pass

        if self._local_processor_task:
            self._local_processor_task.cancel()
            try:
                await self._local_processor_task
            except asyncio.CancelledError:
                pass

        logger.info("Message bus stopped")

    async def send_message(self, message: AgentMessage):
        """Send a message to the bus."""
        await self.message_queue.put(message)

        if self.distributed_enabled:
            message.metadata.setdefault("origin_node", self.node_id)
            message.metadata.setdefault(
                "cluster", getattr(settings, "DISTRIBUTED_CLUSTER_NAME", "agent-cluster")
            )
            await distributed_message_queue.publish(
                self.cluster_queue_name,
                message.to_transport_dict(),
                priority=self._priority_from_message(message),
            )

        logger.debug(
            "Message sent: %s from %s (distributed=%s)",
            message.message_type.value,
            message.from_agent,
            self.distributed_enabled,
        )

    def subscribe(self, agent_id: str, callback: Callable):
        """Subscribe to messages for an agent."""
        if agent_id not in self.subscribers:
            self.subscribers[agent_id] = []
        self.subscribers[agent_id].append(callback)

    async def _message_processor(self):
        """Process messages from the queue."""
        while self.running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self._deliver_message(message)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    async def _deliver_message(self, message: AgentMessage):
        """Deliver message to intended recipients."""
        delivered = False
        if message.to_agent and message.to_agent in self.subscribers:
            for callback in self.subscribers[message.to_agent]:
                try:
                    await callback(message)
                    delivered = True
                except Exception as e:
                    logger.error(f"Error delivering message to {message.to_agent}: {e}")
        return delivered

    def _priority_from_message(self, message: AgentMessage) -> MessagePriority:
        if message.priority <= 2:
            return MessagePriority.CRITICAL
        if message.priority <= 4:
            return MessagePriority.HIGH
        if message.priority <= 7:
            return MessagePriority.NORMAL
        return MessagePriority.LOW

    async def _distributed_consumer(self):
        """Consume messages from the distributed queue."""
        try:
            while self.running:
                envelope = await distributed_message_queue.consume(
                    self.cluster_queue_name, timeout=1
                )
                if not envelope:
                    continue

                data = envelope.payload if isinstance(envelope.payload, dict) else {}
                message = AgentMessage.from_transport_dict(data)
                origin = message.metadata.get("origin_node")

                if origin == self.node_id:
                    await distributed_message_queue.ack(self.cluster_queue_name, envelope.message_id)
                    continue

                delivered = await self._deliver_message(message)
                if delivered:
                    await distributed_message_queue.ack(self.cluster_queue_name, envelope.message_id)
                else:
                    # Requeue the message for another node to process
                    await distributed_message_queue.publish(
                        self.cluster_queue_name,
                        message.to_transport_dict(),
                        priority=self._priority_from_message(message),
                    )
                    await distributed_message_queue.ack(self.cluster_queue_name, envelope.message_id)
        except asyncio.CancelledError:
            logger.debug("Distributed message consumer stopped")


class MultiAgentOrchestrator:
    """Main orchestrator for multi-agent workflows."""

    def __init__(self):
        self.agent_registry = AgentRegistry()
        self.distributed_enabled = getattr(settings, "DISTRIBUTED_ENABLED", False)
        self.message_bus = MessageBus(use_distributed_backend=self.distributed_enabled)
        self.active_tasks: Dict[str, Task] = {}
        self.active_workflows: Dict[str, List[WorkflowStep]] = {}
        self.task_queue = asyncio.Queue()
        self.running = False
        self.node_id = getattr(settings, "DISTRIBUTED_NODE_ID", "local-node")

        try:
            infrastructure_manager.register_distributed_queue(self.message_bus.cluster_queue_name)
        except Exception:
            logger.debug("Distributed queue registration skipped (infrastructure not ready)")

    async def start(self):
        """Start the multi-agent system."""
        await self.message_bus.start()
        self.running = True
        asyncio.create_task(self._task_processor())
        await self._persist_cluster_snapshot()
        logger.info("Multi-agent orchestrator started")

    async def stop(self):
        """Stop the multi-agent system."""
        self.running = False
        await self.message_bus.stop()
        await self._persist_cluster_snapshot()
        logger.info("Multi-agent orchestrator stopped")

    async def create_workflow(self, workflow_definition: Dict[str, Any]) -> str:
        """Create a new multi-agent workflow."""
        workflow_id = str(uuid.uuid4())

        # Parse workflow definition
        steps = []
        for i, step_def in enumerate(workflow_definition.get("steps", [])):
            # Create task for the step
            task = Task(
                task_id=str(uuid.uuid4()),
                title=step_def["title"],
                description=step_def["description"],
                priority=step_def.get("priority", 5),
                inputs=step_def.get("inputs", {})
            )

            # Find best agent for the step
            required_capability = step_def.get("required_capability", "general")
            context = step_def.get("context", {})

            best_agent = self.agent_registry.find_best_agent(required_capability, context)
            if not best_agent:
                # Fallback to coordinator
                coordinator_agents = self.agent_registry.get_agents_by_role(AgentRole.COORDINATOR)
                best_agent = coordinator_agents[0] if coordinator_agents else None

            if best_agent:
                workflow_step = WorkflowStep(
                    step_id=str(uuid.uuid4()),
                    step_name=step_def["title"],
                    assigned_agent=best_agent.agent_id,
                    task=task,
                    order=i,
                    parallel_group=step_def.get("parallel_group")
                )
                steps.append(workflow_step)

        self.active_workflows[workflow_id] = steps
        logger.info(f"Created workflow {workflow_id} with {len(steps)} steps")

        await self._update_workflow_state(workflow_id, "pending")
        await self._persist_cluster_snapshot()

        # Start workflow execution
        asyncio.create_task(self._execute_workflow(workflow_id))

        return workflow_id

    async def _execute_workflow(self, workflow_id: str):
        """Execute a workflow."""
        try:
            steps = self.active_workflows[workflow_id]
            logger.info(f"Starting workflow execution: {workflow_id}")
            await self._update_workflow_state(workflow_id, "in_progress")

            # Group steps for parallel execution
            parallel_groups = {}
            for step in steps:
                group = step.parallel_group if step.parallel_group is not None else step.order
                if group not in parallel_groups:
                    parallel_groups[group] = []
                parallel_groups[group].append(step)

            # Execute parallel groups in order
            for group_num in sorted(parallel_groups.keys()):
                group_steps = parallel_groups[group_num]

                if len(group_steps) == 1:
                    # Single step execution
                    await self._execute_step(group_steps[0])
                else:
                    # Parallel step execution
                    await asyncio.gather(*[self._execute_step(step) for step in group_steps])

            logger.info(f"Workflow completed: {workflow_id}")
            await self._update_workflow_state(workflow_id, "completed")
            await self._persist_cluster_snapshot()

        except Exception as e:
            logger.error(f"Workflow failed: {workflow_id}, error: {e}")
            await self._update_workflow_state(workflow_id, "failed")

    async def _execute_step(self, step: WorkflowStep):
        """Execute a single workflow step."""
        try:
            step.task.status = TaskStatus.IN_PROGRESS
            step.task.started_at = datetime.now()

            # Send task assignment message
            message = AgentMessage(
                message_id=str(uuid.uuid4()),
                from_agent="orchestrator",
                to_agent=step.assigned_agent,
                message_type=MessageType.TASK_ASSIGNMENT,
                task_id=step.task.task_id,
                content={
                    "task_title": step.task.title,
                    "task_description": step.task.description,
                    "task_inputs": step.task.inputs,
                    "workflow_id": step.step_id
                }
            )
            await self.message_bus.send_message(message)

            # Wait for task completion
            await self._wait_for_task_completion(step.task.task_id)

        except Exception as e:
            step.task.status = TaskStatus.FAILED
            step.task.feedback.append(f"Execution failed: {str(e)}")
            logger.error(f"Step execution failed: {step.step_name}, error: {e}")

    async def _wait_for_task_completion(self, task_id: str, timeout: int = 300):
        """Wait for a task to complete."""
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < timeout:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    return task
            await asyncio.sleep(1)
        raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")

    async def _task_processor(self):
        """Process tasks from the queue."""
        while self.running:
            try:
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                await self._process_task(task)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing task: {e}")

    async def _process_task(self, task: Task):
        """Process a single task."""
        try:
            task.status = TaskStatus.IN_PROGRESS
            self.active_tasks[task.task_id] = task

            # Find and assign the best agent
            best_agent = self.agent_registry.find_best_agent("general", {"task_type": "automated"})
            if best_agent:
                task.assigned_agent = best_agent.agent_id
                await self._delegate_to_agent(task, best_agent)
            else:
                raise Exception("No suitable agent found")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.feedback.append(str(e))
            logger.error(f"Task processing failed: {task.task_id}, error: {e}")

    async def _delegate_to_agent(self, task: Task, agent: AgentIdentity):
        """Delegate task to a specific agent."""
        # This would integrate with actual LLM APIs in production
        # For now, simulate task execution

        await asyncio.sleep(2)  # Simulate processing time

        # Simulate task output
        task.outputs = {
            "result": f"Task '{task.title}' completed by {agent.name}",
            "agent_used": agent.name,
            "execution_time": "2.0 seconds",
            "quality_score": 0.85
        }
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()

        # Send completion message
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=agent.agent_id,
            to_agent="orchestrator",
            message_type=MessageType.TASK_COMPLETION,
            task_id=task.task_id,
            content=task.outputs
        )
        await self.message_bus.send_message(message)

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get the current status of a workflow."""
        if workflow_id not in self.active_workflows:
            return {"error": "Workflow not found"}

        steps = self.active_workflows[workflow_id]
        completed_steps = sum(1 for step in steps if step.task.status == TaskStatus.COMPLETED)
        failed_steps = sum(1 for step in steps if step.task.status == TaskStatus.FAILED)

        return {
            "workflow_id": workflow_id,
            "total_steps": len(steps),
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "progress_percentage": (completed_steps / len(steps)) * 100,
            "status": "completed" if completed_steps == len(steps) else "in_progress",
            "steps": [
                {
                    "step_id": step.step_id,
                    "name": step.step_name,
                    "agent": step.assigned_agent,
                    "status": step.task.status.value,
                    "progress": step.task.status.value
                }
                for step in steps
            ]
        }

    async def _persist_cluster_snapshot(self):
        """Store orchestrator status in distributed state."""
        if not self.distributed_enabled:
            return

        snapshot = {
            "node_id": self.node_id,
            "status": "running" if self.running else "stopped",
            "active_workflows": len(self.active_workflows),
            "active_tasks": len(self.active_tasks),
            "timestamp": datetime.now().isoformat(),
        }

        await distributed_state_manager.set_state("multi_agent", self.node_id, snapshot, ttl=180)

    async def _update_workflow_state(self, workflow_id: str, status: str):
        """Persist workflow state for distributed coordination."""
        if not self.distributed_enabled:
            return

        steps = self.active_workflows.get(workflow_id, [])
        await distributed_state_manager.set_state(
            "workflows",
            workflow_id,
            {
                "workflow_id": workflow_id,
                "status": status,
                "node_id": self.node_id,
                "steps": [
                    {
                        "step_id": step.step_id,
                        "agent": step.assigned_agent,
                        "status": step.task.status.value,
                    }
                    for step in steps
                ],
                "updated_at": datetime.now().isoformat(),
            },
            ttl=3600,
        )

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        return {
            "active_agents": len(self.agent_registry.agents),
            "active_workflows": len(self.active_workflows),
            "active_tasks": len(self.active_tasks),
            "agents_by_role": {
                role.value: len(agents)
                for role, agents in self.agent_registry.role_to_agents.items()
            },
            "system_health": "operational" if self.running else "stopped",
            "distributed": {
                "enabled": self.distributed_enabled,
                "queue": self.message_bus.cluster_queue_name if self.distributed_enabled else None,
                "node_id": self.node_id,
            },
        }


# Global multi-agent orchestrator instance
orchestrator = MultiAgentOrchestrator()


async def start_multi_agent_system():
    """Start the global multi-agent system."""
    await orchestrator.start()


async def stop_multi_agent_system():
    """Stop the global multi-agent system."""
    await orchestrator.stop()


async def create_business_workflow(business_task: str, context: Dict[str, Any]) -> str:
    """Create and execute a business workflow."""
    await start_multi_agent_system()

    # Define workflow based on business task
    workflow_definition = {
        "steps": [
            {
                "title": "Research and Analysis",
                "description": f"Research and analyze {business_task}",
                "required_capability": "information_gathering",
                "context": context,
                "priority": 8
            },
            {
                "title": "Solution Development",
                "description": "Develop solutions and recommendations",
                "required_capability": "content_generation",
                "context": context,
                "priority": 7,
                "parallel_group": 1
            },
            {
                "title": "Quality Review",
                "description": "Review and validate the solution",
                "required_capability": "quality_assessment",
                "context": context,
                "priority": 6,
                "parallel_group": 1
            }
        ]
    }

    workflow_id = await orchestrator.create_workflow(workflow_definition)
    return workflow_id


def get_multi_agent_orchestrator() -> MultiAgentOrchestrator:
    """Get the global multi-agent orchestrator instance."""
    return orchestrator
