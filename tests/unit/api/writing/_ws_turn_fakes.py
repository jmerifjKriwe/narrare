"""Shared fakes for WebSocket turn service unit tests.

Kept in a separate module so both ``test_ws_turn_service`` and
``test_ws_turn_budget`` stay under the 300-line test hard limit (RULE-04).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import Mock

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.prompts.context import PromptContext

from narrare.writing.ws_turn_service import WritingTurnService
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer


class RecordingComposer:
    """Stub PromptComposer that records the context it received."""

    def __init__(self) -> None:
        self.last_context: PromptContext | None = None

    async def build(
        self,
        intent: LLMIntent,
        context: PromptContext,
        *,
        db_content: str | None = None,
        user_prompt: str = "",
    ) -> ComposedPrompt:
        self.last_context = context
        return ComposedPrompt(system="sys", user="usr")


async def fake_stream(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
    """Fake stream yielding text then a final chunk with usage."""
    yield StreamChunk(text="Hello ")
    yield StreamChunk(text="world!", is_final=True, usage=TokenUsage(10, 20, 30))


def make_config(token_profile: str | None = None) -> ResolvedModelConfig:
    """Create a test ResolvedModelConfig."""
    return ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=2000,
        token_limit_profile=token_profile,
    )


def make_pipeline() -> InvocationPipeline:
    """Create a real InvocationPipeline with no-op components.

    With no enrichers/validators, prepare/finalize always PASS and the
    context passes through unchanged.
    """
    return InvocationPipeline()


def make_service(
    *,
    token_profile: str | None = None,
) -> tuple[WritingTurnService, RecordingComposer, Mock, InvocationPipeline]:
    """Create a WritingTurnService with recording fakes.

    ADR-086 L39: the service consumes the deferred runtime composition;
    the fake chain pins a static runtime (same config the eager ctor
    seam passed — render- and outcome-inert).

    Returns:
        Tuple of (service, composer, registry_mock, pipeline).
    """
    from narrare.writing._ws_turn_support import WritingTurnRuntime

    composer = RecordingComposer()
    pipeline = make_pipeline()
    registry = Mock()
    registry.stream = Mock(side_effect=fake_stream)
    config = make_config(token_profile)
    resolver = DefaultRunLimitResolver()

    async def static_runtime() -> WritingTurnRuntime:
        return WritingTurnRuntime(config=config, context_assembler=None)

    # Cast is safe: RecordingComposer implements the build() surface used
    # by WritingTurnService (established codebase pattern for composer
    # doubles against the concrete PromptComposer class — RULE-02).
    service = WritingTurnService(
        composer=cast("PromptComposer", composer),
        invocation_pipeline=pipeline,
        registry=registry,
        runtime_factory=static_runtime,
        run_limit_resolver=resolver,
    )
    return service, composer, registry, pipeline
