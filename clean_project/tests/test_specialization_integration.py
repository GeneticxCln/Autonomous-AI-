from __future__ import annotations

from agent_system.multi_agent_system import AgentRole, MultiAgentOrchestrator
from agent_system.project_analyzer import ProjectStressTester
from agent_system.project_analyzer.orchestrator_integration import (
    apply_specialization_plan_to_registry,
)
from agent_system.project_analyzer.specialization import SpecializationPlan


def _make_plan() -> SpecializationPlan:
    return SpecializationPlan(
        domain="docs",
        memory_priority="low",
        cache_overrides={"max_entries": 512, "ttl_seconds": 600},
        agent_roles=[AgentRole.WRITER.value, AgentRole.REVISER.value],
        resource_budget={"parallel_workers": 2, "memory_multiplier": 0.9, "size_gb": 0.01, "total_files": 5},
    )


def test_apply_specialization_plan_to_registry_registers_specialized_agents():
    orchestrator = MultiAgentOrchestrator()
    registry = orchestrator.agent_registry
    plan = _make_plan()
    created = apply_specialization_plan_to_registry(plan, registry)

    assert len(created) == 2
    writer_agents = registry.get_agents_by_role(AgentRole.WRITER)
    reviser_agents = registry.get_agents_by_role(AgentRole.REVISER)

    assert any(agent.agent_id == f"{plan.domain}_{AgentRole.WRITER.value}_specialist" for agent in writer_agents)
    assert any(agent.agent_id == f"{plan.domain}_{AgentRole.REVISER.value}_specialist" for agent in reviser_agents)


def test_project_stress_tester_integrates_with_orchestrator(tmp_path):
    orchestrator = MultiAgentOrchestrator()
    tester = ProjectStressTester(orchestrator=orchestrator)
    metrics = tester.simulate_growth("project_x", [2])

    assert metrics[0].failures == 0
    reviser_agents = orchestrator.agent_registry.get_agents_by_role(AgentRole.REVISER)
    assert reviser_agents, "Revisor agents should be spun up for backend workloads"
