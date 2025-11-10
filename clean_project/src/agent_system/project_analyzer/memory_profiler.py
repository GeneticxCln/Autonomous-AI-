"""Memory profiling helpers wired into the performance tracker."""

from __future__ import annotations

import contextlib
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

try:
    import psutil
except Exception:  # pragma: no cover - optional dependency guard
    psutil = None

from ..performance_tracker import get_performance_tracker
from ..unified_config import unified_config

logger = logging.getLogger(__name__)


@dataclass
class MemoryProfilerConfig:
    enabled: bool = unified_config.project_analysis.profiler_enabled
    label_prefix: str = "project_analysis"


class MemoryProfiler:
    """Context manager friendly profiler that also feeds telemetry."""

    def __init__(self, config: Optional[MemoryProfilerConfig] = None):
        self.config = config or MemoryProfilerConfig()
        self._enabled = self.config.enabled and psutil is not None
        self._tracker = get_performance_tracker()
        self._process = psutil.Process() if self._enabled else None

    @contextlib.contextmanager
    def profile(self, label: str, metadata: Optional[Dict[str, object]] = None):
        """Track RSS delta for the enclosed scope."""
        if not self._enabled or self._process is None:
            yield
            return

        start_rss = self._safe_rss()
        start = time.perf_counter()
        try:
            yield
        finally:
            end_rss = self._safe_rss()
            delta = max(0, end_rss - start_rss)
            duration_ms = (time.perf_counter() - start) * 1000
            label_key = f"{self.config.label_prefix}_{label}"
            if self._tracker:
                self._tracker.track_memory_hotspot(label_key, delta, duration_ms, metadata)

    def snapshot(self) -> Dict[str, object]:
        """Return a quick snapshot for dashboards."""
        if not self._enabled or self._process is None:
            return {"enabled": False}

        info = self._process.memory_info()
        return {
            "enabled": True,
            "rss_bytes": info.rss,
            "vms_bytes": info.vms,
            "timestamp": time.time(),
            "pid": self._process.pid,
        }

    def _safe_rss(self) -> int:
        if not self._enabled or self._process is None:
            return 0
        try:
            return self._process.memory_info().rss
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Failed to read RSS: %s", exc)
            return 0


memory_profiler = MemoryProfiler()
