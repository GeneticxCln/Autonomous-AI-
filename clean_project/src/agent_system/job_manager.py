"""
Persistent storage helpers for asynchronous job records.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, cast

from .database_models import AgentJobModel, AgentModel, db_manager
from .job_definitions import JobPriority, JobStatus, JobType

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class AgentJobStore:
    """Handles creation and lifecycle updates for agent jobs."""

    _AGENT_STATUS_MAP = {
        JobStatus.QUEUED: "queued",
        JobStatus.RUNNING: "executing",
        JobStatus.SUCCEEDED: "idle",
        JobStatus.FAILED: "error",
    }

    def __init__(self) -> None:
        self.db = db_manager

    def create_job(
        self,
        *,
        job_type: JobType,
        priority: JobPriority = JobPriority.NORMAL,
        queue_name: str,
        payload: Dict[str, Any],
        requested_by: Optional[str] = None,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a persisted job record."""
        parameters = self._normalize_payload(payload)
        with self.db.get_session() as session:
            job = AgentJobModel(
                agent_id=agent_id,
                job_type=job_type.value,
                status=JobStatus.QUEUED.value,
                priority=priority.value,
                queue_name=queue_name,
                parameters=parameters,
                requested_by=requested_by,
                tenant_id=tenant_id,
                created_at=_now(),
            )
            session.add(job)
            self._update_agent_status(session, agent_id, JobStatus.QUEUED)
            session.commit()
            session.refresh(job)
            return self._to_dict(job)

    def mark_job_running(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Transition a job to running state."""
        with self.db.get_session() as session:
            job = session.query(AgentJobModel).filter(AgentJobModel.id == job_id).first()
            if not job:
                return None
            job.status = JobStatus.RUNNING.value
            job.started_at = _now()
            job.last_heartbeat = job.started_at
            self._update_agent_status(session, job.agent_id, JobStatus.RUNNING)
            session.commit()
            session.refresh(job)
            return self._to_dict(job)

    def mark_job_succeeded(
        self, job_id: str, result: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Mark job as completed successfully."""
        with self.db.get_session() as session:
            job = session.query(AgentJobModel).filter(AgentJobModel.id == job_id).first()
            if not job:
                return None
            job.status = JobStatus.SUCCEEDED.value
            job.result = result or {}
            job.completed_at = _now()
            self._update_agent_status(session, job.agent_id, JobStatus.SUCCEEDED)
            self._update_agent_last_run(session, job.agent_id)
            session.commit()
            session.refresh(job)
            return self._to_dict(job)

    def mark_job_failed(
        self,
        job_id: str,
        *,
        error: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Mark job as failed."""
        with self.db.get_session() as session:
            job = session.query(AgentJobModel).filter(AgentJobModel.id == job_id).first()
            if not job:
                return None
            job.status = JobStatus.FAILED.value
            job.error = error
            job.result = result or {}
            job.completed_at = _now()
            self._update_agent_status(session, job.agent_id, JobStatus.FAILED)
            session.commit()
            session.refresh(job)
            return self._to_dict(job)

    def record_heartbeat(self, job_id: str) -> None:
        """Update heartbeat timestamp for long-running jobs."""
        with self.db.get_session() as session:
            session.query(AgentJobModel).filter(AgentJobModel.id == job_id).update(
                {"last_heartbeat": _now()}
            )
            session.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Return a serialized job record."""
        with self.db.get_session() as session:
            job = session.query(AgentJobModel).filter(AgentJobModel.id == job_id).first()
            return self._to_dict(job) if job else None

    def list_jobs(
        self,
        *,
        agent_id: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List recent jobs filtered by agent or status."""
        with self.db.get_session() as session:
            query = session.query(AgentJobModel)
            if agent_id:
                query = query.filter(AgentJobModel.agent_id == agent_id)
            if status:
                query = query.filter(AgentJobModel.status == status.value)
            jobs = query.order_by(AgentJobModel.created_at.desc()).limit(limit).all()
            return [self._to_dict(job) for job in jobs]

    def get_queue_depth(self) -> int:
        """Get the current depth of the job queue (number of queued jobs)."""
        with self.db.get_session() as session:
            return cast(
                int,
                (
                    session.query(AgentJobModel)
                    .filter(AgentJobModel.status == JobStatus.QUEUED.value)
                    .count()
                ),
            )

    def _update_agent_status(self, session: Any, agent_id: Optional[str], job_status: JobStatus) -> None:
        if not agent_id:
            return
        status_value = self._AGENT_STATUS_MAP.get(job_status)
        if not status_value:
            return
        agent = session.query(AgentModel).filter(AgentModel.id == agent_id).first()
        if not agent:
            return
        agent.status = status_value
        if job_status == JobStatus.RUNNING:
            agent.last_execution = _now()
        session.add(agent)

    def _update_agent_last_run(self, session: Any, agent_id: Optional[str]) -> None:
        if not agent_id:
            return
        agent = session.query(AgentModel).filter(AgentModel.id == agent_id).first()
        if not agent:
            return
        agent.last_execution = _now()
        agent.status = "idle"
        session.add(agent)

    @staticmethod
    def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        if hasattr(payload, "model_dump"):
            return cast(Dict[str, Any], payload.model_dump())
        return dict(payload)

    @staticmethod
    def _to_dict(job: AgentJobModel) -> Dict[str, Any]:
        def _ts(value: Optional[datetime]) -> Optional[str]:
            return value.isoformat() if value else None

        return {
            "id": job.id,
            "agent_id": job.agent_id,
            "job_type": job.job_type,
            "status": job.status,
            "priority": job.priority,
            "queue_name": job.queue_name,
            "parameters": job.parameters or {},
            "result": job.result or {},
            "error": job.error,
            "requested_by": job.requested_by,
            "tenant_id": job.tenant_id,
            "retries": job.retries,
            "created_at": _ts(job.created_at),
            "started_at": _ts(job.started_at),
            "completed_at": _ts(job.completed_at),
            "last_heartbeat": _ts(job.last_heartbeat),
        }


# Global job store instance
job_store: AgentJobStore = AgentJobStore()
