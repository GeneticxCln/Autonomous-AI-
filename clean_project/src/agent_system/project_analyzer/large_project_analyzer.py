"""Large project analyzer orchestrating parsing and caching."""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..unified_config import unified_config
from .incremental_parser import IncrementalParseSystem
from .kernel_cache_manager import KernelCacheManager, kernel_cache_manager
from .memory_profiler import MemoryProfiler, memory_profiler
from .specialization import DomainSpecializationLayer

logger = logging.getLogger(__name__)


@dataclass
class FileAnalysisResult:
    file_path: str
    language: str
    parser: str
    cached: bool
    content_hash: str
    duration_ms: float
    error: Optional[str] = None
    diff_summary: Optional[Dict[str, Any]] = None
    delta_mode: Optional[str] = None


@dataclass
class AnalyzerReport:
    project_id: str
    version: str
    files_processed: int
    cache_hits: int
    cache_misses: int
    delta_reuses: int
    partial_reparses: int
    duration_ms: float
    files: List[FileAnalysisResult] = field(default_factory=list)
    failures: List[FileAnalysisResult] = field(default_factory=list)
    cache_stats: Dict[str, int] = field(default_factory=dict)
    specialization_plan: Optional[Dict[str, Any]] = None


class LargeProjectAnalyzer:
    """Coordinates parsing, caching, and metric capture."""

    def __init__(
        self,
        *,
        cache_manager: KernelCacheManager = kernel_cache_manager,
        profiler: MemoryProfiler = memory_profiler,
        incremental_parser: Optional[IncrementalParseSystem] = None,
        specialization_layer: Optional[DomainSpecializationLayer] = None,
    ):
        self.config = unified_config.project_analysis
        self.kernel_cache = cache_manager
        self.profiler = profiler
        self.incremental_parser = incremental_parser or IncrementalParseSystem()
        self.specialization_layer = specialization_layer or DomainSpecializationLayer()

    def prime_cache(
        self,
        project_id: str,
        project_root: Path | str,
        *,
        version: str,
        domain: Optional[str] = None,
        files: Optional[Sequence[str | Path]] = None,
        language: Optional[str] = None,
        max_files: Optional[int] = None,
    ) -> AnalyzerReport:
        """Parse a batch of files and populate the kernel cache."""
        start = time.perf_counter()
        root_path = Path(project_root)
        target_files = self._collect_files(root_path, files, max_files)
        project_size = sum(f.stat().st_size for f in target_files if f.exists())
        file_stats = self._summarize_files(target_files)
        specialization_plan = self.specialization_layer.plan_for_project(
            file_stats=file_stats,
            project_size_bytes=project_size,
            domain_override=domain,
        )
        cache_overrides = specialization_plan.cache_overrides
        self.kernel_cache.apply_cache_overrides(
            max_entries=cache_overrides.get("max_entries"),
            ttl_seconds=cache_overrides.get("ttl_seconds"),
        )
        priority = specialization_plan.memory_priority
        if priority != "high" and (len(target_files) > 2000 or project_size > 2 * 1024**3):
            priority = "high"

        cache_hits = 0
        cache_misses = 0
        delta_reuses = 0
        partial_reparses = 0
        results: List[FileAnalysisResult] = []
        failures: List[FileAnalysisResult] = []

        for file_path in target_files:
            relative_path = str(file_path.relative_to(root_path))
            file_key = f"{project_id}:{relative_path}"
            diff_summary_dict: Optional[Dict[str, Any]] = None
            delta_mode = "full"

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                logger.warning("Failed to read %s: %s", file_path, exc)
                failures.append(
                    FileAnalysisResult(
                        file_path=relative_path,
                        language="unknown",
                        parser="io",
                        cached=False,
                        content_hash="",
                        duration_ms=0.0,
                        error=str(exc),
                        diff_summary=None,
                        delta_mode="error",
                    )
                )
                continue

            content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()
            cached = self.kernel_cache.get_kernel(
                project_id,
                relative_path,
                content_hash=content_hash,
                version=version,
            )

            if cached:
                cache_hits += 1
                artifact = cached["artifact"]
                results.append(
                    FileAnalysisResult(
                        file_path=relative_path,
                        language=artifact.language if artifact else language or "unknown",
                        parser=artifact.parser if artifact else "unknown",
                        cached=True,
                        content_hash=content_hash,
                        duration_ms=0.0,
                        diff_summary=None,
                        delta_mode="cached",
                    )
                )
                self.incremental_parser.update_context(
                    file_key,
                    content_hash=content_hash,
                    version=version,
                    language=artifact.language if artifact else language or "unknown",
                    content=content,
                )
                continue

            cache_misses += 1
            detected_language = self._detect_language(file_path, language)
            # compute diff summary before parsing
            diff_summary, _ = self.incremental_parser.compute_diff(
                file_key,
                content,
                version,
                detected_language,
            )
            diff_summary_dict = diff_summary.to_dict()
            previous_payload = self.kernel_cache.get_kernel(project_id, relative_path)
            previous_ast = previous_payload["ast"] if previous_payload else None
            decision = self.incremental_parser.evaluate_delta(
                previous_ast is not None, diff_summary
            )

            if decision.reuse_ast and previous_ast is not None:
                ast_obj = previous_ast
                parser_name = "delta_reuse"
                parse_duration_ms = 0.0
                delta_mode = "reuse"
                delta_reuses += 1
            else:
                with self.profiler.profile(
                    f"parse_{detected_language}",
                    metadata={"file": relative_path, "project_id": project_id},
                ):
                    parse_start = time.perf_counter()
                    try:
                        ast_obj, parser_name = self._build_ast(content, detected_language)
                        parse_duration_ms = (time.perf_counter() - parse_start) * 1000
                    except Exception as exc:  # pragma: no cover - depends on source
                        logger.exception("AST construction failed for %s", relative_path)
                        self.kernel_cache.record_failure(
                            project_id,
                            relative_path,
                            str(exc),
                            metadata={"language": detected_language},
                        )
                        failure = FileAnalysisResult(
                            file_path=relative_path,
                            language=detected_language,
                            parser="parse_error",
                            cached=False,
                            content_hash=content_hash,
                            duration_ms=0.0,
                            error=str(exc),
                            diff_summary=diff_summary_dict,
                            delta_mode="error",
                        )
                        failures.append(failure)
                        continue

                if decision.partial_reparse:
                    partial_reparses += 1
                    delta_mode = "partial"
                else:
                    delta_mode = "full"

            ast_delta = (
                self.incremental_parser.compare_ast_versions(previous_ast, ast_obj)
                if previous_ast is not None
                else None
            )

            artifact = self.kernel_cache.store_kernel(
                project_id,
                relative_path,
                version=version,
                language=detected_language,
                parser=parser_name,
                ast_object=ast_obj,
                content_hash=content_hash,
                project_size_bytes=project_size,
                priority=priority,
                metadata={
                    "lines": content.count("\n") + 1,
                    "diff": diff_summary_dict,
                    "ast_delta": ast_delta,
                    "delta_mode": delta_mode,
                    "specialization_domain": specialization_plan.domain,
                    "resource_budget": specialization_plan.resource_budget,
                },
            )

            if artifact is None:
                self.kernel_cache.record_failure(
                    project_id,
                    relative_path,
                    "cache_rejection",
                    metadata={"language": detected_language, "reason": "memory_guard"},
                )

            results.append(
                FileAnalysisResult(
                    file_path=relative_path,
                    language=detected_language,
                    parser=parser_name,
                    cached=artifact is not None,
                    content_hash=content_hash,
                    duration_ms=parse_duration_ms,
                    error=None if artifact else "cache_rejection",
                    diff_summary=diff_summary_dict,
                    delta_mode=delta_mode if artifact else "rejected",
                )
            )
            self.incremental_parser.update_context(
                file_key,
                content_hash=content_hash,
                version=version,
                language=detected_language,
                content=content,
            )

        duration_ms = (time.perf_counter() - start) * 1000
        report = AnalyzerReport(
            project_id=project_id,
            version=version,
            files_processed=len(target_files),
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            delta_reuses=delta_reuses,
            partial_reparses=partial_reparses,
            duration_ms=duration_ms,
            files=results,
            failures=failures,
            cache_stats=self.kernel_cache.stats(),
            specialization_plan=specialization_plan.to_dict(),
        )
        return report

    def _collect_files(
        self,
        root: Path,
        files: Optional[Sequence[str | Path]],
        max_files: Optional[int],
    ) -> List[Path]:
        if files:
            resolved = []
            for file_ref in files:
                path_obj = Path(file_ref)
                if not path_obj.is_absolute():
                    path_obj = root / path_obj
                resolved.append(path_obj)
            paths = resolved
        else:
            paths = list(root.rglob("*.py"))

        paths = [path for path in paths if path.is_file()]
        paths.sort()
        if max_files:
            paths = paths[:max_files]
        return paths

    def _summarize_files(self, paths: List[Path]) -> Dict[str, int]:
        stats: Dict[str, int] = {}
        for path in paths:
            ext = path.suffix.lower().lstrip(".")
            if not ext:
                ext = "plain"
            stats[ext] = stats.get(ext, 0) + 1
        return stats

    def _detect_language(self, file_path: Path, override: Optional[str]) -> str:
        if override:
            return override
        ext = file_path.suffix.lower()
        return {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".json": "json",
            ".md": "markdown",
        }.get(ext, unified_config.project_analysis.default_language or "python")

    def _build_ast(self, content: str, language: str) -> Tuple[Any, str]:
        """Build an AST-like structure for supported languages."""
        parser = "python_ast"
        if language == "python":
            return ast.parse(content), parser
        if language == "json":
            parser = "json_loader"
            return json.loads(content or "{}"), parser
        if language in {"javascript", "typescript"}:
            parser = "line_tokenizer"
            return self._fallback_tree(content), parser
        if language == "markdown":
            parser = "markdown_outline"
            return self._markdown_outline(content), parser
        parser = "text_block"
        return self._fallback_tree(content), parser

    def _fallback_tree(self, content: str) -> list[dict[str, Any]]:
        lines = content.splitlines()
        return [{"line": idx + 1, "content": line[:200]} for idx, line in enumerate(lines[:1000])]

    def _markdown_outline(self, content: str) -> list[dict[str, Any]]:
        outline = []
        for idx, line in enumerate(content.splitlines(), start=1):
            if line.startswith("#"):
                outline.append({"line": idx, "heading": line.strip()})
        return outline


large_project_analyzer = LargeProjectAnalyzer()
