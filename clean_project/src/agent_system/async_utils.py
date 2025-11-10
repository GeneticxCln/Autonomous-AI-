from __future__ import annotations

import asyncio
import logging
import threading
from functools import partial
from typing import Any, Callable, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


async def run_blocking(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Execute a blocking callable in a dedicated thread and return its result."""
    call = partial(func, *args, **kwargs)
    done = threading.Event()
    result_container: list[T] = []
    error_container: list[BaseException] = []

    def _target() -> None:
        logger.debug(
            "Executing blocking function %s",
            getattr(func, "__qualname__", repr(func)),
        )
        try:
            result_container.append(call())
        except BaseException as exc:  # pragma: no cover - best-effort logging
            error_container.append(exc)
        finally:
            done.set()

    threading.Thread(target=_target, daemon=True).start()

    while not done.is_set():
        await asyncio.sleep(0)

    if error_container:
        exc = error_container[0]
        logger.debug(
            "Blocking function %s raised %s",
            getattr(func, "__qualname__", repr(func)),
            exc,
            exc_info=True,
        )
        raise exc

    result = result_container[0]
    logger.debug(
        "Completed blocking function %s",
        getattr(func, "__qualname__", repr(func)),
    )
    return result
