"""
Database Models for Enterprise Deployment
Replaces JSON file-based persistence with proper database schema
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    Index, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy import create_engine

# Import auth models to ensure shared Base metadata
from .auth_models import UserModel  # Import UserModel for foreign key relationships

# Create a unified Base that includes both auth and database models
from .auth_models import Base as AuthBase
Base = AuthBase


class ActionSelectorModel(Base):
    """Database model for action selector data."""
    __tablename__ = 'action_selectors'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    selector_type = Column(String(50), nullable=False, default='intelligent')
    action_scores = Column(JSON, default=dict)
    action_counts = Column(JSON, default=dict)
    context_weights = Column(JSON, default=dict)
    goal_patterns = Column(JSON, default=dict)
    learning_rate = Column(Float, default=0.1)
    epsilon = Column(Float, default=0.1)
    last_updated = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Indexes for performance
    __table_args__ = (
        Index('idx_action_selector_type', 'selector_type'),
        Index('idx_action_selector_updated', 'last_updated'),
    )


class MemoryModel(Base):
    """Database model for agent memory."""
    __tablename__ = 'memories'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    memory_id = Column(String(100), unique=True, nullable=False, index=True)
    goal_id = Column(String(100), index=True)
    memory_type = Column(String(20), default='working')  # 'working' or 'episodic'
    action_data = Column(JSON)
    observation_data = Column(JSON)
    context_data = Column(JSON)
    success_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    accessed_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Indexes for performance
    __table_args__ = (
        Index('idx_memory_goal_id', 'goal_id'),
        Index('idx_memory_type', 'memory_type'),
        Index('idx_memory_created', 'created_at'),
        UniqueConstraint('memory_id', name='uq_memory_id'),
    )


class LearningSystemModel(Base):
    """Database model for learning system data."""
    __tablename__ = 'learning_systems'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    system_type = Column(String(50), nullable=False, default='default')
    learned_strategies = Column(JSON, default=dict)
    strategy_scores = Column(JSON, default=dict)
    total_episodes = Column(Integer, default=0)
    learning_history = Column(JSON, default=list)
    best_strategies = Column(JSON, default=dict)
    last_updated = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Indexes
    __table_args__ = (
        Index('idx_learning_system_type', 'system_type'),
        Index('idx_learning_updated', 'last_updated'),
    )


class GoalModel(Base):
    """Database model for agent goals."""
    __tablename__ = 'goals'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    status = Column(String(20), default='pending')  # 'pending', 'in_progress', 'completed', 'failed'
    priority = Column(Integer, default=1)  # 1-10 scale
    progress = Column(Float, default=0.0)
    target_date = Column(DateTime, nullable=True)
    created_by = Column(String(100), nullable=True)  # Store user ID as string, no foreign key
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    completed_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_goal_status', 'status'),
        Index('idx_goal_priority', 'priority'),
        Index('idx_goal_created', 'created_at'),
        Index('idx_goal_created_by', 'created_by'),
    )


class AgentModel(Base):
    """Database model for autonomous agents."""
    __tablename__ = 'agents'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    status = Column(String(20), default='idle')  # 'idle', 'running', 'executing', 'error'
    goals = Column(JSON, default=list)
    memory = Column(JSON, default=dict)  # Working and episodic memory
    memory_capacity = Column(Integer, default=1000)
    configuration = Column(JSON, default=dict)
    performance_metrics = Column(JSON, default=dict)
    created_by = Column(String(100), nullable=True)  # Store user ID as string, no foreign key
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    last_execution = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_agent_name', 'name'),
        Index('idx_agent_status', 'status'),
        Index('idx_agent_created', 'created_at'),
        Index('idx_agent_last_execution', 'last_execution'),
    )


class ActionModel(Base):
    """Database model for actions."""
    __tablename__ = 'actions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_id = Column(String(100), unique=True, nullable=False, index=True)
    goal_id = Column(String(100), index=True)
    agent_id = Column(String(36), index=True)  # Remove foreign key for now
    action_type = Column(String(100), nullable=False)
    description = Column(Text)
    parameters = Column(JSON, default=dict)
    status = Column(String(20), default='pending')  # 'pending', 'running', 'completed', 'failed'
    result = Column(JSON)
    success_score = Column(Float, default=0.0)
    user_id = Column(String(100), nullable=True)  # Store user ID as string, no foreign key
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_action_agent_id', 'agent_id'),
        Index('idx_action_goal_id', 'goal_id'),
        Index('idx_action_type', 'action_type'),
        Index('idx_action_status', 'status'),
        Index('idx_action_created', 'created_at'),
        Index('idx_action_user_id', 'user_id'),
        UniqueConstraint('action_id', name='uq_action_id'),
    )


class ObservationModel(Base):
    """Database model for observations."""
    __tablename__ = 'observations'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    observation_id = Column(String(100), unique=True, nullable=False, index=True)
    action_id = Column(String(100), index=True)
    goal_id = Column(String(100), index=True)
    content = Column(Text, nullable=False)
    observation_type = Column(String(50), default='result')
    obs_metadata = Column('metadata', JSON, default=dict)
    success = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_observation_action_id', 'action_id'),
        Index('idx_observation_goal_id', 'goal_id'),
        Index('idx_observation_type', 'observation_type'),
        Index('idx_observation_created', 'created_at'),
        UniqueConstraint('observation_id', name='uq_observation_id'),
    )


class CrossSessionPatternModel(Base):
    """Database model for cross-session learning patterns."""
    __tablename__ = 'cross_session_patterns'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pattern_id = Column(String(100), unique=True, nullable=False, index=True)
    pattern_type = Column(String(50), nullable=False)
    pattern_data = Column(JSON, nullable=False)
    confidence_score = Column(Float, default=0.0)
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    last_used = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Indexes
    __table_args__ = (
        Index('idx_pattern_type', 'pattern_type'),
        Index('idx_pattern_confidence', 'confidence_score'),
        Index('idx_pattern_usage', 'usage_count'),
        Index('idx_pattern_last_used', 'last_used'),
        UniqueConstraint('pattern_id', name='uq_pattern_id'),
    )


class SessionModel(Base):
    """Database model for agent sessions."""
    __tablename__ = 'sessions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    session_type = Column(String(50), default='default')
    start_time = Column(DateTime, default=lambda: datetime.now(UTC))
    end_time = Column(DateTime, nullable=True)
    goals_completed = Column(Integer, default=0)
    total_goals = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    session_meta = Column('session_metadata', JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Indexes
    __table_args__ = (
        Index('idx_session_type', 'session_type'),
        Index('idx_session_start', 'start_time'),
        Index('idx_session_success', 'success_rate'),
        UniqueConstraint('session_id', name='uq_session_id'),
    )


class DecisionModel(Base):
    """Database model for AI debugging decisions."""
    __tablename__ = 'decisions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    decision_id = Column(String(100), unique=True, nullable=False, index=True)
    session_id = Column(String(100), index=True)
    decision_type = Column(String(50), nullable=False)
    context = Column(JSON, default=dict)
    reasoning = Column(Text)
    confidence = Column(Float, default=0.0)
    action_taken = Column(String(100))
    outcome = Column(String(20))  # 'success', 'failure', 'unknown'
    execution_time_ms = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_decision_session', 'session_id'),
        Index('idx_decision_type', 'decision_type'),
        Index('idx_decision_confidence', 'confidence'),
        Index('idx_decision_created', 'created_at'),
        UniqueConstraint('decision_id', name='uq_decision_id'),
    )


class PerformanceMetricModel(Base):
    """Database model for performance metrics."""
    __tablename__ = 'performance_metrics'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), default='count')
    component = Column(String(50))
    metric_tags = Column('tags', JSON, default=dict)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    # Indexes
    __table_args__ = (
        Index('idx_metric_component', 'component'),
        Index('idx_metric_timestamp', 'timestamp'),
        Index('idx_metric_name_timestamp', 'metric_name', 'timestamp'),
    )


class SecurityAuditModel(Base):
    """Database model for security audits."""
    __tablename__ = 'security_audits'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    audit_id = Column(String(100), unique=True, nullable=False, index=True)
    operation_type = Column(String(50), nullable=False)
    target = Column(Text)
    is_valid = Column(Boolean, default=True)
    security_level = Column(String(20), default='low')  # 'low', 'medium', 'high', 'critical'
    message = Column(Text)
    suggestions = Column(JSON, default=list)
    audit_metadata = Column('metadata', JSON, default=dict)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    # Indexes
    __table_args__ = (
        Index('idx_audit_operation', 'operation_type'),
        Index('idx_audit_level', 'security_level'),
        Index('idx_audit_valid', 'is_valid'),
        Index('idx_audit_timestamp', 'timestamp'),
        UniqueConstraint('audit_id', name='uq_audit_id'),
    )


class ConfigurationModel(Base):
    """Database model for system configuration."""
    __tablename__ = 'configurations'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(JSON, nullable=False)
    config_type = Column(String(50), default='system')
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Indexes
    __table_args__ = (
        Index('idx_config_type', 'config_type'),
        Index('idx_config_active', 'is_active'),
        UniqueConstraint('config_key', name='uq_config_key'),
    )


class DatabaseManager:
    """Database connection and session management."""

    def __init__(self, database_url: str = "sqlite:///./agent_enterprise.db"):
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None

    def initialize(self):
        """Initialize database connection and create tables."""
        try:
            # Create engine with connection pooling
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_recycle=300,
                echo=False  # Set to True for SQL debugging
            )

            # Create session factory (prevent attribute expiration on commit)
            self.SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=self.engine, expire_on_commit=False
            )

            # Create all tables
            Base.metadata.create_all(bind=self.engine)

            print(f"✅ Database initialized successfully: {self.database_url}")

        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            raise

    def get_session(self):
        """Get a database session."""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.SessionLocal()

    def close(self):
        """Close database connections."""
        if self.engine:
            self.engine.dispose()
            print("✅ Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


def get_db_session():
    """Dependency function for FastAPI or context managers."""
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()
