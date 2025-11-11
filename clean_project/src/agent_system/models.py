from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class GoalStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class ActionStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


@dataclass
class Goal:
    """Represents a goal the agent is trying to accomplish."""

    id: str
    description: str
    priority: float  # 0-1, higher is more important
    status: GoalStatus = GoalStatus.PENDING
    parent_goal_id: Optional[str] = None
    subgoals: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    progress: float = 0.0  # 0-1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """Represents an action the agent can take."""

    id: str
    name: str
    tool_name: str
    parameters: Dict[str, Any]
    expected_outcome: str
    cost: float  # Estimated cost (time, resources, etc.)
    prerequisites: List[str] = field(default_factory=list)


@dataclass
class Observation:
    """Result of an action execution."""

    action_id: str
    status: ActionStatus
    result: Any
    timestamp: datetime = field(default_factory=datetime.now)
    feedback: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Memory:
    """A memory entry in the agent's experience."""

    id: str
    goal_id: str
    action: Action
    observation: Observation
    context: Dict[str, Any]
    success_score: float  # 0-1
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Plan:
    """A sequence of actions to achieve a goal."""

    goal_id: str
    actions: List[Action]
    estimated_cost: float
    confidence: float  # 0-1
    created_at: datetime = field(default_factory=datetime.now)
