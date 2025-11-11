"""
Database Models for Enterprise Deployment
Replaces JSON file-based persistence with proper database schema
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, Iterator, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Engine,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):  # type: ignore[misc]
    pass


class ActionSelectorModel(Base):
    """Database model for action selector data."""

    __tablename__ = "action_selectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    selector_type: Mapped[str] = mapped_column(String(50), nullable=False, default="intelligent")
    action_scores: Mapped[Dict[str, float]] = mapped_column(JSON, default=dict)
    action_counts: Mapped[Dict[str, int]] = mapped_column(JSON, default=dict)
    action_history: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # For IntelligentActionSelector
    context_weights: Mapped[Dict[str, float]] = mapped_column(JSON, default=dict)
    goal_patterns: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    learning_rate: Mapped[float] = mapped_column(Float, default=0.1)
    epsilon: Mapped[float] = mapped_column(Float, default=0.1)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # Indexes for performance
    __table_args__ = (
        Index("idx_action_selector_type", "selector_type"),
        Index("idx_action_selector_updated", "last_updated"),
    )


class MemoryModel(Base):
    """Database model for agent memory."""

    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    memory_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    goal_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    memory_type: Mapped[str] = mapped_column(String(20), default="working")  # 'working' or 'episodic'
    action_data: Mapped[Dict[str, Any]] = mapped_column(JSON)
    observation_data: Mapped[Dict[str, Any]] = mapped_column(JSON)
    context_data: Mapped[Dict[str, Any]] = mapped_column(JSON)
    success_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    accessed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # Indexes for performance
    __table_args__ = (
        Index("idx_memory_goal_id", "goal_id"),
        Index("idx_memory_type", "memory_type"),
        Index("idx_memory_created", "created_at"),
        UniqueConstraint("memory_id", name="uq_memory_id"),
    )


class LearningSystemModel(Base):
    """Database model for learning system data."""

    __tablename__ = "learning_systems"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    system_type: Mapped[str] = mapped_column(String(50), nullable=False, default="default")
    learned_strategies: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    strategy_performance: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # For LearningSystem
    strategy_scores: Mapped[Dict[str, float]] = mapped_column(JSON, default=dict)
    pattern_library: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # For LearningSystem
    total_episodes: Mapped[int] = mapped_column(Integer, default=0)
    learning_history: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    best_strategies: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # Indexes
    __table_args__ = (
        Index("idx_learning_system_type", "system_type"),
        Index("idx_learning_updated", "last_updated"),
    )


class GoalModel(Base):
    """Database model for agent goals."""

    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # 'pending', 'in_progress', 'completed', 'failed'
    priority: Mapped[int] = mapped_column(Integer, default=1)  # 1-10 scale
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    target_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Store user ID as string, no foreign key
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_goal_status", "status"),
        Index("idx_goal_priority", "priority"),
        Index("idx_goal_created", "created_at"),
        Index("idx_goal_created_by", "created_by"),
    )


class AgentModel(Base):
    """Database model for autonomous agents."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="idle")  # 'idle', 'running', 'executing', 'error'
    goals: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    memory: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # Working and episodic memory
    memory_capacity: Mapped[int] = mapped_column(Integer, default=1000)
    configuration: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    performance_metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Store user ID as string, no foreign key
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    last_execution: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_agent_name", "name"),
        Index("idx_agent_status", "status"),
        Index("idx_agent_created", "created_at"),
        Index("idx_agent_last_execution", "last_execution"),
    )


class ActionModel(Base):
    """Database model for actions."""

    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    goal_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)  # Remove foreign key for now
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # 'pending', 'running', 'completed', 'failed'
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    success_score: Mapped[float] = mapped_column(Float, default=0.0)
    user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Store user ID as string, no foreign key
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_action_agent_id", "agent_id"),
        Index("idx_action_goal_id", "goal_id"),
        Index("idx_action_type", "action_type"),
        Index("idx_action_status", "status"),
        Index("idx_action_created", "created_at"),
        Index("idx_action_user_id", "user_id"),
        UniqueConstraint("action_id", name="uq_action_id"),
    )


class AgentJobModel(Base):
    """Database model tracking asynchronous agent jobs."""

    __tablename__ = "agent_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    queue_name: Mapped[str] = mapped_column(String(50), default="normal")
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_agent_jobs_agent_id", "agent_id"),
        Index("idx_agent_jobs_type", "job_type"),
        Index("idx_agent_jobs_status", "status"),
        Index("idx_agent_jobs_queue", "queue_name"),
        Index("idx_agent_jobs_created", "created_at"),
    )


class ObservationModel(Base):
    """Database model for observations."""

    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    observation_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    action_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    goal_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    observation_type: Mapped[str] = mapped_column(String(50), default="result")
    obs_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_observation_action_id", "action_id"),
        Index("idx_observation_goal_id", "goal_id"),
        Index("idx_observation_type", "observation_type"),
        Index("idx_observation_created", "created_at"),
        UniqueConstraint("observation_id", name="uq_observation_id"),
    )


class CrossSessionPatternModel(Base):
    """Database model for cross-session learning patterns."""

    __tablename__ = "cross_session_patterns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pattern_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    pattern_type: Mapped[str] = mapped_column(String(50), nullable=False)
    pattern_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Indexes
    __table_args__ = (
        Index("idx_pattern_type", "pattern_type"),
        Index("idx_pattern_confidence", "confidence_score"),
        Index("idx_pattern_usage", "usage_count"),
        Index("idx_pattern_last_used", "last_used"),
        UniqueConstraint("pattern_id", name="uq_pattern_id"),
    )


class SessionModel(Base):
    """Database model for agent sessions."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    session_type: Mapped[str] = mapped_column(String(50), default="default")
    start_time: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    goals_completed: Mapped[int] = mapped_column(Integer, default=0)
    total_goals: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    session_meta: Mapped[Dict[str, Any]] = mapped_column("session_metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # Indexes
    __table_args__ = (
        Index("idx_session_type", "session_type"),
        Index("idx_session_start", "start_time"),
        Index("idx_session_success", "success_rate"),
        UniqueConstraint("session_id", name="uq_session_id"),
    )


class DecisionModel(Base):
    """Database model for AI debugging decisions."""

    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    decision_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    decision_type: Mapped[str] = mapped_column(String(50), nullable=False)
    context: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    reasoning: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    action_taken: Mapped[Optional[str]] = mapped_column(String(100))
    outcome: Mapped[Optional[str]] = mapped_column(String(20))  # 'success', 'failure', 'unknown'
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_decision_session", "session_id"),
        Index("idx_decision_type", "decision_type"),
        Index("idx_decision_confidence", "confidence"),
        Index("idx_decision_created", "created_at"),
        UniqueConstraint("decision_id", name="uq_decision_id"),
    )


class PerformanceMetricModel(Base):
    """Database model for performance metrics."""

    __tablename__ = "performance_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_unit: Mapped[str] = mapped_column(String(20), default="count")
    component: Mapped[Optional[str]] = mapped_column(String(50))
    metric_tags: Mapped[Dict[str, Any]] = mapped_column("tags", JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)

    # Indexes
    __table_args__ = (
        Index("idx_metric_component", "component"),
        Index("idx_metric_timestamp", "timestamp"),
        Index("idx_metric_name_timestamp", "metric_name", "timestamp"),
    )


class SecurityAuditModel(Base):
    """Database model for security audits."""

    __tablename__ = "security_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    audit_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target: Mapped[Optional[str]] = mapped_column(Text)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    security_level: Mapped[str] = mapped_column(String(20), default="low")  # 'low', 'medium', 'high', 'critical'
    message: Mapped[Optional[str]] = mapped_column(Text)
    suggestions: Mapped[List[str]] = mapped_column(JSON, default=list)
    audit_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)

    # Indexes
    __table_args__ = (
        Index("idx_audit_operation", "operation_type"),
        Index("idx_audit_level", "security_level"),
        Index("idx_audit_valid", "is_valid"),
        Index("idx_audit_timestamp", "timestamp"),
        UniqueConstraint("audit_id", name="uq_audit_id"),
    )


class ConfigurationModel(Base):
    """Database model for system configuration."""

    __tablename__ = "configurations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    config_value: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    config_type: Mapped[str] = mapped_column(String(50), default="system")
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Indexes
    __table_args__ = (
        Index("idx_config_type", "config_type"),
        Index("idx_config_active", "is_active"),
        UniqueConstraint("config_key", name="uq_config_key"),
    )


class AgentCapabilityModel(Base):
    """Cluster-wide registry of agent/worker capabilities (ADR-002)."""

    __tablename__ = "agent_capabilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # planner/executor/checker/etc
    capabilities: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)  # list of capability descriptors
    expertise_domains: Mapped[List[str]] = mapped_column(JSON, default=list)
    capacity: Mapped[int] = mapped_column(Integer, default=1)  # concurrent tasks supported
    tool_scopes: Mapped[List[str]] = mapped_column(JSON, default=list)
    capability_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("idx_capabilities_role", "role"),
        Index("idx_capabilities_capacity", "capacity"),
        Index("idx_capabilities_updated", "updated_at"),
        UniqueConstraint("instance_id", name="uq_capability_instance_id"),
    )


class DatabaseManager:
    """Database connection and session management."""

    def __init__(
        self,
        database_url: str = "sqlite:///./agent_enterprise.db",
        *,
        pool_size: int | None = None,
        max_overflow: int | None = None,
        pool_timeout: int | None = None,
        pool_recycle: int | None = None,
    ):
        self.database_url = database_url
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker[Session]] = None
        self.pool_size = (
            pool_size if pool_size is not None else int(os.getenv("DB_POOL_SIZE", "20"))
        )
        self.max_overflow = (
            max_overflow if max_overflow is not None else int(os.getenv("DB_MAX_OVERFLOW", "30"))
        )
        self.pool_timeout = (
            pool_timeout if pool_timeout is not None else int(os.getenv("DB_POOL_TIMEOUT", "60"))
        )
        self.pool_recycle = (
            pool_recycle if pool_recycle is not None else int(os.getenv("DB_POOL_RECYCLE", "1800"))
        )

    def configure_pool(
        self,
        *,
        pool_size: Optional[int] = None,
        max_overflow: Optional[int] = None,
        pool_timeout: Optional[int] = None,
        pool_recycle: Optional[int] = None,
    ) -> None:
        """Allow runtime updates of pooling configuration prior to initialization."""
        if pool_size is not None:
            self.pool_size = pool_size
        if max_overflow is not None:
            self.max_overflow = max_overflow
        if pool_timeout is not None:
            self.pool_timeout = pool_timeout
        if pool_recycle is not None:
            self.pool_recycle = pool_recycle

    def _engine_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "pool_pre_ping": True,
            "pool_recycle": self.pool_recycle,
            "echo": False,
        }
        if self.pool_size:
            kwargs["pool_size"] = self.pool_size
        if self.max_overflow is not None:
            kwargs["max_overflow"] = self.max_overflow
        if self.pool_timeout is not None:
            kwargs["pool_timeout"] = self.pool_timeout
        if self.database_url.startswith("sqlite"):
            kwargs.setdefault("connect_args", {})
            # Explicitly type connect_args as Dict[str, Any] before calling update
            connect_args: Dict[str, Any] = kwargs["connect_args"]
            connect_args.update({"check_same_thread": False})
        return kwargs

    def initialize(self) -> None:
        """Initialize database connection and create tables."""
        try:
            engine_kwargs = self._engine_kwargs()
            self.engine = create_engine(self.database_url, **engine_kwargs)

            # Create session factory (prevent attribute expiration on commit)
            self.SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=self.engine, expire_on_commit=False
            )

            # Create all tables
            assert self.engine is not None  # Ensure engine is initialized
            Base.metadata.create_all(bind=self.engine)

            print(f"✅ Database initialized successfully: {self._mask_db_url(self.database_url)}")

        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            raise

    def get_session(self) -> Session:
        """Get a database session."""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.SessionLocal()

    def close(self) -> None:
        """Close database connections."""
        if self.engine:
            self.engine.dispose()
            print("✅ Database connections closed")

    @staticmethod
    def _mask_db_url(url: str) -> str:
        """Mask credentials in database URL for safe logging."""
        try:
            if url.startswith("sqlite"):
                return url
            if "://" not in url:
                return "***"
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                _, host = rest.split("@", 1)
                return f"{scheme}://***@{host}"
            return f"{scheme}://***"
        except Exception:
            return "***"


# Global database manager instance
db_manager = DatabaseManager()


def get_db_session() -> Iterator[Session]:
    """Dependency function for FastAPI or context managers."""
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()
