"""
Enhanced tool registry with real tool support.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .real_tools import RealCodeExecutorTool, RealWebSearchTool
from .tools import Tool, ToolRegistry

logger = logging.getLogger(__name__)


class EnhancedToolRegistry(ToolRegistry):
    """Enhanced tool registry that can use real tools when configured."""

    def __init__(self):
        super().__init__()
        self.use_real_tools = False
        self.real_tools = {}
        self._initialize_real_tools()

    def _initialize_real_tools(self):
        """Initialize real tool instances."""
        try:
            self.real_tools["web_search"] = RealWebSearchTool()
            self.real_tools["code_executor"] = RealCodeExecutorTool()
            # File tools do not require API keys; safe to initialize
            try:
                from .real_tools import RealFileReaderTool, RealFileWriterTool

                self.real_tools["file_reader"] = RealFileReaderTool()
                self.real_tools["file_writer"] = RealFileWriterTool()
            except Exception as fe:
                logger.warning("File tools initialization issue: %s", fe)
            logger.info("Real tools initialized successfully")
        except Exception as e:
            logger.warning("Failed to initialize real tools: %s", e)

    def enable_real_tools(self):
        """Enable real tools instead of mock tools."""
        self.use_real_tools = True
        logger.info("Real tools enabled")

    def disable_real_tools(self):
        """Disable real tools and use mock tools."""
        self.use_real_tools = False
        logger.info("Real tools disabled, using mock tools")

    def register_tool(self, tool: Tool):
        """Register a tool, preferring real tools when available."""
        tool_name = tool.name

        # If we have a real version of this tool and real tools are enabled,
        # replace with the real version
        if self.use_real_tools and tool_name in self.real_tools:
            real_tool = self.real_tools[tool_name]
            super().register_tool(real_tool)
            logger.info("Registered real tool: %s", tool_name)
        else:
            super().register_tool(tool)
            logger.info("Registered tool: %s", tool_name)

    def execute_action(self, action, retry: bool = True):
        """Execute an action using the appropriate tool."""
        return super().execute_action(action, retry)

    async def execute_action_async(self, action, retry: bool = True):
        """Async execution helper for enhanced registries."""
        return await super().execute_action_async(action, retry)

    def get_tool_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tools including real tool info."""
        stats = super().get_tool_stats()

        # Add information about which tools are real vs mock
        for tool_name in self.tools:
            if tool_name in stats:
                stats[tool_name]["tool_type"] = "real" if self.use_real_tools else "mock"

        return stats
