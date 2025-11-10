"""CLI utility to run large-project stress tests."""

from __future__ import annotations

import argparse
import json

from agent_system.multi_agent_system import MultiAgentOrchestrator
from agent_system.project_analyzer import ProjectStressTester


def parse_counts(value: str) -> list[int]:
    return [int(token.strip()) for token in value.split(",") if token.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run large-project analyzer stress tests")
    parser.add_argument("--project-id", default="stress_suite", help="Logical project identifier")
    parser.add_argument(
        "--growth-counts",
        default="100,500,1000",
        help="Comma separated file counts for growth simulation",
    )
    parser.add_argument(
        "--failure-count",
        type=int,
        default=500,
        help="File count used for failure cascade scenario",
    )
    parser.add_argument(
        "--failure-ratio",
        type=float,
        default=0.2,
        help="Ratio (0-1) of files that should be invalid during failure simulation",
    )
    parser.add_argument(
        "--recovery-count",
        type=int,
        default=600,
        help="File count used for recovery benchmark",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "growth", "failure", "recovery"],
        default="all",
        help="Select which scenario to execute",
    )

    parser.add_argument(
        "--with-orchestrator",
        action="store_true",
        help="Enable multi-agent registry integration for specialization plans",
    )

    args = parser.parse_args()
    orchestrator = MultiAgentOrchestrator() if args.with_orchestrator else None
    tester = ProjectStressTester(orchestrator=orchestrator)

    output: dict = {"project_id": args.project_id, "mode": args.mode}
    if args.mode in {"all", "growth"}:
        growth_metrics = tester.simulate_growth(args.project_id, parse_counts(args.growth_counts))
        output["growth"] = [metric.__dict__ for metric in growth_metrics]

    if args.mode in {"all", "failure"}:
        failure_metrics = tester.simulate_failure_cascade(
            args.project_id,
            args.failure_count,
            failure_ratio=args.failure_ratio,
        )
        output["failure_cascade"] = failure_metrics.__dict__

    if args.mode in {"all", "recovery"}:
        recovery_ms = tester.measure_recovery_time(args.project_id, args.recovery_count)
        output["recovery_time_ms"] = recovery_ms

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
