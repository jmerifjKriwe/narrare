"""Shared fixtures for WritingGraph and invocation pipeline tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.models.function import FunctionModel

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.writing_graph_types import WritingDeps, WritingState, create_writing_graph
from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import PromptInvocationContext, ValidationResult
from narrare_core.ai_invocation.pipeline import (
    FinalizedInvocation,
    InvocationPipeline,
    PreparedInvocation,
)
from narrare_core.prompts.composer import ComposedPrompt

# ---------------------------------------------------------------------------
# InvocationPipeline Fakes
# ---------------------------------------------------------------------------


class SpyPipeline(InvocationPipeline):
    """InvocationPipeline mit Spy für prepare/finalize calls.

    Nutzt Standard-Konstruktor (keine Komponenten = alles PASS).
    Zählt und speichert prepare/finalize Aufrufe.
    """

    def __init__(self) -> None:
        super().__init__()
        self.prepare_calls: list[PromptInvocationContext] = []
        self.finalize_calls: list[tuple[ComposedPrompt, PromptInvocationContext]] = []

    async def prepare(
        self,
        context: PromptInvocationContext,
    ) -> PreparedInvocation:
        self.prepare_calls.append(context)
        return await super().prepare(context)

    async def finalize(
        self,
        prompt: ComposedPrompt,
        context: PromptInvocationContext,
        *,
        prepared: PreparedInvocation | None = None,
    ) -> FinalizedInvocation:
        self.finalize_calls.append((prompt, context))
        return await super().finalize(prompt, context, prepared=prepared)


class FailingPipeline(InvocationPipeline):
    """Pipeline die bei prepare() fehlschlägt (FAIL-Validation)."""

    async def prepare(
        self,
        context: PromptInvocationContext,
    ) -> PreparedInvocation:
        return PreparedInvocation(
            context=context,
            budget=None,
            validation=ValidationResult(
                status=ValidationStatus.FAIL,
                errors=("Variable 'missing_var' is required.",),
            ),
            enrichment_result=None,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mock_composer() -> AsyncMock:
    """Build a PromptComposer mock whose build() returns a ComposedPrompt."""
    mock = AsyncMock()
    mock.build = AsyncMock(
        return_value=ComposedPrompt(system="Composed system prompt.", user="Composed user prompt."),
    )
    return mock


def make_deps(pipeline: InvocationPipeline | None = None, **overrides: Any) -> WritingDeps:
    """Build WritingDeps with sensible defaults."""
    defaults: dict[str, Any] = {
        "registry": AsyncMock(),
        "composer": mock_composer(),
        "genre": "fantasy",
        "tone": "balanced",
        "word_target": 1000,
        "user_id": "user-42",
    }
    defaults.update(overrides)
    if pipeline is not None:
        defaults["invocation_pipeline"] = pipeline
    return WritingDeps(**defaults)


def make_state(**overrides: Any) -> WritingState:
    """Build WritingState with sensible defaults."""
    defaults: dict[str, Any] = {"chapter_id": "ch-01", "novel_id": "novel-1"}
    defaults.update(overrides)
    return WritingState(**defaults)


@pytest.fixture()
def writing_graph():  # type: ignore[no-untyped-def]
    """Build den Writing-Graph einmal pro Test."""
    return create_writing_graph()


# ---------------------------------------------------------------------------
# Error test fixtures (restored from original conftest)
# ---------------------------------------------------------------------------


@pytest.fixture()
def make_agent():  # type: ignore[no-untyped-def]
    """Create a _SimpleAgent(NarrareAgent) for error classification tests.

    The agent uses ``object`` as deps_type so callers can pass ``deps=None``.
    """

    def _build(model):  # type: ignore[no-untyped-def]
        class _SimpleAgent(NarrareAgent[Any, Any]):  # type: ignore[misc]
            pass

        return _SimpleAgent(model=model, deps_type=object)

    return _build


@pytest.fixture()
def make_error_model():  # type: ignore[no-untyped-def]
    """Create a FunctionModel that raises the given exception.

    Args:
        exc: The exception to raise on model call.
        stream: If True, raises during streaming (request_stream); otherwise
            raises during non-streamed request.

    Returns:
        A FunctionModel configured to raise ``exc`` when invoked.
    """

    def _build(exc: BaseException, stream: bool = False) -> FunctionModel:
        if stream:

            async def _stream_func(messages, agent_info):  # type: ignore[no-untyped-def]
                raise exc
                yield  # pragma: no cover — make this an async generator

            return FunctionModel(stream_function=_stream_func)
        else:

            async def _func(messages, agent_info):  # type: ignore[no-untyped-def]
                raise exc

            return FunctionModel(_func)

    return _build
