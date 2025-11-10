from __future__ import annotations

from agent_system.project_analyzer.ast_cache import ASTCache, ASTCacheConfig
from agent_system.project_analyzer.incremental_parser import IncrementalParseSystem
from agent_system.project_analyzer.kernel_cache_manager import KernelCacheManager
from agent_system.project_analyzer.large_project_analyzer import LargeProjectAnalyzer
from agent_system.project_analyzer.stress_tester import ProjectStressTester
from agent_system.project_analyzer.memory_guard import (
    MemoryGuard,
    MemoryGuardConfig,
    MemoryGuardContext,
)
from agent_system.project_analyzer.memory_profiler import MemoryProfiler, MemoryProfilerConfig


def _make_guard() -> MemoryGuard:
    return MemoryGuard(
        MemoryGuardConfig(
            soft_limit_bytes=200_000,
            hard_limit_bytes=400_000,
            pressure_threshold=0.95,
        )
    )


def _make_cache(max_entries: int = 8) -> ASTCache:
    config = ASTCacheConfig(max_entries=max_entries, max_bytes=400_000, ttl_seconds=120)
    return ASTCache(config=config, guard=_make_guard())


def _make_analyzer(cache: ASTCache) -> LargeProjectAnalyzer:
    manager = KernelCacheManager(cache)
    profiler = MemoryProfiler(MemoryProfilerConfig(enabled=False))
    incremental = IncrementalParseSystem(max_context_entries=32, delta_threshold=0.5)
    return LargeProjectAnalyzer(
        cache_manager=manager,
        profiler=profiler,
        incremental_parser=incremental,
    )


def test_ast_cache_lru_eviction():
    cache = _make_cache(max_entries=2)
    ctx = MemoryGuardContext(project_id="proj")

    assert cache.store(
        "proj",
        "file_a.py",
        {"node": 1},
        content_hash="hash_a",
        version="v1",
        language="python",
        context=ctx,
    )
    assert cache.store(
        "proj",
        "file_b.py",
        {"node": 2},
        content_hash="hash_b",
        version="v1",
        language="python",
        context=ctx,
    )
    assert cache.store(
        "proj",
        "file_c.py",
        {"node": 3},
        content_hash="hash_c",
        version="v1",
        language="python",
        context=ctx,
    )

    assert cache.get("proj", "file_a.py", content_hash="hash_a") is None
    assert cache.get("proj", "file_b.py", content_hash="hash_b") is not None
    assert cache.get("proj", "file_c.py", content_hash="hash_c") is not None


def test_kernel_cache_store_and_retrieve():
    cache = _make_cache(max_entries=4)
    manager = KernelCacheManager(cache)
    artifact = manager.store_kernel(
        "proj",
        "file_a.py",
        version="v1",
        language="python",
        parser="python_ast",
        ast_object={"node": 1},
        content_hash="hash_a",
    )
    assert artifact is not None

    payload = manager.get_kernel("proj", "file_a.py", content_hash="hash_a")
    assert payload is not None
    assert payload["artifact"].parser == "python_ast"
    assert payload["artifact"].content_hash == "hash_a"


def test_large_project_analyzer_primes_cache(tmp_path):
    cache = _make_cache(max_entries=10)
    analyzer = _make_analyzer(cache)

    file_path = tmp_path / "sample.py"
    file_path.write_text("def demo():\n    return 42\n", encoding="utf-8")

    report = analyzer.prime_cache("proj", tmp_path, version="v1")
    assert report.files_processed == 1
    assert report.cache_misses == 1
    assert report.cache_hits == 0
    assert report.delta_reuses == 0
    assert report.partial_reparses == 0
    assert report.specialization_plan["domain"] in {"backend", "general"}

    report_cached = analyzer.prime_cache("proj", tmp_path, version="v1")
    assert report_cached.cache_hits == 1
    assert report_cached.cache_misses == 0
    assert report_cached.delta_reuses == 0


def test_large_project_analyzer_delta_reuse_on_whitespace(tmp_path):
    cache = _make_cache(max_entries=10)
    analyzer = _make_analyzer(cache)

    file_path = tmp_path / "sample.py"
    file_path.write_text("def demo():\n    return 42\n", encoding="utf-8")
    analyzer.prime_cache("proj", tmp_path, version="v1")

    # introduce trailing whitespace only
    file_path.write_text("def demo():\n    return 42  \n", encoding="utf-8")
    report = analyzer.prime_cache("proj", tmp_path, version="v2")

    assert report.cache_misses == 1
    assert report.delta_reuses == 1
    assert report.files[0].delta_mode == "reuse"


def test_specialization_domain_override(tmp_path):
    cache = _make_cache(max_entries=5)
    analyzer = _make_analyzer(cache)
    doc_file = tmp_path / "README.md"
    doc_file.write_text("# Heading\n\nBody text\n", encoding="utf-8")

    report = analyzer.prime_cache("proj", tmp_path, version="v1", domain="docs")
    assert report.specialization_plan["domain"] == "docs"
    assert report.specialization_plan["memory_priority"] == "low"


def test_project_stress_tester_growth_scenario():
    cache = _make_cache(max_entries=20)
    analyzer = _make_analyzer(cache)
    tester = ProjectStressTester(analyzer)
    metrics = tester.simulate_growth("proj", [3])
    assert metrics[0].file_count == 3
    assert metrics[0].failures == 0
