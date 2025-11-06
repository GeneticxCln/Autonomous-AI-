from __future__ import annotations

import argparse
import json
import logging
import shlex
from typing import Optional

from .agent import AutonomousAgent

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def run_interactive(max_cycles: int = 100) -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    agent = AutonomousAgent()

    print("Terminal Agent (interactive)")
    print("Commands: add <desc>::<prio> | step | run <n> | status | goals | tools | stop | quit")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nexit")
            break
        if not raw:
            continue

        try:
            parts = shlex.split(raw)
        except ValueError:
            print("parse error")
            continue

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "quit" or cmd == "exit":
            break
        elif cmd == "add":
            if not args:
                print("usage: add <description>::<priority>")
                continue
            goal_arg = " ".join(args)
            if "::" in goal_arg:
                desc, prio = goal_arg.split("::", 1)
                try:
                    pr = float(prio)
                except ValueError:
                    pr = 0.5
            else:
                desc, pr = goal_arg, 0.5
            g = agent.add_goal(desc, priority=max(0.0, min(pr, 1.0)))
            print(f"added: {g.id} :: {g.description} :: {g.priority}")
        elif cmd == "run":
            n = int(args[0]) if args else max_cycles
            agent.run(max_cycles=n)
            print("done")
        elif cmd == "step":
            worked = agent.run_cycle()
            print("worked" if worked else "idle")
        elif cmd == "status":
            s = agent.get_status()
            print(json.dumps(s, indent=2, default=str))
        elif cmd == "goals":
            s = agent.get_status()["goals"]
            print(json.dumps(s, indent=2, default=str))
        elif cmd == "tools":
            tools = agent.tool_registry.get_available_tools()
            stats = agent.tool_registry.get_tool_stats()
            out = {"tools": tools, "stats": stats}
            print(json.dumps(out, indent=2, default=str))
        elif cmd == "stop":
            agent.stop()
            print("stopped")
        else:
            print("unknown command")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="terminal_agent", add_help=True)
    parser.add_argument("--max-cycles", type=int, default=100)
    args = parser.parse_args(argv)
    run_interactive(max_cycles=args.max_cycles)