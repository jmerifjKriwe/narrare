"""WikiChapterGenerator — separate agent for chapter wiki summaries.

Extracted from WikiGenerationAgent for RULE-04 compliance.
Uses a separate internal pydantic-ai Agent because WikiChapterOutput
has a different schema than WikiEntityOutput.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic_ai import (
    Agent as PydanticAgent,
)  # narrare: allow-agent reason="WikiChapterGenerator wraps internal PydanticAgent (ADR-015)"
from pydantic_ai import RunContext

from narrare_core.wiki.types import WikiChapterOutput, WikiGenerationDeps


class WikiChapterGenerator:
    """Handles chapter wiki summary generation with a separate pydantic-ai Agent.

    Created lazily so that TestModel injection works correctly — the
    agent is only created when ``generate`` is first called.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        """Initialize the chapter generator.

        Args:
            model: LLM model instance (from ModelRegistry or TestModel).
            system_prompt: Optional override prompt passed to the chapter agent.
        """
        self._model = model
        self._system_prompt = system_prompt
        self._chapter_agent: Any = None

    async def generate(
        self,
        prompt_text: str,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
    ) -> WikiChapterOutput:
        """Generate a wiki summary for a single chapter.

        Args:
            prompt_text: The rendered prompt text with substituted variables.
            deps: Generation dependencies with chapter context.
            stream: If True, use ``run_stream()`` for streaming output.

        Returns:
            Structured chapter wiki summary.
        """
        agent = self._get_agent()
        if stream:
            async with agent.run_stream(prompt_text, deps=deps) as stream_result:
                return cast("WikiChapterOutput", await stream_result.get_output())
        result = await agent.run(  # narrare: allow-agent reason="internal PydanticAgent (ADR-015)"
            prompt_text, deps=deps
        )
        return cast("WikiChapterOutput", result.output)

    def _get_agent(self) -> Any:
        """Get or create the internal chapter agent (lazy)."""
        if self._chapter_agent is None:
            kwargs: dict[str, Any] = {
                "model": self._model,
                "deps_type": WikiGenerationDeps,
                "output_type": [self._process_output, WikiChapterOutput],
            }
            if self._system_prompt is not None:
                kwargs["system_prompt"] = self._system_prompt
            self._chapter_agent = PydanticAgent(**kwargs)
        return self._chapter_agent

    async def _process_output(
        self,
        ctx: RunContext[WikiGenerationDeps],
        narrative_summary: str = "",
        key_events: list[str] | None = None,
        entities_involved: list[dict[str, Any]] | None = None,
        themes: list[str] | None = None,
        emotional_arc: str | None = None,
    ) -> WikiChapterOutput:
        """Output Function for chapter summary generation.

        Streaming (``ctx.partial_output``) returns an empty default instance.
        """
        if ctx.partial_output:
            return WikiChapterOutput(
                narrative_summary="",
                key_events=[],
                entities_involved=[],
                themes=[],
            )
        return WikiChapterOutput(
            narrative_summary=narrative_summary,
            key_events=key_events or [],
            entities_involved=entities_involved or [],
            themes=themes or [],
            emotional_arc=emotional_arc,
        )
