"""Incremental parsing utilities with diff-aware context caching."""

from __future__ import annotations

import difflib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..unified_config import unified_config

logger = logging.getLogger(__name__)


@dataclass
class DiffContext:
    content_hash: str
    version: str
    language: str
    lines: List[str]
    updated_at: float = field(default_factory=time.time)


@dataclass
class DiffSummary:
    changed_lines: List[int]
    additions: int
    deletions: int
    total_lines: int
    whitespace_only: bool
    change_ratio: float
    baseline_available: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "changed_lines": self.changed_lines,
            "additions": self.additions,
            "deletions": self.deletions,
            "total_lines": self.total_lines,
            "whitespace_only": self.whitespace_only,
            "change_ratio": self.change_ratio,
            "baseline_available": self.baseline_available,
        }


@dataclass
class DeltaParseDecision:
    reuse_ast: bool
    partial_reparse: bool
    reason: str


class DiffAwareContextCache:
    """Simple LRU cache for diff contexts."""

    def __init__(self, max_entries: int):
        self.max_entries = max_entries
        self._cache: OrderedDict[str, DiffContext] = OrderedDict()

    def get(self, key: str) -> Optional[DiffContext]:
        entry = self._cache.get(key)
        if entry:
            self._cache.move_to_end(key)
        return entry

    def put(self, key: str, context: DiffContext) -> None:
        self._cache[key] = context
        self._cache.move_to_end(key)
        if len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)


class IncrementalParseSystem:
    """Provides diff-aware delta parsing helpers."""

    def __init__(
        self,
        *,
        max_context_entries: Optional[int] = None,
        delta_threshold: Optional[float] = None,
    ):
        max_entries = max_context_entries or unified_config.project_analysis.diff_sample_window
        self.context_cache = DiffAwareContextCache(max_entries=max_entries)
        self.delta_threshold = (
            delta_threshold or unified_config.project_analysis.delta_change_ratio_threshold
        )

    def compute_diff(
        self, key: str, new_content: str, version: str, language: str
    ) -> Tuple[DiffSummary, Optional[DiffContext]]:
        previous = self.context_cache.get(key)
        old_lines = previous.lines if previous else []
        new_lines = self._trim_lines(new_content)
        summary = self._diff(old_lines, new_lines)
        summary.baseline_available = previous is not None
        return summary, previous

    def update_context(
        self,
        key: str,
        *,
        content_hash: str,
        version: str,
        language: str,
        content: str,
    ) -> DiffContext:
        context = DiffContext(
            content_hash=content_hash,
            version=version,
            language=language,
            lines=self._trim_lines(content),
        )
        self.context_cache.put(key, context)
        return context

    def evaluate_delta(
        self, has_previous_ast: bool, summary: DiffSummary
    ) -> DeltaParseDecision:
        if not has_previous_ast:
            return DeltaParseDecision(False, False, "no_baseline")

        if summary.whitespace_only and has_previous_ast:
            return DeltaParseDecision(True, False, "whitespace_only_change")

        if summary.change_ratio <= self.delta_threshold:
            return DeltaParseDecision(False, True, "limited_change")

        return DeltaParseDecision(False, False, "full_reparse")

    def compare_ast_versions(self, old_ast: Any, new_ast: Any) -> Dict[str, Any]:
        if old_ast is None or new_ast is None:
            return {"comparable": False}

        try:
            old_dump = self._safe_dump(old_ast)
            new_dump = self._safe_dump(new_ast)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("AST dump failed: %s", exc)
            return {"comparable": False, "error": str(exc)}

        matcher = difflib.SequenceMatcher(None, old_dump, new_dump)
        similarity = matcher.quick_ratio()
        delta = max(0.0, 1.0 - similarity)
        return {
            "comparable": True,
            "similarity": similarity,
            "delta_ratio": delta,
        }

    def _safe_dump(self, ast_obj: Any) -> str:
        try:
            import ast

            if isinstance(ast_obj, ast.AST):
                return ast.dump(ast_obj, include_attributes=False)
        except Exception:  # pragma: no cover - best-effort
            pass
        return repr(ast_obj)

    def _trim_lines(self, content: str) -> List[str]:
        lines = content.splitlines()
        return [line[:400] for line in lines]

    def _diff(self, old_lines: List[str], new_lines: List[str]) -> DiffSummary:
        max_len = max(len(old_lines), len(new_lines), 1)
        changed_lines: List[int] = []
        additions = 0
        deletions = 0
        whitespace_only = True

        for idx in range(max_len):
            old_line = old_lines[idx] if idx < len(old_lines) else None
            new_line = new_lines[idx] if idx < len(new_lines) else None

            if old_line == new_line:
                continue

            changed_lines.append(idx + 1)
            if new_line is None:
                deletions += 1
            elif old_line is None:
                additions += 1
            else:
                additions += 1
                deletions += 1

            if whitespace_only and not self._is_whitespace_equivalent(old_line, new_line):
                whitespace_only = False

        change_ratio = len(changed_lines) / max_len
        return DiffSummary(
            changed_lines=changed_lines,
            additions=additions,
            deletions=deletions,
            total_lines=len(new_lines),
            whitespace_only=whitespace_only,
            change_ratio=change_ratio,
            baseline_available=False,
        )

    def _is_whitespace_equivalent(self, old_line: Optional[str], new_line: Optional[str]) -> bool:
        old_norm = self._normalize_line(old_line)
        new_norm = self._normalize_line(new_line)
        return old_norm == new_norm

    def _normalize_line(self, line: Optional[str]) -> str:
        if line is None:
            return ""
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            return ""
        return stripped
