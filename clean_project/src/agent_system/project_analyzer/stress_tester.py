"""Stress testing utilities for large project analysis."""

from __future__ import annotations

import random
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .large_project_analyzer import AnalyzerReport, LargeProjectAnalyzer, large_project_analyzer
from .orchestrator_integration import apply_specialization_plan_to_registry
from .specialization import SpecializationPlan
from ..multi_agent_system import MultiAgentOrchestrator


@dataclass
class StressScenarioMetrics:
    label: str
    file_count: int
    duration_ms: float
    cache_hits: int
    cache_misses: int
    failures: int
    specialization: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StressTestResult:
    growth: List[StressScenarioMetrics] = field(default_factory=list)
    failure_cascade: Optional[StressScenarioMetrics] = None
    recovery_time_ms: Optional[float] = None


class ProjectStressTester:
    """Runs synthetic stress scenarios to validate analyzer resilience."""

    def __init__(
        self,
        analyzer: Optional[LargeProjectAnalyzer] = None,
        orchestrator: Optional[MultiAgentOrchestrator] = None,
    ):
        self.analyzer = analyzer or large_project_analyzer
        self.orchestrator = orchestrator

    def simulate_growth(
        self,
        project_id: str,
        counts: List[int],
        *,
        language: str = "python",
    ) -> List[StressScenarioMetrics]:
        metrics: List[StressScenarioMetrics] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for count in counts:
                self._generate_project_files(root, count, language=language)
                report = self.analyzer.prime_cache(
                    project_id,
                    root,
                    version=f"v{count}",
                    max_files=count,
                )
                self._apply_specialization_plan(report)
                metrics.append(
                    StressScenarioMetrics(
                        label=f"growth_{count}",
                        file_count=count,
                        duration_ms=report.duration_ms,
                        cache_hits=report.cache_hits,
                        cache_misses=report.cache_misses,
                        failures=len(report.failures),
                        specialization=report.specialization_plan or {},
                    )
                )
        return metrics

    def simulate_failure_cascade(
        self,
        project_id: str,
        file_count: int,
        *,
        failure_ratio: float = 0.1,
    ) -> StressScenarioMetrics:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._generate_project_files(
                root,
                file_count,
                invalid_ratio=failure_ratio,
            )
            report = self.analyzer.prime_cache(
                project_id,
                root,
                version="failure",
                max_files=file_count,
            )
            self._apply_specialization_plan(report)
            return StressScenarioMetrics(
                label="failure_cascade",
                file_count=file_count,
                duration_ms=report.duration_ms,
                cache_hits=report.cache_hits,
                cache_misses=report.cache_misses,
                failures=len(report.failures),
                specialization=report.specialization_plan or {},
            )

    def measure_recovery_time(self, project_id: str, file_count: int) -> float:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._generate_project_files(root, file_count)

            # first run to populate cache
            baseline_report = self.analyzer.prime_cache(
                project_id, root, version="baseline", max_files=file_count
            )
            self._apply_specialization_plan(baseline_report)

            # simulate memory pressure by flushing cache
            self.analyzer.kernel_cache.invalidate(project_id)
            start = time.perf_counter()
            recovery_report = self.analyzer.prime_cache(
                project_id, root, version="recovery", max_files=file_count
            )
            self._apply_specialization_plan(recovery_report)
            return (time.perf_counter() - start) * 1000

    def run_all(self, project_id: str) -> StressTestResult:
        growth_metrics = self.simulate_growth(project_id, [100, 500, 1000])
        failure_metrics = self.simulate_failure_cascade(project_id, 300, failure_ratio=0.2)
        recovery = self.measure_recovery_time(project_id, 400)
        return StressTestResult(
            growth=growth_metrics,
            failure_cascade=failure_metrics,
            recovery_time_ms=recovery,
        )

    def _apply_specialization_plan(self, report: Optional[AnalyzerReport]):
        if not self.orchestrator or not report:
            return
        plan_data = report.specialization_plan
        if not plan_data:
            return
        try:
            plan = SpecializationPlan(**plan_data)
        except TypeError:
            return
        apply_specialization_plan_to_registry(plan, self.orchestrator.agent_registry)

    def _generate_project_files(
        self,
        root: Path,
        count: int,
        *,
        language: str = "python",
        invalid_ratio: float = 0.0,
    ):
        root.mkdir(exist_ok=True, parents=True)
        for idx in range(count):
            file_path = root / f"module_{idx}.py"
            if language != "python":
                file_path = root / f"asset_{idx}.{language}"
            invalid = random.random() < invalid_ratio
            content = self._sample_content(language, invalid=invalid, idx=idx)
            file_path.write_text(content, encoding="utf-8")

    def _sample_content(self, language: str, *, invalid: bool, idx: int) -> str:
        if language == "python":
            if invalid:
                return f"def broken(idx={idx}\n    return idx\n"
            return f"def func_{idx}():\n    return {idx}\n"
        if language in {"js", "ts"}:
            if invalid:
                return f"function broken({idx} {{ return; "
            return f"export function fn{idx}() {{ return {idx}; }}\n"
        return f"# asset {idx}\n"
