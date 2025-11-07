from __future__ import annotations

import argparse
import json
import logging
import os
from collections.abc import Sequence
from typing import Any, Dict, Optional, Tuple

from .agent import AutonomousAgent
from .auth_models import SecurityContext, db_manager
from .auth_service import auth_service
from .fastapi_app import app

# Version information
__version__ = "1.0.0"


# System configuration
class Config:
    """Application configuration."""

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./agent_enterprise.db")
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", "your-super-secret-jwt-key-change-in-production"
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60
    MAX_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_DURATION: int = 30
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_WORKERS: int = int(os.getenv("API_WORKERS", "1"))
    API_DEBUG: bool = os.getenv("API_DEBUG", "false").lower() == "true"
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")


config = Config()


# Configure logging
def _configure_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()

    # Configure enterprise-grade logging
    if not root_logger.handlers:
        logging.basicConfig(
            level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    else:
        root_logger.setLevel(level)
        for handler in root_logger.handlers:
            handler.setLevel(level)

    # Log system initialization
    logger = logging.getLogger(__name__)
    logger.info(f"🚀 Agent Enterprise System v{__version__} initialized")
    logger.info(f"📊 Database: {config.DATABASE_URL}")
    logger.info(
        f"🔐 JWT Secret: {'*' * (len(config.JWT_SECRET_KEY) - 4) + config.JWT_SECRET_KEY[-4:] if len(config.JWT_SECRET_KEY) > 4 else '***'}"
    )
    logger.info(f"🌍 Environment: {config.ENVIRONMENT}")
    logger.info(f"🔗 API Server: {config.API_HOST}:{config.API_PORT}")


__all__ = [
    "AutonomousAgent",
    "main",
    "app",
    "auth_service",
    "db_manager",
    "SecurityContext",
    "Config",
    "config",
    "__version__",
]

DEFAULT_GOALS: Tuple[Tuple[str, float], ...] = (
    ("Research machine learning trends", 0.8),
    ("Analyze sales data", 0.6),
    ("Create project report", 0.9),
)


def _parse_goal_argument(goal_arg: str) -> Tuple[str, float]:
    if "::" in goal_arg:
        description, priority_token = goal_arg.split("::", 1)
        try:
            priority = float(priority_token)
        except ValueError as exc:  # pragma: no cover - defensive branch
            raise argparse.ArgumentTypeError(
                f"Invalid priority '{priority_token}' for goal '{goal_arg}'"
            ) from exc
        return description.strip(), max(0.0, min(priority, 1.0))

    return goal_arg.strip(), 0.5


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Run the agent workflow with optional CLI arguments and return the final status."""
    parser = argparse.ArgumentParser(
        prog="agent_system",
        description="Run the autonomous agent demo.",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=20,
        help="Maximum number of agent cycles to execute (default: 20).",
    )
    parser.add_argument(
        "--goal",
        action="append",
        default=[],
        metavar="DESCRIPTION[::PRIORITY]",
        help="Add a goal; may be repeated. Append '::priority' to override default 0.5 priority.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Root logging level (default: INFO).",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run interactive terminal agent (REPL).",
    )

    args = parser.parse_args(argv)

    _configure_logging(args.log_level)

    if args.interactive:
        # Defer to interactive CLI
        from .terminal_cli import run_interactive

        run_interactive(max_cycles=args.max_cycles)
        # After interactive exits, also return the final status (if any)
        # Provide an empty baseline structure when interactive is used
        return {
            "current_goal": None,
            "goals": {"goals": []},
            "memory_stats": {
                "working_memory_size": 0,
                "episodic_memory_size": 0,
                "total_memories": 0,
                "avg_success_score": 0.0,
            },
            "tool_stats": {},
            "learning_stats": {
                "strategies_learned": 0,
                "patterns_learned": 0,
                "total_episodes": 0,
                "best_strategies": {},
            },
            "is_running": False,
        }

    agent = AutonomousAgent()

    if args.goal:
        parsed_goals = [_parse_goal_argument(goal_str) for goal_str in args.goal]
    else:
        parsed_goals = list(DEFAULT_GOALS)

    for description, priority in parsed_goals:
        agent.add_goal(description, priority=priority)

    agent.run(max_cycles=args.max_cycles)

    status = agent.get_status()
    print("\n" + "=" * 80)
    print("AGENT STATUS")
    print("=" * 80)
    print(json.dumps(status, indent=2, default=str))

    return status
