"""Shared fixtures for agent error classification tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from narrare_core.agents.base import NarrareAgent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _SimpleAgent(NarrareAgent[None, str]):
    """Minimal concrete agent for testing."""


def _error_raiser(exc: BaseException):
    """Return a FunctionModel function that raises the given exception."""

    def _fn(messages: Any, info: Any) -> Any:
        raise exc

    return _fn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_agent():
    """Create a _SimpleAgent with the given model."""

    def _make_agent(
        model: Any | None = None,
    ) -> _SimpleAgent:
        return _SimpleAgent(
            model=model or TestModel(),
            deps_type=type(None),
            output_type=str,
        )

    return _make_agent


@pytest.fixture
def make_error_model():
    """Create FunctionModel that raises the given exception.

    For streaming, provides both function and stream_function.
    """

    def _make_error_model(
        exc: BaseException,
        *,
        stream: bool = False,
    ) -> FunctionModel:
        if stream:

            async def _stream_fn(messages: Any, info: Any) -> AsyncIterator[str]:
                raise exc
                # yield makes this an async generator — required for stream_function
                yield  # type: ignore[unreachable]

            return FunctionModel(_error_raiser(exc), stream_function=_stream_fn)
        return FunctionModel(_error_raiser(exc))

    return _make_error_model
