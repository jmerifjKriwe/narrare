"""Shared Fake classes for analysis service unit tests.

Centralises Fake agent classes used across multiple test files
to avoid duplication and keep each test file within RULE-04 limits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from narrare_core.agents.pov_types import POVDetectionOutput
from narrare_core.agents.readability_types import ReadabilityAgentOutput
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.ai_invocation.pipeline import (
        FinalizedInvocation,
        PreparedInvocation,
    )
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext


class FakeComposer:
    """Fake PromptComposer for Mode 1 DI wiring (ADR-048).

    Returns a fixed :class:`ComposedPrompt` so the service can construct its
    agent with a feature-specific system prompt. Records every ``build`` call
    so tests can assert the intent/mode that was composed.

    Mirrors the pattern in ``_coreference_test_helpers.py``.
    """

    def __init__(self, system: str = "COMPOSED-ANALYSIS-SYSTEM") -> None:
        self._system = system
        self.build_calls: list[tuple[LLMIntent, PromptContext]] = []

    async def build(self, intent: LLMIntent, context: PromptContext) -> ComposedPrompt:
        self.build_calls.append((intent, context))
        return ComposedPrompt(system=self._system, user="")


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


class SpyInvocationPipeline(InvocationPipeline):
    """InvocationPipeline that records prepare/finalize calls for assertions.

    Subclasses the real :class:`InvocationPipeline` so it is type-compatible
    with the ``invocation_pipeline`` parameter on analysis services. All
    components default to ``None``, so ``prepare``/``finalize`` return PASS
    results and ``compose_invocation`` proceeds without error.

    Used to verify that analysis services route through ``compose_invocation``
    (ADR-048 Mode 1) with the expected ``feature_id``, rather than the
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
