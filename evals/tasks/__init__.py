"""Task registry for Narrare Pydantic Evals."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from evals.tasks.runtime import RuntimeTaskFactory
from evals.tasks.smoke import SmokeTaskFactory

EvalTask = Callable[[Any], Awaitable[Any]]


def get_task(suite: str, mode: str) -> EvalTask:
    """Return the task function for a suite and execution mode."""

    if mode == "smoke":
        return SmokeTaskFactory().build(suite)
    if mode == "runtime":
        return RuntimeTaskFactory.from_env().build(suite)
    raise ValueError(f"Unsupported eval mode: {mode}")
