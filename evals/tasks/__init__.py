"""Task registry for Narrare Pydantic Evals."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from evals.tasks.runtime import RuntimeTaskFactory
from evals.tasks.smoke import SmokeTaskFactory

EvalTask = Callable[[Any], Awaitable[Any]]


def available_suites_for_mode(mode: str) -> list[str]:
    """Return suite names that have a task for *mode*, in stable sorted order.

    Single-source: each factory's ``available_suites()`` derives from its
    own ``_task_map()``. The runner uses this to skip smoke-only suites
    gracefully in runtime mode (per the eval-expansion plan: Tier 2/3
    suites are smoke-only).

    Raises:
        ValueError: if *mode* is neither ``"smoke"`` nor ``"runtime"``.
    """

    if mode == "smoke":
        return SmokeTaskFactory().available_suites()
    if mode == "runtime":
        return RuntimeTaskFactory.from_env().available_suites()
    raise ValueError(f"Unsupported eval mode: {mode}")


def get_task(suite: str, mode: str) -> EvalTask:
    """Return the task function for a suite and execution mode.

    Callers running ``--suite all`` should filter via
    ``available_suites_for_mode(mode)`` first — ``build()`` raises
    ``ValueError`` for suites not registered in the requested mode.
    """

    if mode == "smoke":
        return SmokeTaskFactory().build(suite)
    if mode == "runtime":
        return RuntimeTaskFactory.from_env().build(suite)
    raise ValueError(f"Unsupported eval mode: {mode}")
