"""
Job schema definitions for asynchronous agent processing.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, validator


class JobType(str, Enum):
    """Supported asynchronous job types."""

    AGENT_EXECUTION = "agent_execution"
    LEARNING_REFRESH = "learning_refresh"
    TOOL_EXECUTION = "tool_execution"


class JobStatus(str, Enum):
    """Lifecycle states for background jobs."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobPriority(str, Enum):
    """Logical priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AgentExecutionPayload(BaseModel):
    """Payload required to execute an agent asynchronously."""

    agent_id: str = Field(..., description="Agent identifier to execute")
    max_cycles: int = Field(
        50, ge=1, le=1000, description="Maximum planner cycles the worker should run"
    )
    max_concurrent_goals: int = Field(
        1, ge=1, le=20, description="Upper bound for concurrent goal processing"
    )
    requested_by: Optional[str] = Field(
        default=None, description="User who initiated the execution"
    )
    tenant_id: Optional[str] = Field(
        default=None, description="Tenant or organization scoping this job"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context metadata")

    @validator("agent_id")
    def _agent_id_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("agent_id must be provided")
        return value


class JobQueueMessage(BaseModel):
    """Payload stored in the distributed queue."""

    job_id: str
    job_type: JobType
    priority: JobPriority = JobPriority.NORMAL
    attempts: int = 0


AGENT_JOB_QUEUE = "agent.jobs"
