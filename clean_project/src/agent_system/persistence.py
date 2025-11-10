"""
Legacy persistence compatibility layer.

All persistence operations now delegate to the database-backed
`enhanced_persistence` module so existing imports continue to work.
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import enhanced_persistence as _backend


def save_action_selector(selector: Any, filename: str = "action_selector.json") -> None:
    _backend.save_action_selector(selector, filename)


async def save_action_selector_async(selector: Any, filename: str = "action_selector.json") -> None:
    await _backend.save_action_selector_async(selector, filename)


def load_action_selector(
    selector: Any = None, filename: str = "action_selector.json"
) -> Dict[str, Any]:
    return _backend.load_action_selector(selector, filename)


async def load_action_selector_async(
    selector: Any = None, filename: str = "action_selector.json"
) -> Dict[str, Any]:
    return await _backend.load_action_selector_async(selector, filename)


def save_learning_system(learning_system: Any, filename: str = "learning_system.json") -> None:
    _backend.save_learning_system(learning_system, filename)


async def save_learning_system_async(
    learning_system: Any, filename: str = "learning_system.json"
) -> None:
    await _backend.save_learning_system_async(learning_system, filename)


def load_learning_system(
    learning_system: Any = None, filename: str = "learning_system.json"
) -> Dict[str, Any]:
    return _backend.load_learning_system(learning_system, filename)


async def load_learning_system_async(
    learning_system: Any = None, filename: str = "learning_system.json"
) -> Dict[str, Any]:
    return await _backend.load_learning_system_async(learning_system, filename)


def save_memory_system(memory_system: Any, filename: str = "episodic_memory.json") -> None:
    _backend.save_memory_system(memory_system, filename)


async def save_memory_system_async(
    memory_system: Any, filename: str = "episodic_memory.json"
) -> None:
    await _backend.save_memory_system_async(memory_system, filename)


def load_memory_system(
    memory_system: Any = None, filename: str = "episodic_memory.json"
) -> List[Dict[str, Any]]:
    return _backend.load_memory_system(memory_system, filename)


async def load_memory_system_async(
    memory_system: Any = None, filename: str = "episodic_memory.json"
) -> List[Dict[str, Any]]:
    return await _backend.load_memory_system_async(memory_system, filename)


def save_all(agent: Any) -> None:
    _backend.save_all(agent)


async def save_all_async(agent: Any) -> None:
    await _backend.save_all_async(agent)


def load_all(agent: Any) -> None:
    _backend.load_all(agent)


async def load_all_async(agent: Any) -> None:
    await _backend.load_all_async(agent)


def get_storage_info() -> Dict[str, Any]:
    return _backend.get_storage_info()


async def get_storage_info_async() -> Dict[str, Any]:
    return await _backend.get_storage_info_async()


def get_database_stats() -> Dict[str, int]:
    return _backend.get_database_stats()


async def get_database_stats_async() -> Dict[str, int]:
    return await _backend.get_database_stats_async()


__all__ = [
    "save_action_selector",
    "save_action_selector_async",
    "load_action_selector",
    "load_action_selector_async",
    "save_learning_system",
    "save_learning_system_async",
    "load_learning_system",
    "load_learning_system_async",
    "save_memory_system",
    "save_memory_system_async",
    "load_memory_system",
    "load_memory_system_async",
    "save_all",
    "save_all_async",
    "load_all",
    "load_all_async",
    "get_storage_info",
    "get_storage_info_async",
    "get_database_stats",
    "get_database_stats_async",
]
