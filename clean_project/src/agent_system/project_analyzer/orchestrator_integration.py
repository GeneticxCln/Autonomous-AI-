"""Bridge between project specialization plans and the multi-agent registry."""

from __future__ import annotations

from typing import List

from ..multi_agent_system import AgentCapability, AgentIdentity, AgentRegistry, AgentRole
from .specialization import SpecializationPlan

SPECIALIZED_AGENT_SUFFIX = "specialist"


def apply_specialization_plan_to_registry(plan: SpecializationPlan, registry: AgentRegistry) -> List[str]:
    """Ensure the registry has domain-specific agents for the plan roles."""
    created_agent_ids: List[str] = []

    for role_value in plan.agent_roles:
        try:
            role = AgentRole(role_value)
        except ValueError:
            continue

        agent_id = f"{plan.domain}_{role.value}_{SPECIALIZED_AGENT_SUFFIX}"
        existing_for_role = registry.get_agents_by_role(role)
        if any(agent.agent_id == agent_id for agent in existing_for_role):
            continue

        capability = AgentCapability(
            name=f"{role.value}_specialized",
            description=f"Handles {plan.domain} {role.value} work with {plan.memory_priority} priority",
            complexity_level="high" if plan.memory_priority == "high" else "medium",
            estimated_duration=int(plan.resource_budget.get("size_gb", 1) * 100),
        )

        specialist = AgentIdentity(
            agent_id=agent_id,
            name=f"{plan.domain.title()} {role.value.title()} Specialist",
            role=role,
            capabilities=[capability],
            expertise_domains=[plan.domain, role.value],
            max_concurrent_tasks=max(1, int(plan.resource_budget.get("parallel_workers", 2))),
            communication_style="adaptive",
            quality_standards=[plan.memory_priority, "domain_alignment"],
        )

        registry.register_agent(specialist)
        created_agent_ids.append(agent_id)

    return created_agent_ids
