from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

pytest.importorskip("sqlalchemy")

from agent_system.database_models import AgentModel, db_manager
from agent_system.job_definitions import JobPriority, JobType
from agent_system.job_manager import AgentJobStore


@pytest.fixture(autouse=True)
def isolated_job_database(tmp_path: Path):
    """Provide an isolated SQLite database for job store tests."""

    db_manager.close()
    db_path = tmp_path / "jobs.db"
    db_manager.database_url = f"sqlite:///{db_path}"
    db_manager.initialize()
    try:
        yield
    finally:
        db_manager.close()


@pytest.fixture
def agent_id() -> str:
    with db_manager.get_session() as session:
        agent = AgentModel(name="Test Agent", description="worker test agent")
        session.add(agent)
        session.commit()
        return agent.id


def test_job_store_lifecycle(agent_id: str):
    store = AgentJobStore()
    payload: Dict[str, object] = {
        "agent_id": agent_id,
        "max_cycles": 5,
        "max_concurrent_goals": 1,
    }

    record = store.create_job(
        job_type=JobType.AGENT_EXECUTION,
        priority=JobPriority.HIGH,
        queue_name="agent.jobs",
        payload=payload,
        requested_by="tester",
        agent_id=agent_id,
    )

    assert record["status"] == "queued"

    running = store.mark_job_running(record["id"])
    assert running is not None
    assert running["status"] == "running"
    assert running["started_at"] is not None

    completed = store.mark_job_succeeded(record["id"], result={"ok": True})
    assert completed is not None
    assert completed["status"] == "succeeded"
    assert completed["result"]["ok"] is True

    with db_manager.get_session() as session:
        agent = session.query(AgentModel).filter(AgentModel.id == agent_id).first()
        assert agent is not None
        assert agent.status == "idle"
        assert agent.last_execution is not None


def test_job_store_failure(agent_id: str):
    store = AgentJobStore()
    payload = {"agent_id": agent_id, "max_cycles": 3, "max_concurrent_goals": 1}
    record = store.create_job(
        job_type=JobType.AGENT_EXECUTION,
        priority=JobPriority.NORMAL,
        queue_name="agent.jobs",
        payload=payload,
        requested_by="tester",
        agent_id=agent_id,
    )

    failed = store.mark_job_failed(record["id"], error="boom")
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["error"] == "boom"

    jobs = store.list_jobs(agent_id=agent_id)
    assert len(jobs) >= 1
    assert jobs[0]["id"] == record["id"]
