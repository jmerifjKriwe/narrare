"""PROMPT-003 live-test agent.

This agent accepts a pre-composed system prompt plus user message and produces
free-form text through the standard ``NarrareAgent`` boundary. Backend services
will supply the model via ``ModelRegistry`` and stream the resulting text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, ConfigDict, Field

from narrare_core.agents.base import NarrareAgent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai import RunContext
    from pydantic_ai.models import Model
    from pydantic_ai.output import OutputSpec

    from narrare_core.agents.base import StreamEvent


class PromptLiveTestDeps(BaseModel):
    """Runtime input for previewing a resolved prompt with a real model."""

    model_config = ConfigDict(frozen=True)

    composed_system: str = Field(..., description="Pre-composed system prompt")
    composed_user: str = Field(..., description="Pre-composed user message")
    language: str = Field("en", description="ISO language for the live-test run")


class PromptLiveTestResult(BaseModel):
    """Free-form text produced by the prompt live test."""

    model_config = ConfigDict(frozen=True)

    text: str


class PromptLiveTestAgent(NarrareAgent[PromptLiveTestDeps, PromptLiveTestResult]):
    """Agent boundary for optional PROMPT-003 live tests."""

    def __init__(self, *, model: Model) -> None:
        """Initialise the live-test agent with a ModelRegistry-provided model.

        Args:
            model: Pydantic-AI model instance supplied by ``ModelRegistry``.
        """
        super().__init__(
            model=model,
            deps_type=PromptLiveTestDeps,
            output_type=cast("OutputSpec[PromptLiveTestResult]", str),
            instructions=self._build_instructions,
        )

    @staticmethod
    def _build_instructions(ctx: RunContext[PromptLiveTestDeps]) -> str:
        """Inject the pre-composed system prompt into the system channel.

        Registered as a dynamic ``instructions`` callable (RULE-02a §3) so
        that each run reads ``deps.composed_system`` fresh, allowing a single
        agent instance to preview different pre-composed prompts.
        """
        return ctx.deps.composed_system

    async def run(
        self,
        prompt: str,
        deps: PromptLiveTestDeps,
        **kwargs: Any,
    ) -> PromptLiveTestResult:
        """Run the live test and wrap free-form model text in a typed result."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return PromptLiveTestResult(text=cast("str", result.output))

    async def run_stream(
        self,
        prompt: str,
        deps: PromptLiveTestDeps,
        *,
        message_history: list[Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        """Stream live-test free-form text through the standard agent events."""
        async for event in super().run_stream(
            prompt,
            deps,
            message_history=message_history,
            **kwargs,
        ):
            yield event
