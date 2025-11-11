"""
Enhanced tool registry with real tool support.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Protocol, Tuple, cast, runtime_checkable

from agent_system.models import Action, ActionStatus, Observation
from agent_system.tools import Tool, ToolRegistry

from .config_simple import get_api_key, settings
from .real_tools import (
    RealCodeExecutorTool,
    RealFileReaderTool,
    RealFileWriterTool,
    RealWebSearchTool,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class ToolLike(Protocol):
    @property
    def name(self) -> str: ...
    def execute(self, **kwargs: Any) -> Tuple[ActionStatus, Any] | Awaitable[Tuple[ActionStatus, Any]]: ...


class EnhancedToolRegistry(cast(Any, ToolRegistry)):  # type: ignore[misc]
    """Enhanced tool registry that can use real tools when configured."""

    def __init__(self) -> None:
        super().__init__()
        self.use_real_tools = True  # default to real tools by default
        if getattr(settings, "USE_REAL_TOOLS_CONFIGURED", False):
            self.use_real_tools = bool(getattr(settings, "USE_REAL_TOOLS", True))

        self.real_tools: Dict[str, Tool] = {}
        self._real_tools_initialized = False

        if self.use_real_tools:
            self._initialize_real_tools()

    def _initialize_real_tools(self) -> None:
        """Initialize real tool instances."""
        if self._real_tools_initialized:
            return

        errors: Dict[str, Exception] = {}

        def _register(name: str, factory: Callable[[], Any]) -> None:
            try:
                self.real_tools[name] = cast(Tool, factory())
            except Exception as exc:  # pragma: no cover - dependency bootstrap
                errors[name] = exc

        # Always initialize real file and code tools
        _register("file_reader", RealFileReaderTool)
        _register("file_writer", RealFileWriterTool)
        _register("code_executor", RealCodeExecutorTool)

        # Initialize web search (may require API key); failures reported unless terminal-only
        if not settings.TERMINAL_ONLY:
            _register("web_search", RealWebSearchTool)

        if errors:
            combined = "; ".join(f"{name}: {exc}" for name, exc in errors.items())
            raise RuntimeError(
                f"Failed to initialize required real tools ({combined}). "
                "Install missing dependencies or disable USE_REAL_TOOLS."
            )

        self._real_tools_initialized = True
        logger.info("Real tools initialized successfully")

    def enable_real_tools(self) -> None:
        """Enable real tools instead of mock tools."""
        if not self._real_tools_initialized:
            self._initialize_real_tools()
        self.use_real_tools = True
        logger.info("Real tools enabled")

    def disable_real_tools(self) -> None:
        """Disable real tools and use mock tools."""
        self.use_real_tools = False
        logger.info("Real tools disabled, using mock tools")

    def register_tool(self, tool: Tool | ToolLike) -> None:
        """Register a tool, preferring real tools when available."""
        t: Tool = cast(Tool, tool)
        tool_name = t.name

        if self.use_real_tools:
            if not self._real_tools_initialized:
                self._initialize_real_tools()

            # Replace with the real version when available
            if tool_name in self.real_tools:
                if tool_name == "web_search":
                    if settings.TERMINAL_ONLY:
                        logger.info("Terminal-only mode: skipping web_search registration")
                        return

                    if not (get_api_key("serpapi") or get_api_key("bing") or get_api_key("google")):
                        raise RuntimeError(
                            "web_search requires SERPAPI_KEY, BING_SEARCH_KEY, or GOOGLE_SEARCH_KEY. "
                            "Set USE_REAL_TOOLS=false to use the agent without network search."
                        )

                super().register_tool(self.real_tools[tool_name])
                logger.info("Registered real tool: %s", tool_name)
                return

            if tool_name in {"file_reader", "file_writer", "code_executor"}:
                raise RuntimeError(
                    f"Real tool '{tool_name}' is not available. Ensure dependencies are installed "
                    "or disable USE_REAL_TOOLS."
                )

        # Fall back to provided tool (typically synthetic or custom)
        # Enforce provider readiness for network tools even when real tools are disabled
        if tool_name == "web_search" and not settings.TERMINAL_ONLY:
            raise RuntimeError(
                "web_search requires SERPAPI_KEY, BING_SEARCH_KEY, or GOOGLE_SEARCH_KEY. "
                "Configure an API provider or enable TERMINAL_ONLY."
            )

        super().register_tool(t)
        logger.info("Registered tool: %s", tool_name)

    def execute_action(self, action: Action, retry: bool = True) -> Observation:
        """Execute an action using the appropriate tool."""
        return cast(Observation, super().execute_action(action, retry))

    async def execute_action_async(self, action: Action, retry: bool = True) -> Observation:
        """Async execution helper for enhanced registries."""
        return cast(Observation, await super().execute_action_async(action, retry))

    def get_tool_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tools including per-tool implementation type."""
        stats: Dict[str, Dict[str, Any]] = super().get_tool_stats()

        # Determine type per registered tool
        for tool_name, tool_obj in self.tools.items():
            try:
                impl = type(tool_obj).__name__
                is_real = impl.startswith("Real")
                if tool_name in stats:
                    stats[tool_name]["tool_type"] = "real" if is_real else "mock"
                    stats[tool_name]["impl_class"] = impl
            except Exception:
                continue

        return stats
