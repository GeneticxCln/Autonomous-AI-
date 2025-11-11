"""Context-aware memory guard for large project analysis."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from ..unified_config import unified_config

# Optional psutil import with typing-friendly fallback
psutil: Any | None = None
try:
    import psutil as _psutil
    psutil = _psutil
except Exception:  # pragma: no cover - optional dependency
    psutil = None

logger = logging.getLogger(__name__)


def _mb_to_bytes(value_mb: int) -> int:
    return value_mb * 1024 * 1024


@dataclass
class MemoryGuardConfig:
    """Configuration for the memory guard."""

    soft_limit_bytes: int = _mb_to_bytes(unified_config.project_analysis.memory_soft_limit_mb)
    hard_limit_bytes: int = _mb_to_bytes(unified_config.project_analysis.memory_hard_limit_mb)
    pressure_threshold: float = unified_config.project_analysis.memory_pressure_threshold
    context_multiplier: float = 0.15


@dataclass
class MemoryGuardContext:
    """Describes the workload requesting memory."""

    project_id: str
    project_size_bytes: Optional[int] = None
    domain: Optional[str] = None
    priority: str = "normal"  # low, normal, high


class MemoryGuard:
    """Tracks memory allocations and applies adaptive limits."""

    def __init__(self, config: Optional[MemoryGuardConfig] = None):
        self.config = config or MemoryGuardConfig()
        self._lock = threading.RLock()
        self._allocations: Dict[str, int] = {}
        self._current_bytes = 0
        self._last_pressure_sample = 0.0
        self._last_pressure_value = 0.0

    def get_limits(self, context: Optional[MemoryGuardContext] = None) -> Tuple[int, int]:
        """Return (soft_limit_bytes, hard_limit_bytes) for a context."""
        soft_limit = self.config.soft_limit_bytes
        hard_limit = self.config.hard_limit_bytes

        if context and context.project_size_bytes:
            project_gb = context.project_size_bytes / (1024**3)
            scale = 1 + min(project_gb * self.config.context_multiplier, 1.0)
            soft_limit = int(min(soft_limit * scale, hard_limit * 0.95))

        if context and context.priority == "low":
            soft_limit = int(soft_limit * 0.85)
        elif context and context.priority == "high":
            soft_limit = int(min(soft_limit * 1.15, hard_limit * 0.98))

        return soft_limit, hard_limit

    def required_reclaim(
        self, bytes_required: int, context: Optional[MemoryGuardContext] = None
    ) -> int:
        """Return how many bytes must be reclaimed before allocating."""
        with self._lock:
            soft_limit, hard_limit = self.get_limits(context)
            projected = self._current_bytes + bytes_required

            if projected > hard_limit:
                return projected - hard_limit

            reclaim = max(0, projected - soft_limit)

            if self._get_system_pressure() >= self.config.pressure_threshold:
                reclaim = max(reclaim, int(soft_limit * 0.1))

            return reclaim

    def reserve_allocation(
        self, key: str, bytes_required: int, context: Optional[MemoryGuardContext] = None
    ) -> bool:
        """Reserve memory accounting for a cache entry."""
        with self._lock:
            reclaim = self.required_reclaim(bytes_required, context)
            if reclaim > 0:
                return False

            existing = self._allocations.get(key, 0)
            self._current_bytes -= existing
            self._allocations[key] = bytes_required
            self._current_bytes += bytes_required
            return True

    def release_allocation(self, key: str) -> None:
        """Release previously reserved memory accounting."""
        with self._lock:
            size = self._allocations.pop(key, 0)
            if size:
                self._current_bytes = max(0, self._current_bytes - size)

    def current_usage(self) -> int:
        with self._lock:
            return self._current_bytes

    def _get_system_pressure(self) -> float:
        """Return percentage (0-1) of system memory usage."""
        now = time.time()
        if now - self._last_pressure_sample < 1.0:
            return self._last_pressure_value

        if psutil is None:  # pragma: no cover - fallback path
            return 0.0

        try:
            virtual_mem = psutil.virtual_memory()
            self._last_pressure_value = virtual_mem.percent / 100.0
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Failed to sample memory pressure: %s", exc)
            self._last_pressure_value = 0.0

        self._last_pressure_sample = now
        return self._last_pressure_value

    def get_stats(self) -> Dict[str, int]:
        """Expose guard stats for dashboards."""
        with self._lock:
            return {
                "tracked_entries": len(self._allocations),
                "allocated_bytes": self._current_bytes,
            }


# Global guard instance for reuse across analyzers
memory_guard = MemoryGuard()
