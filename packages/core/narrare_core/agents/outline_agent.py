"""OutlineAgent — NarrareAgent für Kapitel-Outline-Generierung.

Usage:
    model = await registry.get_model(config)
    agent = OutlineAgent(model=model)
    deps = OutlineDeps(
        genre="Fantasy",
        tone="dark",
        language="en",
    )
    result = await agent.run(
        prompt="Chapter 3: The hero enters the forbidden forest",
        deps=deps,
    )
    print(result.chapter_title)
    print(result.scenes)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.outline_types import OutlineOutput

if TYPE_CHECKING:
    from narrare_core.writing.context_assembler import WritingContextAssembler


class OutlineDeps:
    """Dependencies for OutlineAgent.

    Attributes:
        genre: Story genre (e.g. "Fantasy", "Sci-Fi").
        tone: Desired tone (e.g. "dark", "humorous", "balanced").
        language: Output language code.
        context_assembler: Optional context provider for additional context.
    """

    def __init__(
        self,
        genre: str = "",
        tone: str = "balanced",
        language: str = "en",
        context_assembler: WritingContextAssembler | None = None,
    ) -> None:
        self.genre = genre
        self.tone = tone
        self.language = language
        self.context_assembler = context_assembler


class OutlineAgent(NarrareAgent[OutlineDeps, OutlineOutput]):
    """Agent für Kapitel-Outline-Generierung.

    Generiert strukturierte Outlines mit Chapter-Titel + Scene-Liste.
    Nutzt Output Function zur Strukturierung.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=OutlineDeps,
            output_type=[self._process_outline, OutlineOutput],
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[OutlineDeps],
        output: OutlineOutput,
    ) -> OutlineOutput:
        """Validate deterministic invariants for outline output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - At least one scene
        - chapter_title must be non-empty
        - Filter empty scene strings
        """
        # chapter_title must be non-empty
        if not output.chapter_title.strip():
            raise ModelRetry("chapter_title must be non-empty — every outline needs a title")

        # Filter empty scene strings
        filtered_scenes = [s for s in output.scenes if s.strip()]

        # At least one scene
        if not filtered_scenes:
            raise ModelRetry("At least one scene is required in the outline")

        return output.model_copy(update={"scenes": filtered_scenes})

    async def _process_outline(
        self,
        ctx: RunContext[OutlineDeps],
        scenes: list[str] | None = None,
        chapter_title: str | None = None,
    ) -> OutlineOutput:
        """Output Function — strukturiert die LLM-Response in OutlineOutput.

        Bei Streaming (``ctx.partial_output``) wird nur minimal verarbeitet.
        """
        if ctx.partial_output:
            return OutlineOutput()

        return OutlineOutput(
            chapter_title=chapter_title or "",
            scenes=scenes or [],
            outline_text="\n\n".join(scenes) if scenes else "",
        )

    async def run(
        self,
        prompt: str,
        deps: OutlineDeps,
        **kwargs: Any,
    ) -> OutlineOutput:
        """Execute the outline agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return cast("OutlineOutput", result.output)
