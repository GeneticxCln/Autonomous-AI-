"""Kernel cache manager built on top of the AST cache."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional

from .ast_cache import ASTCache, ast_cache
from .memory_guard import MemoryGuardContext

logger = logging.getLogger(__name__)


@dataclass
class KernelArtifact:
    project_id: str
    file_path: str
    version: str
    language: str
    parser: str
    content_hash: str
    ast_digest: str
    stored_at: float
    size_bytes: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KernelFailureRecord:
    project_id: str
    file_path: str
    error: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class KernelCacheManager:
    """Tracks AST cache metadata and failure telemetry."""

    def __init__(self, cache: Optional[ASTCache] = None):
        self.cache = cache or ast_cache
        self._metadata: Dict[str, KernelArtifact] = {}
        self._failures: Deque[KernelFailureRecord] = deque(maxlen=5000)
        self._lock = threading.RLock()

    def _key(self, project_id: str, file_path: str) -> str:
        return f"{project_id}:{file_path}"

    def store_kernel(
        self,
        project_id: str,
        file_path: str,
        *,
        version: str,
        language: str,
        parser: str,
        ast_object: Any,
        content_hash: Optional[str] = None,
        project_size_bytes: Optional[int] = None,
        priority: str = "normal",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[KernelArtifact]:
        """Persist AST plus metadata."""
        content_hash = content_hash or hashlib.sha1(
            f"{project_id}:{file_path}:{version}".encode("utf-8")
        ).hexdigest()

        context = MemoryGuardContext(
            project_id=project_id,
            project_size_bytes=project_size_bytes,
            priority=priority,
        )

        stored = self.cache.store(
            project_id,
            file_path,
            ast_object,
            content_hash=content_hash,
            version=version,
            language=language,
            context=context,
        )
        if not stored:
            logger.debug("AST cache rejected kernel for %s:%s", project_id, file_path)
            return None

        digest_source = f"{parser}:{content_hash}".encode("utf-8")
        artifact = KernelArtifact(
            project_id=project_id,
            file_path=file_path,
            version=version,
            language=language,
            parser=parser,
            content_hash=content_hash,
            ast_digest=hashlib.sha1(digest_source).hexdigest(),
            stored_at=time.time(),
            size_bytes=self.cache.get(project_id, file_path, content_hash=content_hash).size_bytes,
            metadata=metadata or {},
        )

        with self._lock:
            self._metadata[self._key(project_id, file_path)] = artifact

        return artifact

    def get_kernel(
        self,
        project_id: str,
        file_path: str,
        *,
        content_hash: Optional[str] = None,
        version: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch AST and metadata."""
        entry = self.cache.get(
            project_id,
            file_path,
            content_hash=content_hash,
            version=version,
        )
        if not entry:
            return None

        with self._lock:
            artifact = self._metadata.get(self._key(project_id, file_path))

        return {"ast": entry.ast_object, "artifact": artifact}

    def invalidate(self, project_id: str, file_path: Optional[str] = None):
        self.cache.invalidate(project_id, file_path)
        if file_path:
            with self._lock:
                self._metadata.pop(self._key(project_id, file_path), None)
        else:
            with self._lock:
                keys = [key for key in self._metadata.keys() if key.startswith(f"{project_id}:")]
                for key in keys:
                    self._metadata.pop(key, None)

    def record_failure(
        self,
        project_id: str,
        file_path: str,
        error: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Track parse failures for recovery analysis."""
        self._failures.append(
            KernelFailureRecord(
                project_id=project_id,
                file_path=file_path,
                error=error,
                metadata=metadata or {},
            )
        )

    def get_failure_report(self, limit: int = 20):
        return list(self._failures)[-limit:]

    def stats(self) -> Dict[str, Any]:
        cache_stats = self.cache.stats()
        with self._lock:
            meta_count = len(self._metadata)
        cache_stats.update({"artifacts": meta_count, "failures_tracked": len(self._failures)})
        return cache_stats

    def apply_cache_overrides(
        self,
        *,
        max_entries: Optional[int] = None,
        max_bytes: Optional[int] = None,
        ttl_seconds: Optional[int] = None,
    ):
        """Delegate cache tuning to the underlying AST cache."""
        self.cache.reconfigure(
            max_entries=max_entries,
            max_bytes=max_bytes,
            ttl_seconds=ttl_seconds,
        )


kernel_cache_manager = KernelCacheManager()
