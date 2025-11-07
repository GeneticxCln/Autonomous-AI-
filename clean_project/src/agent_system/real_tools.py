"""
Real web search tool implementation.
"""

from __future__ import annotations

import ast
import csv
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from bs4 import BeautifulSoup
except Exception:  # Optional dependency; fallback parser will be used
    BeautifulSoup = None  # type: ignore
import re

from .config_simple import get_api_key, settings, validate_file_path
from .models import ActionStatus

logger = logging.getLogger(__name__)


class RealWebSearchTool:
    """Real web search tool using various search APIs."""

    def __init__(self):
        self.session = self._create_session()
        self.cache = {}  # Simple in-memory cache

    def _create_session(self) -> requests.Session:
        """Create a requests session with retries and timeouts."""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            allowed_methods=["GET", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    @property
    def name(self) -> str:
        return "web_search"

    def execute(self, **kwargs) -> tuple[ActionStatus, Any]:
        """Execute a web search using available APIs."""
        query = kwargs.get("query", "").strip()
        search_type = kwargs.get("search_type", "general").lower()
        max_results = min(kwargs.get("max_results", 10), 50)  # Limit to 50 results max
        fetch = bool(kwargs.get("fetch", False))
        fetch_limit = int(kwargs.get("fetch_limit", 1))

        if not query:
            return ActionStatus.FAILURE, {"error": "Search query is required"}

        # Check cache first
        cache_key = f"{query}_{search_type}_{max_results}_{int(fetch)}_{fetch_limit}"
        if cache_key in self.cache:
            logger.info("Returning cached search results for query: %s", query)
            return ActionStatus.SUCCESS, self.cache[cache_key]

        # Try different search APIs in order of preference
        result = self._try_serpapi_search(query, max_results)
        if not result:
            # Fallback to DuckDuckGo (no API key required)
            result = self._try_duckduckgo_search(query, max_results)

        if result and fetch and result.get("results"):
            enriched = []
            for i, item in enumerate(result["results"][:fetch_limit]):
                url = item.get("link") or item.get("FirstURL")
                if not url:
                    enriched.append(item)
                    continue
                page = self._fetch_page(url)
                if page:
                    item = {**item, **page}
                enriched.append(item)
            result = {**result, "results": enriched}

        if result:
            self.cache[cache_key] = result
            return ActionStatus.SUCCESS, result

        return ActionStatus.FAILURE, {
            "error": "No search APIs available. Please configure SERPAPI_KEY or use offline mode."
        }

    def _try_serpapi_search(self, query: str, max_results: int) -> Optional[Dict[str, Any]]:
        """Try search using SerpAPI."""
        api_key = get_api_key("serpapi")
        if not api_key:
            return None

        try:
            params = {"engine": "google", "q": query, "num": max_results, "api_key": api_key}

            response = self.session.get(
                "https://serpapi.com/search.json", params=params, timeout=settings.TOOL_TIMEOUT
            )
            response.raise_for_status()

            data = response.json()

            if "organic_results" in data:
                results = []
                for result in data["organic_results"][:max_results]:
                    results.append(
                        {
                            "title": result.get("title", ""),
                            "link": result.get("link", ""),
                            "snippet": result.get("snippet", ""),
                            "display_link": result.get("display_link", ""),
                            "source": "google",
                        }
                    )

                return {
                    "results": results,
                    "count": len(results),
                    "search_engine": "google_serpapi",
                    "total_results": data.get("search_information", {}).get("total_results", 0),
                    "query": query,
                    "timestamp": time.time(),
                }

        except requests.RequestException as e:
            logger.warning("SerpAPI search failed: %s", e)

        return None

    def _try_duckduckgo_search(self, query: str, max_results: int) -> Optional[Dict[str, Any]]:
        """Try search using DuckDuckGo instant answer API."""
        try:
            params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}

            response = self.session.get(
                "https://api.duckduckgo.com/", params=params, timeout=settings.TOOL_TIMEOUT
            )
            response.raise_for_status()

            data = response.json()
            results = []

            # Extract related topics
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if "Text" in topic and "FirstURL" in topic:
                    results.append(
                        {
                            "title": topic.get("Text", "").split(" - ")[0],
                            "link": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", ""),
                            "display_link": topic.get("FirstURL", "").split("//")[-1].split("/")[0],
                            "source": "duckduckgo",
                        }
                    )

            # If no related topics, try abstract
            if not results and data.get("Abstract"):
                results.append(
                    {
                        "title": data.get("Heading", ""),
                        "link": data.get("AbstractURL", ""),
                        "snippet": data.get("Abstract", ""),
                        "display_link": (
                            data.get("AbstractURL", "").split("//")[-1].split("/")[0]
                            if data.get("AbstractURL")
                            else ""
                        ),
                        "source": "duckduckgo",
                    }
                )

            if results:
                return {
                    "results": results,
                    "count": len(results),
                    "search_engine": "duckduckgo",
                    "query": query,
                    "timestamp": time.time(),
                }

        except requests.RequestException as e:
            logger.warning("DuckDuckGo search failed: %s", e)

        return None

    def _fetch_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch a web page and extract text summary and metadata."""
        try:
            resp = self.session.get(url, timeout=min(settings.TOOL_TIMEOUT, 15))
            resp.raise_for_status()
            html = resp.text
            title = ""
            text = ""
            if BeautifulSoup is not None:
                soup = BeautifulSoup(html, "html.parser")
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                text = " ".join(soup.get_text(separator=" ").split())
            else:
                # Fallback: naive tag stripping
                try:
                    title_match = re.search(
                        r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL
                    )
                    title = title_match.group(1).strip() if title_match else ""
                except Exception:
                    title = ""
                text = re.sub(r"<[^>]+>", " ", html)
                text = " ".join(text.split())
            excerpt = text[:2000]
            return {
                "title": title,
                "content_excerpt": excerpt,
                "content_length": len(text),
                "url": url,
            }
        except Exception as e:
            logger.warning("Page fetch failed for %s: %s", url, e)
            return None


class RealCodeExecutorTool:
    """Real code execution tool with security restrictions."""

    # Blocked imports for security
    BLOCKED_IMPORTS = {
        "os",
        "subprocess",
        "sys",
        "glob",
        "shutil",
        "pickle",
        "marshal",
        "exec",
        "eval",
        "compile",
        "__import__",
        "open",
        "input",
    }

    @property
    def name(self) -> str:
        return "code_executor"

    def execute(self, **kwargs) -> tuple[ActionStatus, Any]:
        """Execute code safely with restrictions."""
        code = kwargs.get("code", "").strip()
        language = kwargs.get("language", "python").lower()
        timeout = min(kwargs.get("timeout", settings.CODE_EXECUTION_TIMEOUT), 60)

        if not code:
            return ActionStatus.FAILURE, {"error": "Code is required"}

        if language not in ["python", "bash", "shell"]:
            return ActionStatus.FAILURE, {
                "error": f"Language '{language}' not supported. Only Python and Bash are supported."
            }

        try:
            if language == "python":
                return self._execute_python(code, timeout)
            else:
                return self._execute_bash(code, timeout)

        except Exception as e:
            return ActionStatus.FAILURE, {
                "error": f"Execution failed: {str(e)}",
                "code": code,
                "language": language,
            }

    @staticmethod
    def _is_code_safe(code: str) -> tuple[bool, str | None]:
        """Lightweight AST-based guard to block dangerous constructs.
        This is NOT a full sandbox; it reduces obvious risks.
        """
        banned_calls = {
            "open",
            "exec",
            "eval",
            "compile",
            "__import__",
            "input",
        }
        banned_names = {
            "os",
            "sys",
            "subprocess",
            "shutil",
            "socket",
            "requests",
            "pathlib",
            "importlib",
            "builtins",
            "pickle",
            "marshal",
        }

        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"

        class Guard(ast.NodeVisitor):
            unsafe: tuple[bool, str | None] = (False, None)

            def visit_Import(self, node: ast.Import):  # type: ignore[override]
                self.unsafe = (True, "Imports are not allowed")

            def visit_ImportFrom(self, node: ast.ImportFrom):  # type: ignore[override]
                self.unsafe = (True, "Imports are not allowed")

            def visit_Attribute(self, node: ast.Attribute):  # type: ignore[override]
                if node.attr.startswith("__"):
                    self.unsafe = (True, "Dunder attribute access is not allowed")
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call):  # type: ignore[override]
                # Block calls to banned names
                func = node.func
                if isinstance(func, ast.Name) and func.id in banned_calls:
                    self.unsafe = (True, f"Call to '{func.id}' is not allowed")
                elif isinstance(func, ast.Attribute):
                    # Block if base name is banned or attribute name looks dangerous
                    base = func.value
                    if isinstance(base, ast.Name) and base.id in banned_names:
                        self.unsafe = (True, f"Access to '{base.id}' is not allowed")
                    if func.attr in banned_calls:
                        self.unsafe = (True, f"Call to '{func.attr}' is not allowed")
                self.generic_visit(node)

            def visit_Global(self, node: ast.Global):  # type: ignore[override]
                # Discourage global mutation patterns
                self.unsafe = (True, "Global declarations are not allowed")

            def visit_Nonlocal(self, node: ast.Nonlocal):  # type: ignore[override]
                self.unsafe = (True, "Nonlocal declarations are not allowed")

        g = Guard()
        g.visit(tree)
        if g.unsafe[0]:
            return False, g.unsafe[1]
        return True, None

    def _execute_python(self, code: str, timeout: int) -> tuple[ActionStatus, Any]:
        """Execute Python code with security restrictions."""
        # Basic security check - block dangerous imports and calls using AST
        ok, reason = self._is_code_safe(code)
        if not ok:
            return ActionStatus.FAILURE, {"error": str(reason or "Unsafe code"), "security_violation": True}

        # Create temporary file for execution
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            # Execute with timeout and restricted environment
            start_time = time.time()

            # Use isolated mode (-I) to ignore environment variables and user site dirs
            result = subprocess.run(
                [sys.executable, "-I", temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={
                    **os.environ,
                    "PYTHONPATH": "",  # Clear Python path
                    "HOME": "/tmp",  # Restrict home directory
                },
                cwd="/tmp",  # Restrict working directory
            )

            execution_time = time.time() - start_time

            return ActionStatus.SUCCESS, {
                "output": result.stdout,
                "error": result.stderr,
                "return_code": result.returncode,
                "execution_time": execution_time,
                "language": "python",
                "timeout_used": timeout,
            }

        except subprocess.TimeoutExpired:
            return ActionStatus.FAILURE, {
                "error": f"Code execution timed out after {timeout} seconds",
                "timeout": True,
            }

        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file)
            except Exception:
                pass

    def _execute_bash(self, code: str, timeout: int) -> tuple[ActionStatus, Any]:
        """Execute bash code with security restrictions."""
        # Basic security check for dangerous commands
        dangerous_commands = {"rm -rf", "sudo", "su", "chmod", "chown", "dd", "mkfs"}
        for dangerous in dangerous_commands:
            if dangerous in code:
                return ActionStatus.FAILURE, {
                    "error": f"Dangerous command detected: {dangerous}",
                    "security_violation": True,
                }

        start_time = time.time()

        try:
            result = subprocess.run(
                ["/bin/bash", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd="/tmp",  # Restrict working directory
            )

            execution_time = time.time() - start_time

            return ActionStatus.SUCCESS, {
                "output": result.stdout,
                "error": result.stderr,
                "return_code": result.returncode,
                "execution_time": execution_time,
                "language": "bash",
                "timeout_used": timeout,
            }

        except subprocess.TimeoutExpired:
            return ActionStatus.FAILURE, {
                "error": f"Command execution timed out after {timeout} seconds",
                "timeout": True,
            }


class RealFileReaderTool:
    """Real file reader tool with secure path validation and format support."""

    @property
    def name(self) -> str:
        return "file_reader"

    def execute(self, **kwargs) -> tuple[ActionStatus, Any]:
        filepath = kwargs.get("filepath")
        fmt = (kwargs.get("format") or "auto").lower()
        encoding = kwargs.get("encoding", "utf-8")
        max_bytes = int(kwargs.get("max_bytes", 1024 * 1024))  # 1MB default

        if not filepath:
            return ActionStatus.FAILURE, {"error": "Filepath is required"}

        try:
            if not validate_file_path(filepath):
                return ActionStatus.FAILURE, {"error": "Access to this path is not allowed"}

            p = Path(filepath)
            if not p.exists() or not p.is_file():
                return ActionStatus.FAILURE, {"error": f"File not found: {filepath}"}

            detected_fmt = fmt
            if fmt == "auto":
                ext = p.suffix.lower().lstrip(".")
                if ext in {"json", "csv", "txt", "md"}:
                    detected_fmt = ext if ext != "txt" else "text"
                else:
                    detected_fmt = "text"

            meta = {
                "filepath": str(p),
                "size": p.stat().st_size,
                "modified": p.stat().st_mtime,
                "format": detected_fmt,
            }

            if detected_fmt == "json":
                with p.open("r", encoding=encoding) as f:
                    data = json.load(f)
                return ActionStatus.SUCCESS, {"content": data, **meta}

            if detected_fmt == "csv":
                with p.open("r", encoding=encoding, newline="") as f:
                    reader = csv.DictReader(f)
                    rows = []
                    for i, row in enumerate(reader):
                        rows.append(row)
                        if (i + 1) >= 2000:  # cap rows
                            break
                meta.update(
                    {
                        "rows": len(rows),
                        "columns": list(rows[0].keys()) if rows else [],
                    }
                )
                return ActionStatus.SUCCESS, {"content": rows, **meta}

            # Fallback to text
            with p.open("rb") as fb:
                data = fb.read(max_bytes)
                truncated = p.stat().st_size > len(data)
            try:
                text = data.decode(encoding, errors="replace")
            except Exception:
                text = data.decode("utf-8", errors="replace")
            lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
            meta.update({"lines": lines, "truncated": truncated})
            return ActionStatus.SUCCESS, {"content": text, **meta}

        except Exception as e:
            logger.error("File read failed: %s", e)
            return ActionStatus.FAILURE, {"error": f"Read failed: {str(e)}"}


class RealFileWriterTool:
    """Real file writer tool with secure path validation."""

    @property
    def name(self) -> str:
        return "file_writer"

    def execute(self, **kwargs) -> tuple[ActionStatus, Any]:
        filepath = kwargs.get("filepath")
        content = kwargs.get("content")
        fmt = (kwargs.get("format") or "text").lower()
        encoding = kwargs.get("encoding", "utf-8")
        ensure_dir = bool(kwargs.get("ensure_dir", True))

        if not filepath:
            return ActionStatus.FAILURE, {"error": "Filepath is required"}

        try:
            if not validate_file_path(filepath):
                return ActionStatus.FAILURE, {"error": "Access to this path is not allowed"}

            p = Path(filepath)
            if ensure_dir:
                p.parent.mkdir(parents=True, exist_ok=True)

            bytes_written = 0
            if fmt == "json":
                # If content is string, try to parse; else dump as JSON
                if isinstance(content, str):
                    try:
                        parsed = json.loads(content)
                    except json.JSONDecodeError:
                        parsed = {"content": content}
                else:
                    parsed = content
                data = json.dumps(parsed, indent=2, ensure_ascii=False)
                with p.open("w", encoding=encoding) as f:
                    f.write(data)
                bytes_written = len(data.encode(encoding))
            else:
                text = (
                    content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                )
                with p.open("w", encoding=encoding) as f:
                    f.write(text)
                bytes_written = len(text.encode(encoding))

            meta = {
                "filepath": str(p),
                "bytes_written": bytes_written,
                "format": fmt,
                "created": True,
            }
            return ActionStatus.SUCCESS, meta

        except Exception as e:
            logger.error("File write failed: %s", e)
            return ActionStatus.FAILURE, {"error": f"Write failed: {str(e)}"}
