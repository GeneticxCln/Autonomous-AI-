from __future__ import annotations

import asyncio
import atexit
import inspect
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Dict, Tuple

from .models import Action, ActionStatus, Observation

logger = logging.getLogger(__name__)


class Tool(ABC):
    """Abstract base class for tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def execute(self, **kwargs) -> Tuple[ActionStatus, Any] | Awaitable[Tuple[ActionStatus, Any]]:
        raise NotImplementedError


class WebSearchTool(Tool):
    """Mock web search tool."""

    @property
    def name(self) -> str:
        return "web_search"

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        query = kwargs.get("query", "")
        logger.info("Executing web search: %s", query)
        return ActionStatus.SUCCESS, {"results": [f"Result for: {query}"], "count": 1}


class FileReaderTool(Tool):
    """Mock file reader tool."""

    @property
    def name(self) -> str:
        return "file_reader"

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        filepath = kwargs.get("filepath", "")
        logger.info("Reading file (mock): %s", filepath)
        return ActionStatus.SUCCESS, {
            "content": f"Contents of {filepath} (mock)",
            "filepath": filepath,
        }


class FileWriterTool(Tool):
    """Mock file writer tool."""

    @property
    def name(self) -> str:
        return "file_writer"

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        filepath = kwargs.get("filepath", "")
        content = kwargs.get("content", "")
        fmt = kwargs.get("format", "text")
        logger.info("Writing file (mock): %s", filepath)
        return ActionStatus.SUCCESS, {
            "filepath": filepath,
            "bytes_written": len(str(content).encode("utf-8")),
            "format": fmt,
            "note": "Mock write; no file created",
        }


class CodeExecutorTool(Tool):
    """Mock code executor tool."""

    @property
    def name(self) -> str:
        return "code_executor"

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        logger.info("Executing code")
        return ActionStatus.SUCCESS, {"output": "Code executed successfully"}


class ShellTool(Tool):
    """Restricted read-only shell executor for terminal operations."""

    ALLOWED_CMDS = {"ls", "cat", "head", "tail", "wc", "grep", "stat", "pwd", "echo"}

    @property
    def name(self) -> str:
        return "shell"

    def _safe_token(self, token: str) -> bool:
        import re

        return bool(re.fullmatch(r"[A-Za-z0-9_\-\./]+", token))

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        import subprocess

        from .config_simple import settings, validate_file_path

        cmd = str(kwargs.get("cmd", "")).strip()
        args = kwargs.get("args", [])
        if not cmd or cmd not in self.ALLOWED_CMDS:
            return ActionStatus.FAILURE, {"error": "Command not allowed"}
        if not isinstance(args, list):
            return ActionStatus.FAILURE, {"error": "args must be a list"}

        tokens = [cmd]
        for a in args:
            s = str(a)
            if not self._safe_token(s):
                return ActionStatus.FAILURE, {"error": f"Unsafe token: {s}"}
            # Validate file path-like tokens
            if "/" in s or s.startswith("."):
                if not validate_file_path(s):
                    return ActionStatus.FAILURE, {"error": f"Path not allowed: {s}"}
            tokens.append(s)

        try:
            proc = subprocess.run(
                tokens, capture_output=True, text=True, timeout=settings.TOOL_TIMEOUT
            )
            return ActionStatus.SUCCESS, {
                "cmd": tokens,
                "return_code": proc.returncode,
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-8000:],
            }
        except subprocess.TimeoutExpired:
            return ActionStatus.FAILURE, {"error": "Command timeout"}
        except Exception as e:
            return ActionStatus.FAILURE, {"error": str(e)}


class CodeSearchTool(Tool):
    """Search code/files for a regex pattern within allowed paths."""

    @property
    def name(self) -> str:
        return "code_search"

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        import fnmatch
        import os
        import re

        from .config_simple import validate_file_path

        root = str(kwargs.get("path", "."))
        pattern = str(kwargs.get("pattern", "")).strip()
        includes = kwargs.get("include", ["**/*"])
        excludes = kwargs.get("exclude", [".git/*", "*.pyc", "*.log", "node_modules/*"])
        max_results = int(kwargs.get("max_results", 200))
        flags = re.IGNORECASE if kwargs.get("ignore_case", True) else 0

        if not pattern:
            return ActionStatus.FAILURE, {"error": "pattern required"}
        if not validate_file_path(root):
            return ActionStatus.FAILURE, {"error": f"path not allowed: {root}"}

        # Normalize include/exclude to lists
        if isinstance(includes, str):
            includes = [includes]
        if isinstance(excludes, str):
            excludes = [excludes]

        regex = re.compile(pattern, flags)
        matches = []

        for dirpath, dirnames, filenames in os.walk(root):
            # Apply directory excludes
            dirnames[:] = [
                d
                for d in dirnames
                if not any(fnmatch.fnmatch(os.path.join(dirpath, d), ex) for ex in excludes)
            ]
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if any(fnmatch.fnmatch(filepath, ex) for ex in excludes):
                    continue
                if not any(fnmatch.fnmatch(filepath, inc) or inc == "**/*" for inc in includes):
                    continue
                try:
                    # Read text files only (best-effort)
                    with open(filepath, encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, start=1):
                            if regex.search(line):
                                matches.append(
                                    {
                                        "file": filepath,
                                        "line": i,
                                        "text": line.strip()[:500],
                                    }
                                )
                                if len(matches) >= max_results:
                                    break
                except Exception:
                    continue
                if len(matches) >= max_results:
                    break
            if len(matches) >= max_results:
                break

        return ActionStatus.SUCCESS, {"count": len(matches), "matches": matches}


class EditFileTool(Tool):
    """Safely edit a single file by replacing an exact substring (with optional single occurrence)."""

    @property
    def name(self) -> str:
        return "edit_file"

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        import hashlib
        import json
        import time
        from pathlib import Path

        from .config_simple import validate_file_path

        path = str(kwargs.get("path", "")).strip()
        search = kwargs.get("search")
        replace = kwargs.get("replace")
        once = bool(kwargs.get("once", True))
        if not path or search is None or replace is None:
            return ActionStatus.FAILURE, {"error": "path, search, replace required"}
        if not validate_file_path(path):
            return ActionStatus.FAILURE, {"error": f"path not allowed: {path}"}
        p = Path(path)
        if not p.exists() or not p.is_file():
            return ActionStatus.FAILURE, {"error": f"file not found: {path}"}
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            return ActionStatus.FAILURE, {"error": "failed to read file as utf-8"}
        count = txt.count(search)
        if count == 0:
            return ActionStatus.FAILURE, {"error": "search string not found"}
        if once and count > 1:
            # replace only first occurrence
            new_txt = txt.replace(search, replace, 1)
            replaced = 1
        else:
            new_txt = txt.replace(search, replace)
            replaced = count
        # backup with meta
        backup_dir = Path(".agent_state/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        safe = hashlib.sha1(str(p).encode("utf-8")).hexdigest()[:10]
        base = f"{p.name}.{safe}.{ts}"
        backup_path = backup_dir / (base + ".bak")
        meta_path = backup_dir / (base + ".meta.json")
        try:
            backup_path.write_text(txt, encoding="utf-8")
            meta_path.write_text(
                json.dumps({"original": str(p)}, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            p.write_text(new_txt, encoding="utf-8")
        except Exception as e:
            return ActionStatus.FAILURE, {"error": f"write failed: {e}"}
        return ActionStatus.SUCCESS, {
            "edited": True,
            "replacements": replaced,
            "backup": str(backup_path),
            "meta": str(meta_path),
        }


class RestoreBackupTool(Tool):
    """Restore a file from a backup created by edit_file/replace_in_files."""

    @property
    def name(self) -> str:
        return "restore_backup"

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        import json
        from pathlib import Path

        backups_dir = Path(".agent_state/backups")
        latest = bool(kwargs.get("latest", True))
        backup = kwargs.get("backup")  # path to .bak or .meta.json
        # pick latest meta if requested
        meta_path: Path | None = None
        bak_path: Path | None = None
        try:
            if latest:
                metas = sorted(
                    backups_dir.glob("*.meta.json"), key=lambda p: p.stat().st_mtime, reverse=True
                )
                if not metas:
                    return ActionStatus.FAILURE, {"error": "no backups"}
                meta_path = metas[0]
            else:
                if not backup:
                    return ActionStatus.FAILURE, {"error": "backup path required"}
                p = Path(str(backup))
                if p.suffix == ".json":
                    meta_path = p
                else:
                    # infer meta path by swapping extension
                    meta_path = p.with_suffix(".meta.json")
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            original = data.get("original")
            if not original:
                return ActionStatus.FAILURE, {"error": "invalid meta"}
            base = meta_path.name.replace(".meta.json", "")
            bak_path = meta_path.with_name(base + ".bak")
            if not bak_path.exists():
                return ActionStatus.FAILURE, {"error": "backup file missing"}
            Path(original).write_text(bak_path.read_text(encoding="utf-8"), encoding="utf-8")
            return ActionStatus.SUCCESS, {
                "restored": original,
                "backup": str(bak_path),
                "meta": str(meta_path),
            }
        except Exception as e:
            return ActionStatus.FAILURE, {"error": str(e)}


class ReplaceInFilesTool(Tool):
    """Search/replace across multiple files (regex), within allowed paths."""

    @property
    def name(self) -> str:
        return "replace_in_files"

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        import fnmatch
        import hashlib
        import json
        import os
        import re
        import time
        from pathlib import Path

        from .config_simple import validate_file_path

        root = str(kwargs.get("path", "."))
        pattern = kwargs.get("search")
        repl = kwargs.get("replace", "")
        includes = kwargs.get(
            "include", ["**/*.py", "**/*.txt", "**/*.md", "**/*.json", "**/*.ts", "**/*.js"]
        )
        excludes = kwargs.get("exclude", [".git/*", "*.pyc", "node_modules/*", "*.min.js"])
        max_edits = int(kwargs.get("max_edits", 1000))
        flags = re.IGNORECASE if kwargs.get("ignore_case", False) else 0
        if not pattern:
            return ActionStatus.FAILURE, {"error": "search regex required"}
        if not validate_file_path(root):
            return ActionStatus.FAILURE, {"error": f"path not allowed: {root}"}
        if isinstance(includes, str):
            includes = [includes]
        if isinstance(excludes, str):
            excludes = [excludes]
        rx = re.compile(pattern, flags)
        total_edits = 0
        files_changed = 0
        changes = []
        backup_dir = Path(".agent_state/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d
                for d in dirnames
                if not any(fnmatch.fnmatch(os.path.join(dirpath, d), ex) for ex in excludes)
            ]
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if any(fnmatch.fnmatch(filepath, ex) for ex in excludes):
                    continue
                if not any(fnmatch.fnmatch(filepath, inc) or inc == "**/*" for inc in includes):
                    continue
                if not validate_file_path(filepath):
                    continue
                try:
                    text = Path(filepath).read_text(encoding="utf-8")
                except Exception:
                    continue
                new_text, n = rx.subn(repl, text)
                if n > 0:
                    try:
                        p = Path(filepath)
                        safe = hashlib.sha1(str(p).encode("utf-8")).hexdigest()[:10]
                        base = f"{p.name}.{safe}.{ts}"
                        backup_path = backup_dir / (base + ".bak")
                        meta_path = backup_dir / (base + ".meta.json")
                        backup_path.write_text(text, encoding="utf-8")
                        meta_path.write_text(
                            json.dumps({"original": str(p)}, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        p.write_text(new_text, encoding="utf-8")
                        files_changed += 1
                        total_edits += n
                        changes.append(
                            {
                                "file": filepath,
                                "replacements": n,
                                "backup": str(backup_path),
                                "meta": str(meta_path),
                            }
                        )
                    except Exception:
                        continue
                if total_edits >= max_edits:
                    break
            if total_edits >= max_edits:
                break
        return ActionStatus.SUCCESS, {
            "files_changed": files_changed,
            "total_replacements": total_edits,
            "changes": changes,
        }


class GitTool(Tool):
    """Restricted git wrapper (read-only)."""

    ALLOWED_CMDS = {"status", "log", "diff"}

    @property
    def name(self) -> str:
        return "git"

    def _safe_token(self, tok: str) -> bool:
        import re

        return bool(re.fullmatch(r"[A-Za-z0-9._/\-]+", tok))

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        import subprocess

        from .config_simple import settings

        cmd = str(kwargs.get("cmd", "")).lower().strip()
        if cmd not in self.ALLOWED_CMDS:
            return ActionStatus.FAILURE, {"error": "unsupported git cmd"}

        args: list[str] = ["git", "--no-pager"]

        try:
            if cmd == "status":
                args += ["status", "--porcelain"]
            elif cmd == "log":
                n = int(kwargs.get("n", 10))
                n = max(1, min(100, n))
                args += ["log", "--oneline", "-n", str(n)]
            elif cmd == "diff":
                rng = kwargs.get("range")
                path = kwargs.get("path")
                args += ["diff", "--name-only"]
                if rng and isinstance(rng, str) and self._safe_token(rng):
                    args.append(rng)
                if path and isinstance(path, str) and self._safe_token(path):
                    args.append(path)

            proc = subprocess.run(
                args, capture_output=True, text=True, timeout=settings.TOOL_TIMEOUT
            )
            return ActionStatus.SUCCESS, {
                "cmd": args,
                "return_code": proc.returncode,
                "stdout": proc.stdout[-10000:],
                "stderr": proc.stderr[-10000:],
            }
        except subprocess.TimeoutExpired:
            return ActionStatus.FAILURE, {"error": "git timeout"}
        except Exception as e:
            return ActionStatus.FAILURE, {"error": str(e)}


class TestTool(Tool):
    """Run unit tests (read-only) and return a compact summary."""

    @property
    def name(self) -> str:
        return "tests"

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        import subprocess

        from .config_simple import settings

        path = str(kwargs.get("path", "tests"))
        pattern = str(kwargs.get("pattern", "test*.py"))
        try:
            cmd = ["python3", "-m", "unittest", "discover", "-s", path, "-p", pattern, "-q"]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=max(settings.TOOL_TIMEOUT, 60)
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            lines = out.strip().splitlines()[-50:]
            return ActionStatus.SUCCESS, {
                "cmd": cmd,
                "return_code": proc.returncode,
                "output": "\n".join(lines),
            }
        except subprocess.TimeoutExpired:
            return ActionStatus.FAILURE, {"error": "tests timed out"}
        except Exception as e:
            return ActionStatus.FAILURE, {"error": str(e)}


class FormatTool(Tool):
    """Format Python code using black (writes changes)."""

    @property
    def name(self) -> str:
        return "format"

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        import subprocess

        from .config_simple import settings, validate_file_path

        path = str(kwargs.get("path", ".")).strip()
        check = bool(kwargs.get("check", False))
        if not validate_file_path(path):
            return ActionStatus.FAILURE, {"error": f"path not allowed: {path}"}
        cmd = ["python3", "-m", "black"] + (["--check"] if check else []) + [path]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=max(settings.TOOL_TIMEOUT, 60)
            )
            return ActionStatus.SUCCESS, {
                "cmd": cmd,
                "return_code": proc.returncode,
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-8000:],
            }
        except subprocess.TimeoutExpired:
            return ActionStatus.FAILURE, {"error": "format timed out"}
        except Exception as e:
            return ActionStatus.FAILURE, {"error": str(e)}


class LintTool(Tool):
    """Run ruff linter (optionally fix)."""

    @property
    def name(self) -> str:
        return "lint"

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        import subprocess

        from .config_simple import settings, validate_file_path

        path = str(kwargs.get("path", ".")).strip()
        fix = bool(kwargs.get("fix", False))
        if not validate_file_path(path):
            return ActionStatus.FAILURE, {"error": f"path not allowed: {path}"}
        cmd = ["python3", "-m", "ruff"] + (["--fix"] if fix else []) + [path]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=max(settings.TOOL_TIMEOUT, 60)
            )
            return ActionStatus.SUCCESS, {
                "cmd": cmd,
                "return_code": proc.returncode,
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-8000:],
            }
        except subprocess.TimeoutExpired:
            return ActionStatus.FAILURE, {"error": "lint timed out"}
        except Exception as e:
            return ActionStatus.FAILURE, {"error": str(e)}


class GenericTool(Tool):
    """Fallback tool for abstract actions without dedicated implementations."""

    @property
    def name(self) -> str:
        return "generic_tool"

    def execute(self, **kwargs) -> Tuple[ActionStatus, Any]:
        action_name = kwargs.get("action") or kwargs.get("goal", "generic_task")
        logger.info("Executing generic action handler for: %s", action_name)
        return ActionStatus.SUCCESS, {"status": f"Completed generic action for {action_name}"}


class ToolRegistry:
    """Manages available tools and handles execution with retry logic."""

    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.tool_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"success": 0, "failure": 0, "total": 0}
        )
        self.max_retries = 3
        max_workers = 4
        try:  # Avoid import cycles during early bootstrap
            from .config_simple import settings as _settings

            max_workers = max(1, int(getattr(_settings, "TOOL_EXECUTOR_WORKERS", max_workers)))
        except Exception:
            pass

        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="tool-registry",
        )
        atexit.register(self._executor.shutdown, False)

    def register_tool(self, tool: Tool):
        """Register a tool."""
        self.tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def execute_action(self, action: Action, retry: bool = True) -> Observation:
        """Execute an action synchronously (legacy compatibility)."""
        tool = self.tools.get(action.tool_name)

        if not tool:
            logger.error("Tool not found: %s", action.tool_name)
            return Observation(
                action_id=action.id,
                status=ActionStatus.FAILURE,
                result=None,
                feedback=f"Tool {action.tool_name} not available",
            )

        attempts = 0
        max_attempts = self.max_retries if retry else 1

        try:
            payload_bytes = len(json.dumps(action.parameters, ensure_ascii=False).encode("utf-8"))
        except Exception:
            payload_bytes = 0

        start = time.perf_counter()
        while attempts < max_attempts:
            attempts += 1

            try:
                status, result = tool.execute(**action.parameters)

                self._update_tool_stats(tool.name, status)

                duration_ms = (time.perf_counter() - start) * 1000.0
                try:
                    result_bytes = len(
                        json.dumps(result, ensure_ascii=False)[:100000].encode("utf-8")
                    )
                except Exception:
                    result_bytes = 0

                observation = Observation(
                    action_id=action.id,
                    status=status,
                    result=result,
                    feedback=f"Completed in {attempts} attempt(s)",
                    metrics={
                        "tool": tool.name,
                        "latency_ms": round(duration_ms, 3),
                        "attempts": attempts,
                        "payload_bytes": payload_bytes,
                        "result_bytes": result_bytes,
                        "success": 1.0 if status == ActionStatus.SUCCESS else 0.0,
                    },
                )

                if status == ActionStatus.SUCCESS or not retry:
                    return observation

                logger.warning("Action failed, attempt %s/%s", attempts, max_attempts)

            except Exception as exc:  # pragma: no cover - placeholder for real tool errors
                logger.error("Tool execution error: %s", exc)

                if attempts >= max_attempts:
                    duration_ms = (time.perf_counter() - start) * 1000.0
                    return Observation(
                        action_id=action.id,
                        status=ActionStatus.FAILURE,
                        result=None,
                        feedback=f"Failed after {attempts} attempts: {exc}",
                        metrics={
                            "tool": tool.name,
                            "latency_ms": round(duration_ms, 3),
                            "attempts": attempts,
                            "payload_bytes": payload_bytes,
                            "result_bytes": 0,
                            "success": 0.0,
                            "error_type": type(exc).__name__,
                        },
                    )

        duration_ms = (time.perf_counter() - start) * 1000.0
        return Observation(
            action_id=action.id,
            status=ActionStatus.FAILURE,
            result=None,
            feedback=f"Failed after {max_attempts} attempts",
            metrics={
                "tool": tool.name if tool else action.tool_name,
                "latency_ms": round(duration_ms, 3),
                "attempts": attempts,
                "payload_bytes": payload_bytes,
                "result_bytes": 0,
                "success": 0.0,
            },
        )

    async def execute_action_async(self, action: Action, retry: bool = True) -> Observation:
        """Execute an action using the appropriate tool with basic retry logic (async)."""
        tool = self.tools.get(action.tool_name)

        if not tool:
            logger.error("Tool not found: %s", action.tool_name)
            return Observation(
                action_id=action.id,
                status=ActionStatus.FAILURE,
                result=None,
                feedback=f"Tool {action.tool_name} not available",
            )

        attempts = 0
        max_attempts = self.max_retries if retry else 1

        payload_bytes = 0
        try:
            payload_bytes = len(json.dumps(action.parameters, ensure_ascii=False).encode("utf-8"))
        except Exception:
            payload_bytes = 0

        start = time.perf_counter()
        while attempts < max_attempts:
            attempts += 1

            try:
                status, result = await self._invoke_tool(tool, action.parameters)

                self._update_tool_stats(tool.name, status)

                duration_ms = (time.perf_counter() - start) * 1000.0
                try:
                    result_bytes = len(
                        json.dumps(result, ensure_ascii=False)[:100000].encode("utf-8")
                    )
                except Exception:
                    result_bytes = 0

                observation = Observation(
                    action_id=action.id,
                    status=status,
                    result=result,
                    feedback=f"Completed in {attempts} attempt(s)",
                    metrics={
                        "tool": tool.name,
                        "latency_ms": round(duration_ms, 3),
                        "attempts": attempts,
                        "payload_bytes": payload_bytes,
                        "result_bytes": result_bytes,
                        "success": 1.0 if status == ActionStatus.SUCCESS else 0.0,
                    },
                )

                if status == ActionStatus.SUCCESS or not retry:
                    return observation

                logger.warning("Action failed, attempt %s/%s", attempts, max_attempts)

            except Exception as exc:  # pragma: no cover - placeholder for real tool errors
                logger.error("Tool execution error: %s", exc)

                if attempts >= max_attempts:
                    duration_ms = (time.perf_counter() - start) * 1000.0
                    return Observation(
                        action_id=action.id,
                        status=ActionStatus.FAILURE,
                        result=None,
                        feedback=f"Failed after {attempts} attempts: {exc}",
                        metrics={
                            "tool": tool.name,
                            "latency_ms": round(duration_ms, 3),
                            "attempts": attempts,
                            "payload_bytes": payload_bytes,
                            "result_bytes": 0,
                            "success": 0.0,
                            "error_type": type(exc).__name__,
                        },
                    )

        duration_ms = (time.perf_counter() - start) * 1000.0
        return Observation(
            action_id=action.id,
            status=ActionStatus.FAILURE,
            result=None,
            feedback=f"Failed after {max_attempts} attempts",
            metrics={
                "tool": tool.name if tool else action.tool_name,
                "latency_ms": round(duration_ms, 3),
                "attempts": attempts,
                "payload_bytes": payload_bytes,
                "result_bytes": 0,
                "success": 0.0,
            },
        )

    async def _invoke_tool(
        self, tool: Tool, parameters: Dict[str, Any]
    ) -> Tuple[ActionStatus, Any]:
        """Invoke the tool, running sync implementations in a worker thread."""
        if inspect.iscoroutinefunction(tool.execute):
            result = await tool.execute(**parameters)
        else:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(self._executor, lambda: tool.execute(**parameters))

        if inspect.isawaitable(result):
            result = await result

        return result

    def _update_tool_stats(self, tool_name: str, status: ActionStatus) -> None:
        stats = self.tool_stats[tool_name]
        stats["total"] += 1
        if status == ActionStatus.SUCCESS:
            stats["success"] += 1
        else:
            stats["failure"] += 1

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names."""
        return list(self.tools.keys())

    def get_tool(self, name: str) -> Tool | None:
        """Retrieve a tool by name if registered, else None."""
        return self.tools.get(name)

    def get_tool_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tools."""
        stats: Dict[str, Dict[str, Any]] = {}
        for tool_name, data in self.tool_stats.items():
            total = data["total"]
            stats[tool_name] = {
                "success_rate": data["success"] / total if total > 0 else 0,
                "total_executions": total,
                "successes": data["success"],
                "failures": data["failure"],
            }
        return stats
