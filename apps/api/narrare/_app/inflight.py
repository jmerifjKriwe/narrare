"""Graceful-shutdown drain for in-flight background tasks (ADR-080).

Background work runs in-process via ``asyncio.create_task`` with
module-level ``_INFLIGHT_TASKS`` GC-guard sets (see
``narrare.kb.embedding_hooks`` and ``narrare.series.tasks``).  On graceful
shutdown these tasks must be cancelled and awaited **before** the database
engine is disposed, so no background coroutine can touch a disposed pool.

The drain is cancel-first (no bounded wait): every tracked task is
cancelled, then ``asyncio.gather(..., return_exceptions=True)`` waits for
each to finish its cancellation path.  Cancellation is an intentional,
expected part of shutdown — each cancelled task is logged at **info**
level, never at error (RULE-11).  This module is deliberately small and
single-purpose (RULE-04).
"""

from __future__ import annotations

import asyncio
import importlib
from contextlib import suppress
from typing import cast

import structlog

logger = structlog.get_logger(__name__)

#: Dotted module names whose module-level ``_INFLIGHT_TASKS`` sets are
#: drained.  A tuple so the drain sites are explicit and the collection
#: helper stays trivially testable.
_DRAIN_SOURCES: tuple[str, ...] = (
    "narrare.kb.embedding_hooks",
    "narrare.series.tasks",
)


def _snapshot_tasks() -> list[tuple[str, asyncio.Task[None]]]:
    """Collect ``(source, task)`` pairs from every registered drain source.

    Iterates over a copy of each GC-guard set (``tuple(inflight)``) so a
    done-callback that discards a completed task cannot mutate the set
    mid-iteration.  Sources without a ``_INFLIGHT_TASKS`` set are skipped
    defensively.
    """
    pending: list[tuple[str, asyncio.Task[None]]] = []
    for module_name in _DRAIN_SOURCES:
        module = importlib.import_module(module_name)
        inflight = getattr(module, "_INFLIGHT_TASKS", None)
        if isinstance(inflight, set):
            tracked = cast("set[asyncio.Task[None]]", inflight)
            pending.extend((module_name, task) for task in tuple(tracked))
    return pending


async def drain_inflight_tasks() -> None:
    """Cancel and await every in-flight background task (graceful shutdown).

    Snapshots all tracked tasks, cancels them, then awaits completion via
    ``asyncio.gather(..., return_exceptions=True)`` so a task that raises
    during its cancellation path never propagates to the caller.  Each
    cancelled task is logged at **info** with its task name and source
    module — intentional cancellation is not an error (RULE-11).

    No-op when no tasks are tracked: returns immediately without logging.
    """
    pending = _snapshot_tasks()
    if not pending:
        return

    for _source, task in pending:
        task.cancel()

    with suppress(asyncio.CancelledError):
        await asyncio.gather(*(task for _source, task in pending), return_exceptions=True)

    for source, task in pending:
        logger.info(
            "background_task_cancelled_shutdown",
            task_name=task.get_name(),
            source=source,
        )
