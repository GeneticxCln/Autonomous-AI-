from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _load_yaml(path: Path) -> Dict[str, Any] | None:
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.warning("Failed to parse YAML %s: %s", path, e)
        return {}


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.warning("Failed to parse JSON %s: %s", path, e)
        return {}


def _instantiate(class_path: str) -> Any:
    mod_name, _, cls_name = class_path.rpartition(".")
    if not mod_name:
        raise ImportError(f"Invalid class path: {class_path}")
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    return cls()


def load_plugins(agent: Any, config_path: str | None = None) -> Dict[str, Any]:
    """Load custom tools and goals from a plugins config file.

    Supports .yaml/.yml or .json with schema:
    tools:
      - class: agent_system.real_tools.RealWebSearchTool
        enabled: true
      - class: mypkg.tools.CustomTool
        enabled: true
    goals:
      - description: "Improve test coverage"
        priority: 0.8
    """
    root = Path(".")
    path = Path(config_path) if config_path else None
    if not path:
        for name in (".agent_plugins.yaml", ".agent_plugins.yml", ".agent_plugins.json"):
            p = root / name
            if p.exists():
                path = p
                break
    if not path or not path.exists():
        return {"loaded": False, "reason": "no_config"}

    cfg: Dict[str, Any]
    if path.suffix.lower() in (".yaml", ".yml"):
        cfg = _load_yaml(path) or {}
    else:
        cfg = _load_json(path)

    tools = cfg.get("tools", []) or []
    registered = []
    for tool_def in tools:
        if not isinstance(tool_def, dict) or not tool_def.get("class"):
            continue
        if tool_def.get("enabled") is False:
            continue
        try:
            inst = _instantiate(tool_def["class"])
            agent.tool_registry.register_tool(inst)
            registered.append(inst.name if hasattr(inst, "name") else tool_def["class"])
        except Exception as e:
            logger.warning("Failed to load tool %s: %s", tool_def.get("class"), e)

    goals = cfg.get("goals", []) or []
    added_goals = []
    for g in goals:
        if not isinstance(g, dict) or not g.get("description"):
            continue
        prio = float(g.get("priority", 0.5))
        goal = agent.add_goal(g["description"], prio)
        added_goals.append(goal.id)

    return {
        "loaded": True,
        "tools_registered": registered,
        "goals_added": added_goals,
        "config": str(path),
    }
