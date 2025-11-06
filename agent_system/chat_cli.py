from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
import os

from .llm_integration import llm_manager
from .enhanced_tools import EnhancedToolRegistry
from .models import Action
from .config_simple import settings
from .config_simple import validate_file_path
from .vector_memory import SimpleVectorMemory
from .todo_store import SimpleTodoStore
from .tools import GenericTool, FileReaderTool, FileWriterTool, CodeExecutorTool, ShellTool, CodeSearchTool, EditFileTool, ReplaceInFilesTool, RestoreBackupTool, GitTool, TestTool, FormatTool, LintTool

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
STATE_DIR = Path(".agent_state/chat_sessions")
STATE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_TOOLS = {"code_executor", "file_reader", "file_writer", "shell", "code_search", "edit_file", "replace_in_files", "restore_backup", "git", "tests", "format", "lint"}

SYSTEM_PROMPT = (
    "You are a terminal agent. Respond concisely. "
    "When a tool is needed, output ONLY a compact JSON on a single line with one of: "
    "1) {\"type\":\"tool\",\"tool\":(code_executor|file_reader|file_writer|shell|code_search|git|edit_file|replace_in_files|restore_backup|tests),\"args\":{...}} "
    "2) {\"type\":\"tool_batch\",\"calls\":[{\"tool\":...,\"args\":{...}}, ...]} (max 5 calls). "
    "For shell: args {cmd: <ls|cat|head|tail|wc|grep|stat|pwd|echo>, args: [<tokens>]}. "
    "For code_search: args {pattern: <regex>, path: '.', include?: pattern|[...], exclude?: pattern|[...], max_results?: N}. "
    "For git: args {cmd: <status|log|diff>, n?: <1..100>, path?: <path>, range?: <rev..rev>}. "
    "For tests: args {path?: 'tests', pattern?: 'test*.py'}. "
    "Otherwise, output plain text. No markdown fences."
)

@dataclass
class ChatState:
    provider: str = "local"
    messages: List[Dict[str, str]] = field(default_factory=list)
    tool_registry: EnhancedToolRegistry = field(default_factory=EnhancedToolRegistry)
    summary: str = ""
    max_tool_loops: int = 4
    max_messages: int = 200
    pinned: List[str] = field(default_factory=list)
    last_plan: Optional[List[Dict[str, Any]]] = None
    aliases: Dict[str, Any] = field(default_factory=dict)

    def add_system(self, content: str):
        self.messages.append({"role": "system", "content": content})

    def add_user(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str):
        self.messages.append({"role": "assistant", "content": content})


def save_session(state: ChatState) -> Path:
    path = STATE_DIR / ("session_" + str(len(list(STATE_DIR.glob("session_*.json"))) + 1) + ".json")
    with path.open("w", encoding="utf-8") as f:
        json.dump({"provider": state.provider, "messages": state.messages, "summary": state.summary}, f, indent=2)
    return path


def sanitize_tool_call(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tool = data.get("tool")
    if tool not in ALLOWED_TOOLS:
        return None
    args = data.get("args", {})
    if not isinstance(args, dict):
        return None
    # Basic arg coercion
    if tool == "code_executor":
        code = args.get("code", "")
        if not isinstance(code, str) or not code.strip():
            return None
        lang = str(args.get("language", "python")).lower()
        if lang not in {"python", "bash", "shell"}:
            lang = "python"
        timeout = int(args.get("timeout", settings.CODE_EXECUTION_TIMEOUT))
        args = {"code": code, "language": lang, "timeout": timeout}
    elif tool == "file_reader":
        fp = str(args.get("filepath", "")).strip()
        if not fp:
            return None
        fmt = str(args.get("format", "auto")).lower()
        args = {"filepath": fp, "format": fmt}
    elif tool == "file_writer":
        fp = str(args.get("filepath", "")).strip()
        if not fp:
            return None
        content = args.get("content", "")
        fmt = str(args.get("format", "text")).lower()
        args = {"filepath": fp, "content": content, "format": fmt}
    elif tool == "shell":
        cmd = str(args.get("cmd", "")).lower().strip()
        arg_list = args.get("args", [])
        if not cmd:
            return None
        if not isinstance(arg_list, list):
            return None
        args = {"cmd": cmd, "args": [str(x) for x in arg_list]}
    elif tool == "edit_file":
        path = str(args.get("path", "")).strip()
        search = args.get("search")
        replace = args.get("replace")
        once = bool(args.get("once", True))
        if not path or search is None or replace is None:
            return None
        args = {"path": path, "search": str(search), "replace": str(replace), "once": once}
    elif tool == "replace_in_files":
        path = str(args.get("path", ".")).strip()
        search = args.get("search")
        replace = args.get("replace", "")
        include = args.get("include", ["**/*"]) 
        exclude = args.get("exclude", [".git/*", "*.pyc", "node_modules/*"]) 
        max_edits = int(args.get("max_edits", 1000))
        if not search:
            return None
        args = {"path": path, "search": str(search), "replace": str(replace), "include": include, "exclude": exclude, "max_edits": max_edits}
    elif tool == "restore_backup":
        latest = bool(args.get("latest", True))
        backup = args.get("backup")
        args = {"latest": latest, "backup": backup}
    elif tool == "git":
        cmd = str(args.get("cmd", "")).lower().strip()
        if cmd not in {"status", "log", "diff"}:
            return None
        out: Dict[str, Any] = {"cmd": cmd}
        if cmd == "log":
            try:
                out["n"] = max(1, min(100, int(args.get("n", 10))))
            except Exception:
                out["n"] = 10
        if cmd == "diff":
            rng = args.get("range")
            path = args.get("path")
            if isinstance(rng, str):
                out["range"] = rng
            if isinstance(path, str):
                out["path"] = path
        args = out
    data["args"] = args
    return data


def summarize(messages: List[Dict[str, str]], limit: int = 500) -> str:
    # Naive summarizer: keep last user+assistant sentences, truncate
    chunks: List[str] = []
    for m in messages[-10:]:
        if m["role"] in ("user", "assistant"):
            txt = m.get("content", "").strip().replace("\n", " ")
            if txt:
                prefix = "U:" if m["role"] == "user" else "A:"
                chunks.append(f"{prefix} {txt}")
    text = " | ".join(chunks)
    return (text[:limit] + ("…" if len(text) > limit else ""))


def _extract_json_block(text: str) -> Optional[str]:
    # Try fenced blocks first
    try:
        import re
        m = re.search(r"```(?:json)?\s*({[\s\S]*?})\s*```", text, re.IGNORECASE)
        if m:
            return m.group(1)
    except Exception:
        pass
    # Naive brace matching (best-effort) to find first JSON object
    s = text
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, min(len(s), start + 10000)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return s[start : i + 1]
    return None


def _sanitize_batch(calls: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    sanitized: List[Dict[str, Any]] = []
    if not isinstance(calls, list):
        return None
    for item in calls[:5]:
        if not isinstance(item, dict):
            return None
        tool = item.get("tool")
        args = item.get("args", {})
        if not tool:
            return None
        d = {"type": "tool", "tool": tool, "args": args}
        s = sanitize_tool_call(d)
        if not s:
            return None
        sanitized.append(s)
    return sanitized


def parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()
    # Direct JSON
    candidates: list[str] = []
    if text.startswith("{") and text.endswith("}"):
        candidates.append(text)
    block = _extract_json_block(text)
    if block:
        candidates.append(block)
    for cand in candidates:
        try:
            data = json.loads(cand)
            if data.get("type") == "tool":
                return sanitize_tool_call(data)
            if data.get("type") == "tool_batch":
                calls = _sanitize_batch(data.get("calls", []))
                if calls is not None:
                    return {"type": "tool_batch", "calls": calls}
        except Exception:
            continue
    return None


async def run_chat(provider: str = "local", stream: bool = True):
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL), format=LOG_FORMAT)
    state = ChatState(provider=provider)
    memory = SimpleVectorMemory()
    todos = SimpleTodoStore()

    # Register terminal tools
    state.tool_registry.register_tool(GenericTool())
    state.tool_registry.register_tool(FileReaderTool())
    state.tool_registry.register_tool(FileWriterTool())
    state.tool_registry.register_tool(CodeExecutorTool())
    state.tool_registry.register_tool(ShellTool())
    state.tool_registry.register_tool(CodeSearchTool())
    state.tool_registry.register_tool(EditFileTool())
    state.tool_registry.register_tool(ReplaceInFilesTool())
    state.tool_registry.register_tool(RestoreBackupTool())
    state.tool_registry.register_tool(GitTool())
    state.tool_registry.register_tool(TestTool())
    state.tool_registry.register_tool(FormatTool())
    state.tool_registry.register_tool(LintTool())

    # Enable real tool implementations where available (code_executor, file_reader, file_writer)
    if getattr(settings, "USE_REAL_TOOLS", True):
        state.tool_registry.enable_real_tools()

    state.add_system(SYSTEM_PROMPT)
    print("Terminal Chat Agent. Type 'exit' to quit. /help for commands.")

    current_provider = provider
    redact_output = True

    # Add file logger
    fh = logging.FileHandler(".agent_state/chat.log")
    fh.setLevel(getattr(logging, settings.LOG_LEVEL))
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.getLogger().addHandler(fh)

    while True:
        try:
            user = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user.lower() in {"exit", "quit"}:
            break

        # Slash commands
        if user.startswith("/"):
            cmd, *rest = user[1:].split()
            if cmd == "help":
                print("/provider <openai|anthropic|local>  /reset  /mem  /save  /load <path>  /loops <n>  /max <n>  /tool {json}  /context  /real <on|off>  /tools  /stats  /git ...  /tests  /format [path]  /lint [path]  /lintfix [path]  /undo  /backups  /todo add <text> [prio]  /todo ls  /todo done <id>  /todo clear  /redact <on|off>  /dump  /py <code>  /sh <cmd>  /ls [path]  /pwd  /cd <path>  /cat <path>  /write <path> <content>  /searchmem <regex>  /pin <text>  /unpin  /alias <name> {json}  /aliases  /unalias <name>  /run <name>  /plan <goal>  /runplan")
                continue
            if cmd == "provider" and rest:
                cand = rest[0].lower()
                if cand in {"openai", "anthropic", "local"}:
                    current_provider = cand
                    print(f"provider={current_provider}")
                else:
                    print("invalid provider")
                continue
            if cmd == "reset":
                state.messages = []
                state.add_system(SYSTEM_PROMPT)
                # re-apply pinned
                for p in state.pinned:
                    state.add_system(p)
                print("reset")
                continue
            if cmd == "context":
                print(f"messages={len(state.messages)} summary_len={len(state.summary)} provider={current_provider}")
                continue
            if cmd == "loops" and rest:
                try:
                    n = max(1, min(10, int(rest[0])))
                    state.max_tool_loops = n
                    print(f"loops={n}")
                except ValueError:
                    print("invalid number")
                continue
            if cmd == "max" and rest:
                try:
                    n = max(20, min(2000, int(rest[0])))
                    state.max_messages = n
                    print(f"max_messages={n}")
                except ValueError:
                    print("invalid number")
                continue
            if cmd == "tool" and rest:
                raw = " ".join(rest)
                try:
                    obj = json.loads(raw)
                except Exception:
                    print("invalid json")
                    continue
                tool = parse_tool_call(json.dumps(obj))
                if not tool:
                    print("invalid tool call")
                    continue
                if tool.get("type") == "tool_batch":
                    for call in tool.get("calls", []):
                        tool_name = call.get("tool")
                        args = call.get("args", {})
                        action = Action(id="manual_tool", name=tool_name, tool_name=tool_name, parameters=args, expected_outcome="tool_executed", cost=0.1)
                        observation = state.tool_registry.execute_action(action)
                        print(json.dumps({"tool": tool_name, "status": observation.status.value, "result": observation.result}, indent=2))
                else:
                    tool_name = tool.get("tool")
                    args = tool.get("args", {})
                    action = Action(
                        id="manual_tool",
                        name=tool_name,
                        tool_name=tool_name,
                        parameters=args,
                        expected_outcome="tool_executed",
                        cost=0.1,
                    )
                    observation = state.tool_registry.execute_action(action)
                    print(json.dumps({"status": observation.status.value, "result": observation.result}, indent=2))
                continue
            if cmd == "mem":
                top = memory.query("*", top_k=5)
                for score, it in top:
                    print(f"{score:.2f} {it.meta.get('type','mem')}: {it.text[:120]}")
                continue
            if cmd == "alias" and len(rest) >= 2:
                name = rest[0]
                raw = user.split(" ", 2)[2]
                try:
                    obj = json.loads(raw)
                except Exception:
                    print("invalid json")
                    continue
                tool = parse_tool_call(json.dumps(obj))
                if not tool:
                    print("invalid tool or tool_batch json")
                    continue
                state.aliases[name] = tool
                print(f"aliased {name}")
                continue
            if cmd == "aliases":
                print("aliases:", ", ".join(sorted(state.aliases.keys())))
                continue
            if cmd == "unalias" and rest:
                name = rest[0]
                if name in state.aliases:
                    del state.aliases[name]
                    print("unalised")
                else:
                    print("not found")
                continue
            if cmd == "run" and rest:
                name = rest[0]
                tool = state.aliases.get(name)
                if not tool:
                    print("not found")
                    continue
                # Reuse manual execution path
                if tool.get("type") == "tool_batch":
                    for call in tool.get("calls", []):
                        tool_name = call.get("tool")
                        args = call.get("args", {})
                        action = Action(id="alias_tool", name=tool_name, tool_name=tool_name, parameters=args, expected_outcome="tool_executed", cost=0.1)
                        observation = state.tool_registry.execute_action(action)
                        print(json.dumps({"tool": tool_name, "status": observation.status.value, "result": observation.result}, indent=2))
                else:
                    tool_name = tool.get("tool")
                    args = tool.get("args", {})
                    action = Action(id="alias_tool", name=tool_name, tool_name=tool_name, parameters=args, expected_outcome="tool_executed", cost=0.1)
                    observation = state.tool_registry.execute_action(action)
                    print(json.dumps({"status": observation.status.value, "result": observation.result}, indent=2))
                continue
            if cmd == "plan" and rest:
                goal = user.split(" ", 1)[1]
                planner_prompt = (
                    "Plan a minimal tool batch to accomplish the goal. Output ONLY JSON with schema: "
                    "{\"type\":\"tool_batch\",\"calls\":[{\"tool\":...,\"args\":{...}}]}"
                )
                tmp_msgs = state.messages + [{"role": "system", "content": planner_prompt}, {"role": "user", "content": goal}]
                plan_text = await llm_manager.chat(tmp_msgs, provider=current_provider)
                plan_obj = parse_tool_call(plan_text)
                if not plan_obj or plan_obj.get("type") != "tool_batch":
                    print("planning failed")
                    continue
                state.last_plan = plan_obj.get("calls", [])
                print(json.dumps({"planned": state.last_plan}, indent=2))
                continue
            if cmd == "runplan":
                if not state.last_plan:
                    print("no last plan")
                    continue
                for call in state.last_plan[:5]:
                    tool_name = call.get("tool")
                    args = call.get("args", {})
                    action = Action(id="runplan_tool", name=tool_name, tool_name=tool_name, parameters=args, expected_outcome="tool_executed", cost=0.1)
                    observation = state.tool_registry.execute_action(action)
                    print(json.dumps({"tool": tool_name, "status": observation.status.value, "result": observation.result}, indent=2))
                continue
            if cmd == "py" and rest:
                code = user.split(" ", 1)[1]
                action = Action(id="py", name="code_executor", tool_name="code_executor", parameters={"language": "python", "code": code, "timeout": settings.CODE_EXECUTION_TIMEOUT}, expected_outcome="ok", cost=0.1)
                obs = state.tool_registry.execute_action(action)
                print(json.dumps({"status": obs.status.value, "result": obs.result}, indent=2))
                continue
            if cmd == "sh" and rest:
                shcode = user.split(" ", 1)[1]
                action = Action(id="sh", name="code_executor", tool_name="code_executor", parameters={"language": "bash", "code": shcode, "timeout": settings.CODE_EXECUTION_TIMEOUT}, expected_outcome="ok", cost=0.1)
                obs = state.tool_registry.execute_action(action)
                print(json.dumps({"status": obs.status.value, "result": obs.result}, indent=2))
                continue
            if cmd == "ls":
                pth = rest[0] if rest else "."
                action = Action(id="ls", name="shell", tool_name="shell", parameters={"cmd": "ls", "args": [pth]}, expected_outcome="ok", cost=0.02)
                obs = state.tool_registry.execute_action(action)
                print(json.dumps({"status": obs.status.value, "result": obs.result}, indent=2))
                continue
            if cmd == "pwd":
                action = Action(id="pwd", name="shell", tool_name="shell", parameters={"cmd": "pwd", "args": []}, expected_outcome="ok", cost=0.01)
                obs = state.tool_registry.execute_action(action)
                print(json.dumps({"status": obs.status.value, "result": obs.result}, indent=2))
                continue
            if cmd == "cd" and rest:
                pth = rest[0]
                if not validate_file_path(pth):
                    print("path not allowed")
                    continue
                try:
                    os.chdir(pth)
                    print(f"cwd={os.getcwd()}")
                except Exception as e:
                    print(f"cd error: {e}")
                continue
            if cmd == "cat" and rest:
                pth = rest[0]
                action = Action(id="cat", name="file_reader", tool_name="file_reader", parameters={"filepath": pth, "format": "auto"}, expected_outcome="ok", cost=0.05)
                obs = state.tool_registry.execute_action(action)
                print(json.dumps({"status": obs.status.value, "result": obs.result}, indent=2))
                continue
            if cmd == "write" and len(rest) >= 2:
                pth = rest[0]
                content = user.split(" ", 2)[2]
                action = Action(id="write", name="file_writer", tool_name="file_writer", parameters={"filepath": pth, "content": content, "format": "text"}, expected_outcome="ok", cost=0.05)
                obs = state.tool_registry.execute_action(action)
                print(json.dumps({"status": obs.status.value, "result": obs.result}, indent=2))
                continue
            if cmd == "searchmem" and rest:
                import re as _re
                patt = " ".join(rest)
                try:
                    rx = _re.compile(patt, _re.IGNORECASE)
                except Exception:
                    print("invalid regex")
                    continue
                hits = []
                for it in memory.items:
                    if rx.search(it.text):
                        hits.append(it)
                    if len(hits) >= 10:
                        break
                for i, it in enumerate(hits, 1):
                    print(f"{i}. {it.meta.get('type','mem')}: {it.text[:200]}")
                continue
            if cmd == "pin" and rest:
                text_pin = user.split(" ", 1)[1]
                state.pinned.append(text_pin)
                state.add_system(text_pin)
                print("pinned")
                continue
            if cmd == "unpin":
                state.pinned = []
                print("unpinned")
                continue
            if cmd == "save":
                p = save_session(state)
                print(f"saved {p}")
                continue
            if cmd == "load" and rest:
                path = Path(rest[0])
                if path.exists():
                    obj = json.loads(path.read_text())
                    state.provider = obj.get("provider", state.provider)
                    state.messages = obj.get("messages", [])
                    print(f"loaded {path}")
                else:
                    print("not found")
                continue
            if cmd == "real" and rest:
                mode = rest[0].lower()
                if mode in {"on", "true", "1"}:
                    state.tool_registry.enable_real_tools()
                    print("real_tools=on")
                elif mode in {"off", "false", "0"}:
                    state.tool_registry.disable_real_tools()
                    print("real_tools=off")
                else:
                    print("usage: /real <on|off>")
                continue
            if cmd == "tools":
                names = state.tool_registry.get_available_tools()
                print("tools:", ", ".join(names))
                continue
            if cmd == "stats":
                print(json.dumps(state.tool_registry.get_tool_stats(), indent=2))
                continue
            if cmd == "git":
                # convenience wrapper: /git status | /git log 20 | /git diff [path]
                if not rest:
                    print("usage: /git <status|log N|diff [path] [range]>")
                    continue
                sub = rest[0].lower()
                params: Dict[str, Any] = {"cmd": "status"}
                if sub == "status":
                    params = {"cmd": "status"}
                elif sub == "log":
                    n = 10
                    if len(rest) > 1:
                        try:
                            n = int(rest[1])
                        except Exception:
                            n = 10
                    params = {"cmd": "log", "n": n}
                elif sub == "diff":
                    pth = rest[1] if len(rest) > 1 else None
                    rng = rest[2] if len(rest) > 2 else None
                    params = {"cmd": "diff"}
                    if pth:
                        params["path"] = pth
                    if rng:
                        params["range"] = rng
                else:
                    print("unknown git subcmd")
                    continue
                action = Action(id="git_cmd", name="git", tool_name="git", parameters=params, expected_outcome="git_ok", cost=0.05)
                obs = state.tool_registry.execute_action(action)
                print(json.dumps({"status": obs.status.value, "result": obs.result}, indent=2))
                continue
            if cmd == "tests":
                params: Dict[str, Any] = {"path": "tests", "pattern": "test*.py"}
                if rest:
                    params["path"] = rest[0]
                action = Action(id="run_tests", name="tests", tool_name="tests", parameters=params, expected_outcome="tests_ok", cost=0.1)
                obs = state.tool_registry.execute_action(action)
                print(json.dumps({"status": obs.status.value, "result": obs.result}, indent=2))
                continue
            if cmd == "format":
                pth = rest[0] if rest else "."
                action = Action(id="fmt", name="format", tool_name="format", parameters={"path": pth, "check": False}, expected_outcome="ok", cost=0.1)
                obs = state.tool_registry.execute_action(action)
                print(json.dumps({"status": obs.status.value, "result": obs.result}, indent=2))
                continue
            if cmd == "lint":
                pth = rest[0] if rest else "."
                action = Action(id="lint", name="lint", tool_name="lint", parameters={"path": pth, "fix": False}, expected_outcome="ok", cost=0.1)
                obs = state.tool_registry.execute_action(action)
                print(json.dumps({"status": obs.status.value, "result": obs.result}, indent=2))
                continue
            if cmd == "lintfix":
                pth = rest[0] if rest else "."
                action = Action(id="lintfix", name="lint", tool_name="lint", parameters={"path": pth, "fix": True}, expected_outcome="ok", cost=0.1)
                obs = state.tool_registry.execute_action(action)
                print(json.dumps({"status": obs.status.value, "result": obs.result}, indent=2))
                continue
            if cmd == "undo":
                action = Action(id="undo", name="restore_backup", tool_name="restore_backup", parameters={"latest": True}, expected_outcome="restored", cost=0.05)
                obs = state.tool_registry.execute_action(action)
                print(json.dumps({"status": obs.status.value, "result": obs.result}, indent=2))
                continue
            if cmd == "backups":
                from pathlib import Path as P
                bdir = P(".agent_state/backups")
                items = sorted(bdir.glob("*.meta.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
                print("backups:")
                for it in items:
                    print("-", it)
                continue
            if cmd == "todo" and rest:
                sub = rest[0].lower()
                if sub == "add" and len(rest) >= 2:
                    text = " ".join(rest[1:])
                    # optional priority at end
                    prio = 3
                    try:
                        maybe = rest[-1]
                        if maybe.isdigit():
                            prio = int(maybe)
                            text = " ".join(rest[1:-1])
                    except Exception:
                        pass
                    item = todos.add(text, priority=prio)
                    print(f"todo added #{item.id}")
                    continue
                if sub == "ls":
                    items = todos.list(include_done=True)
                    for t in items:
                        print(f"({t.id}) [{'x' if t.status=='done' else ' '}] p{t.priority} {t.title}")
                    continue
                if sub == "done" and len(rest) >= 2:
                    try:
                        tid = int(rest[1])
                    except Exception:
                        print("invalid id")
                        continue
                    ok = todos.done(tid)
                    print("ok" if ok else "not found")
                    continue
                if sub == "clear":
                    n = todos.clear(include_open=False)
                    print(f"cleared {n} done item(s)")
                    continue
                print("usage: /todo add <text> [prio] | /todo ls | /todo done <id> | /todo clear")
                continue
            if cmd == "dump":
                print(json.dumps({"provider": state.provider, "messages": state.messages, "summary": state.summary, "pinned": state.pinned, "aliases": list(state.aliases.keys()), "todos": [t.__dict__ for t in todos.list(include_done=True)]}, indent=2))
                continue
            if cmd == "redact" and rest:
                val = rest[0].lower()
                nonlocal_redact = val in {"on", "true", "1"}
                redact_output = nonlocal_redact
                print(f"redact={'on' if redact_output else 'off'}")
                continue
            if cmd == "runbatch" and rest:
                try:
                    obj = json.loads(" ".join(rest))
                except Exception:
                    print("invalid json")
                    continue
                tool = parse_tool_call(json.dumps(obj))
                if not tool or tool.get("type") != "tool_batch":
                    print("expecting {type: 'tool_batch', calls: [...]}")
                    continue
                for call in tool.get("calls", []):
                    tool_name = call.get("tool")
                    args = call.get("args", {})
                    action = Action(id="batch_tool", name=tool_name, tool_name=tool_name, parameters=args, expected_outcome="tool_executed", cost=0.1)
                    observation = state.tool_registry.execute_action(action)
                    print(json.dumps({"tool": tool_name, "status": observation.status.value, "result": observation.result}, indent=2))
                continue
            print("unknown command")
            continue

        state.add_user(user)

        # Retrieve memory and inject brief context
        memories = memory.query(user, top_k=3)
        if memories:
            ctx = "\n".join(f"- {it.meta.get('type','mem')}: {it.text[:300]}" for _, it in memories)
            state.add_system(f"Relevant memory:\n{ctx}")
        # Inject top TODOs
        todo_list = todos.list()
        if todo_list:
            todo_ctx = "\n".join(f"- [{('x' if t.status=='done' else ' ')}] ({t.id}) p{t.priority} {t.title}" for t in todo_list[:5])
            state.add_system(f"TODOs:\n{todo_ctx}")

        # Allow up to N tool calls per turn
        tool_loops = 0
        while tool_loops < state.max_tool_loops:
            def redact(s: str) -> str:
                if not redact_output:
                    return s
                import re
                s = re.sub(r"(?i)\b(ak-[A-Za-z0-9_\-]{20,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z\-_]{33})\b", "[REDACTED]", s)
                s = re.sub(r"\b[A-Za-z0-9_\-]{32,}\b", "[REDACTED]", s)
                return s

            if stream:
                gen = await llm_manager.stream_chat(state.messages, provider=current_provider)
                collected = ""
                async for chunk in gen:
                    out = redact(chunk)
                    print(out, end="", flush=True)
                    collected += chunk
                print()
                assistant_text = collected
            else:
                assistant_text = await llm_manager.chat(state.messages, provider=current_provider)
                print(redact(assistant_text))

            tool = parse_tool_call(assistant_text)
            if not tool:
                state.add_assistant(assistant_text)
                memory.add(assistant_text, {"type": "assistant"})
                break

            # Execute single tool or batch
            if tool.get("type") == "tool_batch":
                batch: List[Dict[str, Any]] = tool.get("calls", [])
                batch_results: List[Dict[str, Any]] = []
                for idx, call in enumerate(batch, 1):
                    tool_name = call.get("tool")
                    args = call.get("args", {})
                    action = Action(
                        id=f"chat_tool_{tool_loops}_{idx}",
                        name=tool_name,
                        tool_name=tool_name,
                        parameters=args,
                        expected_outcome="tool_executed",
                        cost=0.1,
                    )
                    observation = state.tool_registry.execute_action(action)
                    res = {
                        "type": "tool_result",
                        "tool": tool_name,
                        "status": observation.status.value,
                        "result": observation.result,
                    }
                    batch_results.append(res)
                    state.add_assistant(json.dumps(res))
                    memory.add(json.dumps(res), {"type": "tool_result", "tool": tool_name})
                    if observation.status.value != "success":
                        break
                # Summarize batch
                state.add_assistant(json.dumps({"type": "tool_batch_result", "results": batch_results}))
                tool_loops += 1
                continue
            else:
                tool_name = tool.get("tool")
                args = tool.get("args", {})
                action = Action(
                    id=f"chat_tool_{tool_loops}",
                    name=tool_name,
                    tool_name=tool_name,
                    parameters=args,
                    expected_outcome="tool_executed",
                    cost=0.1,
                )
                observation = state.tool_registry.execute_action(action)
                # Append tool result to messages and loop
                tool_result = {
                    "type": "tool_result",
                    "tool": tool_name,
                    "status": observation.status.value,
                    "result": observation.result
                }
                state.add_assistant(json.dumps(tool_result))
                memory.add(json.dumps(tool_result), {"type": "tool_result", "tool": tool_name})
                tool_loops += 1

        # Update rolling summary and trim context
        state.summary = summarize(state.messages)
        if len(state.messages) > state.max_messages:
            # Keep system and last messages
            base_sys = [m for m in state.messages if m["role"] == "system"][:1]
            state.messages = base_sys + state.messages[-(state.max_messages-1):]

        # Persist after each turn
        save_session(state)


def main():
    parser = argparse.ArgumentParser(prog="chat_agent")
    parser.add_argument("--provider", choices=["openai", "anthropic", "local"], default="local")
    parser.add_argument("--no-stream", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_chat(provider=args.provider, stream=not args.no_stream))
    asyncio.run(run_chat(provider=args.provider, stream=not args.no_stream))