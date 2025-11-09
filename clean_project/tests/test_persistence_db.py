from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_system.database_models import db_manager
from agent_system.enhanced_persistence import (
    load_action_selector,
    load_learning_system,
    load_memory_system,
    save_action_selector,
    save_learning_system,
    save_memory_system,
)
from agent_system.enterprise_persistence import enterprise_persistence
from agent_system.intelligent_action_selector import IntelligentActionSelector
from agent_system.learning import LearningSystem
from agent_system.memory import MemorySystem
from agent_system.models import Action, ActionStatus, Observation


@pytest.fixture(autouse=True)
def isolated_database(tmp_path: Path):
    """Use an isolated SQLite database for each persistence test."""

    db_path = tmp_path / "persistence.db"
    db_url = f"sqlite:///{db_path}"

    # Dispose any existing connections before switching URLs
    db_manager.close()
    enterprise_persistence.configure(database_url=db_url)

    yield

    db_manager.close()


def test_action_selector_roundtrip():
    selector = IntelligentActionSelector()
    selector.action_history["goal/test"] = {"success": 0.9}
    selector.context_weights = {"recent": 0.6}
    selector.goal_patterns = {"goal": ["act"]}

    save_action_selector(selector)

    restored = IntelligentActionSelector()
    payload = load_action_selector(restored)

    assert payload["action_history"] == selector.action_history
    assert restored.context_weights == selector.context_weights
    assert restored.goal_patterns == selector.goal_patterns


def test_learning_system_roundtrip():
    learning = LearningSystem()
    learning.strategy_performance["strategy"] = [1.0, 0.5]
    learning.pattern_library["pattern"] = [("act", 0.75)]

    save_learning_system(learning)

    restored = LearningSystem()
    payload = load_learning_system(restored)

    assert payload["strategy_performance"]["strategy"] == [1.0, 0.5]
    assert restored.pattern_library["pattern"] == [("act", 0.75)]


def test_memory_system_roundtrip():
    memory_system = MemorySystem()
    action = Action(
        id="action-1",
        name="search_information",
        tool_name="web",
        parameters={"query": "test"},
        expected_outcome="result",
        cost=0.1,
        prerequisites=[],
    )
    observation = Observation(
        action_id="action-1",
        status=ActionStatus.SUCCESS,
        result={"data": True},
        feedback="ok",
        metrics={"duration_ms": 10},
    )
    memory_system.store_memory(
        goal_id="goal-1",
        action=action,
        observation=observation,
        context={"goal_description": "test memory"},
        success_score=0.8,
    )

    save_memory_system(memory_system)

    restored = MemorySystem()
    stored_payload = load_memory_system(restored)

    assert len(stored_payload) == 1
    assert len(restored.working_memory) == 1
    assert restored.working_memory[0].observation.result == {"data": True}
    assert restored.memory_counter >= 1
