"""AST cache with LRU eviction and memory guard integration."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..unified_config import unified_config
from .memory_guard import MemoryGuard, MemoryGuardContext, memory_guard

logger = logging.getLogger(__name__)


def _default_max_bytes() -> int:
    return unified_config.project_analysis.ast_cache_max_mb * 1024 * 1024


@dataclass
class ASTCacheConfig:
    """Configuration for AST caching."""

    max_entries: int = unified_config.project_analysis.ast_cache_entries
    max_bytes: int = field(default_factory=_default_max_bytes)
    ttl_seconds: int = unified_config.project_analysis.ast_cache_ttl_seconds


@dataclass
class ASTCacheEntry:
    """Metadata stored alongside parsed ASTs."""

    project_id: str
    file_path: str
    content_hash: str
    version: str
    language: str
    ast_object: Any
    size_bytes: int
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: int) -> bool:
        return ttl_seconds > 0 and (time.time() - self.created_at) > ttl_seconds

    def touch(self) -> None:
        self.accessed_at = time.time()


class ASTCache:
    """Provides LRU caching for parsed AST objects."""

    def __init__(
        self, config: Optional[ASTCacheConfig] = None, guard: Optional[MemoryGuard] = None
    ):
        self.config = config or ASTCacheConfig()
        self.guard = guard or memory_guard
        self._entries: "OrderedDict[str, ASTCacheEntry]" = OrderedDict()
        self._lock = threading.RLock()
        self._current_bytes = 0

    def _make_key(self, project_id: str, file_path: str) -> str:
        return hashlib.sha1(f"{project_id}:{file_path}".encode("utf-8")).hexdigest()

    def get(
        self,
        project_id: str,
        file_path: str,
        *,
        content_hash: Optional[str] = None,
        version: Optional[str] = None,
    ) -> Optional[ASTCacheEntry]:
        """Retrieve a cached AST if it matches the provided identifiers."""
        key = self._make_key(project_id, file_path)
        with self._lock:
            entry = self._entries.get(key)
            if not entry:
                return None
            if entry.is_expired(self.config.ttl_seconds):
                self._evict_entry_locked(key)
                return None
            if content_hash and entry.content_hash != content_hash:
                return None
            if version and entry.version != version:
                return None
            entry.touch()
            self._entries.move_to_end(key)
            return entry

    def store(
        self,
        project_id: str,
        file_path: str,
        ast_object: Any,
        *,
        content_hash: str,
        version: str,
        language: str,
        context: Optional[MemoryGuardContext] = None,
    ) -> bool:
        """Store an AST result in the cache."""
        entry_size = self._estimate_size(ast_object)
        key = self._make_key(project_id, file_path)

        with self._lock:
            existing = self._entries.get(key)

            if len(self._entries) >= self.config.max_entries and key not in self._entries:
                self._evict_lru_locked(1)

            if (self._current_bytes + entry_size) > self.config.max_bytes:
                excess = self._current_bytes + entry_size - self.config.max_bytes
                self._evict_until_locked(excess)

            reclaim = self.guard.required_reclaim(entry_size, context)
            if reclaim > 0:
                self._evict_until_locked(reclaim)
                # Try again after eviction
                if self.guard.required_reclaim(entry_size, context) > 0:
                    logger.debug(
                        "Memory guard rejected AST cache entry for %s:%s", project_id, file_path
                    )
                    return False

            previous_entry = None
            if existing:
                previous_entry = existing
                self._entries.pop(key)
                self._current_bytes -= existing.size_bytes
                self.guard.release_allocation(key)

            if not self.guard.reserve_allocation(key, entry_size, context):
                logger.debug(
                    "Reservation rejected for AST cache entry %s:%s", project_id, file_path
                )
                if previous_entry:
                    # Restore previous reservation to keep cache consistent
                    if self.guard.reserve_allocation(key, previous_entry.size_bytes, context):
                        self._entries[key] = previous_entry
                        self._entries.move_to_end(key)
                        self._current_bytes += previous_entry.size_bytes
                return False

            entry = ASTCacheEntry(
                project_id=project_id,
                file_path=file_path,
                content_hash=content_hash,
                version=version,
                language=language,
                ast_object=ast_object,
                size_bytes=entry_size,
            )
            self._entries[key] = entry
            self._entries.move_to_end(key)
            self._current_bytes += entry_size
            return True

    def invalidate(self, project_id: str, file_path: Optional[str] = None) -> None:
        """Invalidate cache entries for a project or a specific file."""
        with self._lock:
            keys = list(self._entries.keys())
            for key in keys:
                entry = self._entries[key]
                if entry.project_id != project_id:
                    continue
                if file_path and entry.file_path != file_path:
                    continue
                self._evict_entry_locked(key)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "entries": len(self._entries),
                "bytes": self._current_bytes,
                "max_entries": self.config.max_entries,
                "max_bytes": self.config.max_bytes,
            }

    def _evict_lru_locked(self, count: int) -> None:
        for _ in range(min(count, len(self._entries))):
            key, _ = self._entries.popitem(last=False)
            self.guard.release_allocation(key)

    def _evict_entry_locked(self, key: str) -> None:
        entry = self._entries.pop(key, None)
        if entry:
            self._current_bytes -= entry.size_bytes
            self.guard.release_allocation(key)

    def reconfigure(
        self,
        *,
        max_entries: Optional[int] = None,
        max_bytes: Optional[int] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Adjust cache parameters at runtime."""
        with self._lock:
            if max_entries:
                self.config.max_entries = max_entries
                if len(self._entries) > max_entries:
                    self._evict_lru_locked(len(self._entries) - max_entries)
            if max_bytes:
                self.config.max_bytes = max_bytes
                if self._current_bytes > max_bytes:
                    self._evict_until_locked(self._current_bytes - max_bytes)
            if ttl_seconds:
                self.config.ttl_seconds = ttl_seconds

    def _evict_until_locked(self, reclaim_bytes: int) -> None:
        reclaimed = 0
        while self._entries and reclaimed < reclaim_bytes:
            key, entry = self._entries.popitem(last=False)
            reclaimed += entry.size_bytes
            self.guard.release_allocation(key)
            self._current_bytes -= entry.size_bytes

    def _estimate_size(self, ast_object: Any) -> int:
        """Rudimentary heuristic for AST object size."""
        try:
            import sys

            size = sys.getsizeof(ast_object)
            if isinstance(ast_object, (list, tuple)):
                size += sum(self._estimate_size(item) for item in ast_object[:20])
            elif hasattr(ast_object, "__dict__"):
                size += sum(
                    self._estimate_size(value) for value in list(vars(ast_object).values())[:20]
                )
            return min(size, self.config.max_bytes // 4)
        except Exception:
            return 1024


ast_cache = ASTCache()
