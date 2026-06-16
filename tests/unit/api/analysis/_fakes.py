"""Shared Fake classes for analysis service unit tests.

Centralises Fake agent classes used across multiple test files
to avoid duplication and keep each test file within RULE-04 limits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from narrare_core.agents.pov_types import POVDetectionOutput
from narrare_core.agents.readability_types import ReadabilityAgentOutput
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.ai_invocation.pipeline import (
        FinalizedInvocation,
        PreparedInvocation,
    )
    from narrare_core.prompts.composer import ComposedPrompt


class FakePOVAgent:
    """Fake POVDetectionAgent — returns a predetermined output or raises."""

    def __init__(
        self,
        output: POVDetectionOutput | None = None,
        error: Exception | None = None,
    ) -> None:
        self._output = output or POVDetectionOutput(overall_assessment="ok")
        self._error = error
        self.run_called: bool = False
        self.last_deps: Any = None

    async def run(self, prompt: str, deps: Any = None, **kwargs: Any) -> POVDetectionOutput:
        self.run_called = True
        self.last_deps = deps
        if self._error:
            raise self._error
        return self._output


class FakeReadabilityAgent:
    """Fake ReadabilityAgent — returns predetermined output or raises."""

    def __init__(
        self,
        output: ReadabilityAgentOutput | None = None,
        error: Exception | None = None,
    ) -> None:
        self._output = output or ReadabilityAgentOutput(overall_assessment="Good.")
        self._error = error
        self.run_called: bool = False
        self.last_deps: Any = None

    async def run(self, prompt: str, deps: Any = None, **kwargs: Any) -> ReadabilityAgentOutput:
        self.run_called = True
        self.last_deps = deps
        if self._error:
            raise self._error
        return self._output


class SeededKBRepository:
    """KB repo stub returning seeded character names from list_entries.

    Standalone stub (does not inherit FakeKBRepository) — only
    ``list_entries`` is exercised by the analysis service tests.
    """

    def __init__(self, character_names: list[str]) -> None:
        self._names = character_names
        self.calls: list[CallRecord] = []

    async def list_entries(
        self,
        novel_id: UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Any], int]:
        self.calls.append(CallRecord("list_entries"))
        entries = [type("Entry", (), {"name": n})() for n in self._names]
        return entries, len(entries)


class SpyInvocationPipeline(InvocationPipeline):
    """InvocationPipeline that records prepare/finalize calls for assertions.

    Subclasses the real :class:`InvocationPipeline` so it is type-compatible
    with the ``invocation_pipeline`` parameter on analysis services. All
    components default to ``None``, so ``prepare``/``finalize`` return PASS
    results and ``compose_invocation`` proceeds without error.

    Used to verify that analysis services route through ``compose_invocation``
    (ADR-048 Mode 2) with the expected ``feature_id``, rather than the
    deprecated ``safe_record_evidence`` placeholder-evidence path.
    """

    def __init__(self) -> None:
        super().__init__()
        self.prepare_calls: list[PromptInvocationContext] = []
        self.finalize_calls: list[PromptInvocationContext] = []

    async def prepare(self, context: PromptInvocationContext) -> PreparedInvocation:
        self.prepare_calls.append(context)
        return await super().prepare(context)

    async def finalize(
        self,
        prompt: ComposedPrompt,
        context: PromptInvocationContext,
        *,
        prepared: PreparedInvocation | None = None,
    ) -> FinalizedInvocation:
        self.finalize_calls.append(context)
        return await super().finalize(prompt, context, prepared=prepared)
