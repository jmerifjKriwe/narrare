"""Shared fakes for interview draft unit tests.

Kept in a separate module so ``test_interview_draft`` and
``test_interview_draft_contract`` stay under the test hard limit
(RULE-04).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import Mock
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.context import PromptContext

from narrare.writing._interview_draft import InterviewDraftGenerator
from narrare.writing._ws_cache import InMemorySessionCache
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.writing.session_manager import SessionManager


class RecordingComposer:
    """Stub PromptComposer that records the context it received."""

    def __init__(self) -> None:
        self.last_context: PromptContext | None = None
        self.call_count: int = 0

    async def build(
        self,
        intent: LLMIntent,
        context: PromptContext,
        *,
        db_content: str | None = None,
        user_prompt: str = "",
    ) -> ComposedPrompt:
        self.last_context = context
        self.call_count += 1
        return ComposedPrompt(system="system-prompt", user="user-prompt")


async def fake_stream_hello(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
    """Yield text chunks then a final chunk."""
    yield StreamChunk(text="Once upon a time ")
    yield StreamChunk(text="there was a dog.", is_final=True, usage=TokenUsage(10, 20, 30))


def make_config() -> ResolvedModelConfig:
    """Create a test ResolvedModelConfig."""
    return ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=100,
    )


def make_generator(
    *,
    pipeline: InvocationPipeline | None = None,
) -> tuple[InterviewDraftGenerator, SessionManager, Mock, RecordingComposer]:
    """Create an InterviewDraftGenerator with wired invocation contract.

    By default wires a real (no-op) InvocationPipeline and a real
    DefaultRunLimitResolver so the full contract runs.
    """
    cache = InMemorySessionCache()
    session_manager = SessionManager(cache=cache)
    gateway = Mock()
    gateway.stream = Mock(side_effect=fake_stream_hello)
    composer = RecordingComposer()
    config = make_config()
    invocation_pipeline = pipeline if pipeline is not None else InvocationPipeline()

    generator = InterviewDraftGenerator(
        session_manager=session_manager,
        registry=gateway,
        composer=cast("PromptComposer", composer),
        config=config,
        invocation_pipeline=invocation_pipeline,  # type: ignore[call-arg]
        run_limit_resolver=DefaultRunLimitResolver(),  # type: ignore[call-arg]
    )
    return generator, session_manager, gateway, composer


def identifiers() -> tuple[UUID, UUID, UUID]:
    """Return (user_id, project_id, chapter_id) as fresh UUIDs."""
    return uuid4(), uuid4(), uuid4()
