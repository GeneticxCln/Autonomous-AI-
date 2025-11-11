"""Domain specialization layer for large project analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..multi_agent_system import AgentRole
from ..unified_config import unified_config

logger = logging.getLogger(__name__)


@dataclass
class DomainProfile:
    name: str
    languages: List[str]
    cache_entries: int
    ttl_seconds: int
    memory_priority: str
    agent_roles: List[AgentRole]
    base_workers: int
    memory_multiplier: float
    description: str = ""


@dataclass
class SpecializationPlan:
    domain: str
    memory_priority: str
    cache_overrides: Dict[str, int]
    agent_roles: List[str]
    resource_budget: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "memory_priority": self.memory_priority,
            "cache_overrides": self.cache_overrides,
            "agent_roles": self.agent_roles,
            "resource_budget": self.resource_budget,
        }


class PatternResourceAllocator:
    """Heuristic-based resource planner using project makeup."""

    def compute(
        self, profile: DomainProfile, file_stats: Dict[str, int], project_size_bytes: int
    ) -> Dict[str, Any]:
        total_files = sum(file_stats.values()) or 1
        size_gb = project_size_bytes / (1024**3) if project_size_bytes else 0
        scale_factor = min(3.0, 1 + (total_files / 2000) + size_gb * 0.5)
        parallel_workers = min(
            unified_config.project_analysis.max_parallel_parse_tasks,
            max(1, int(profile.base_workers * scale_factor)),
        )
        return {
            "parallel_workers": parallel_workers,
            "memory_multiplier": min(3.0, profile.memory_multiplier * scale_factor),
            "size_gb": size_gb,
            "total_files": total_files,
        }


class DomainSpecializationLayer:
    """Maps project characteristics to domain-aware strategies."""

    def __init__(self) -> None:
        self.allocator = PatternResourceAllocator()
        self.profiles = {
            "frontend": DomainProfile(
                name="frontend",
                languages=["ts", "tsx", "js", "jsx", "css", "html"],
                cache_entries=1024,
                ttl_seconds=900,
                memory_priority="high",
                agent_roles=[AgentRole.ANALYST, AgentRole.EXECUTOR, AgentRole.CHECKER],
                base_workers=6,
                memory_multiplier=1.2,
                description="UI-heavy projects favor shorter TTLs and more parallel parsing.",
            ),
            "backend": DomainProfile(
                name="backend",
                languages=["py", "rs", "go", "java"],
                cache_entries=2048,
                ttl_seconds=3600,
                memory_priority="normal",
                agent_roles=[AgentRole.PLANNER, AgentRole.EXECUTOR, AgentRole.REVISER],
                base_workers=4,
                memory_multiplier=1.0,
                description="Server-side code benefits from deeper cache and balanced workers.",
            ),
            "data": DomainProfile(
                name="data",
                languages=["sql", "ipynb", "r", "csv"],
                cache_entries=1536,
                ttl_seconds=1800,
                memory_priority="high",
                agent_roles=[AgentRole.ANALYST, AgentRole.RESEARCHER, AgentRole.COORDINATOR],
                base_workers=5,
                memory_multiplier=1.4,
                description="ETL workloads skew towards higher memory footprints.",
            ),
            "docs": DomainProfile(
                name="docs",
                languages=["md", "rst"],
                cache_entries=512,
                ttl_seconds=600,
                memory_priority="low",
                agent_roles=[AgentRole.WRITER, AgentRole.REVISER],
                base_workers=2,
                memory_multiplier=0.8,
                description="Documentation parsing favors smaller caches.",
            ),
            "general": DomainProfile(
                name="general",
                languages=[],
                cache_entries=unified_config.project_analysis.ast_cache_entries,
                ttl_seconds=unified_config.project_analysis.ast_cache_ttl_seconds,
                memory_priority="normal",
                agent_roles=[AgentRole.PLANNER, AgentRole.EXECUTOR],
                base_workers=3,
                memory_multiplier=1.0,
                description="Fallback profile for mixed workloads.",
            ),
        }

    def plan_for_project(
        self,
        *,
        file_stats: Dict[str, int],
        project_size_bytes: int,
        domain_override: Optional[str] = None,
    ) -> SpecializationPlan:
        domain_key = domain_override or self._infer_domain(file_stats)
        profile = self.profiles.get(domain_key, self.profiles["general"])
        resource_budget = self.allocator.compute(profile, file_stats, project_size_bytes)
        cache_multiplier = resource_budget["memory_multiplier"]
        cache_overrides = {
            "max_entries": int(profile.cache_entries * cache_multiplier),
            "ttl_seconds": profile.ttl_seconds,
        }

        logger.debug(
            "Specialization plan: domain=%s cache=%s resources=%s",
            profile.name,
            cache_overrides,
            resource_budget,
        )

        return SpecializationPlan(
            domain=profile.name,
            memory_priority=profile.memory_priority,
            cache_overrides=cache_overrides,
            agent_roles=[role.value for role in profile.agent_roles],
            resource_budget=resource_budget,
        )

    def _infer_domain(self, file_stats: Dict[str, int]) -> str:
        if not file_stats:
            return "general"

        dominant_ext = max(file_stats.items(), key=lambda item: item[1])[0]
        for key, profile in self.profiles.items():
            if dominant_ext in profile.languages:
                return key
        return "general"
