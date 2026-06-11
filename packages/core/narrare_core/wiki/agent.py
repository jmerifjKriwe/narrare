"""WikiGenerationAgent — generates structured wiki summaries.

Extends NarrareAgent with two run paths:
- ``generate_entity`` → WikiEntityOutput (primary, uses NarrareAgent._agent)
- ``generate_chapter`` → WikiChapterOutput (delegates to WikiChapterGenerator)

Streaming support (RULE-13): Both paths accept ``stream: bool = False``.
When streaming, ``run_stream()`` is used and the output function returns
default/empty instances for partial outputs (``ctx.partial_output``).
"""

from __future__ import annotations

from typing import Any, cast

from pydantic_ai import (
    RunContext,  # noqa: TC002
)  # narrare: allow-agent reason="WikiGenerationAgent uses RunContext for pydantic_ai internals"

from narrare_core.agents.base import NarrareAgent
from narrare_core.wiki.agent_chapter import WikiChapterGenerator
from narrare_core.wiki.prompt_loader import WikiPromptLoader
from narrare_core.wiki.types import WikiChapterOutput, WikiEntityOutput, WikiGenerationDeps


class WikiGenerationAgent(NarrareAgent[WikiGenerationDeps, WikiEntityOutput]):
    """Agent for generating wiki summaries (entity + chapter).

    Injected with an LLM model. Optionally accepts a ``system_prompt``
    for overrides — when omitted, prompts are loaded from the bundled
    wiki prompt files.

    Usage:
        agent = WikiGenerationAgent(model=model)
        result = await agent.generate_entity(deps=WikiGenerationDeps(...))
        # or
        result = await agent.generate_chapter(deps=WikiGenerationDeps(...))
    """

    def __init__(
        self,
        model: Any,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize the wiki generation agent.

        Args:
            model: LLM model instance (from ModelRegistry or TestModel).
            system_prompt: Optional override prompt. When omitted, prompts
                are loaded from bundled wiki prompt files per language.
        """
        super().__init__(
            model=model,
            deps_type=WikiGenerationDeps,
            output_type=[self._process_entity_output, WikiEntityOutput],
            system_prompt=system_prompt,
        )
        self._model = model
        self._system_prompt = system_prompt
        self._chapter_generator = WikiChapterGenerator(model=model, system_prompt=system_prompt)

    # ------------------------------------------------------------------
    # Output function: entity
    # ------------------------------------------------------------------

    async def _process_entity_output(
        self,
        ctx: RunContext[WikiGenerationDeps],
        narrative_summary: str = "",
        role_in_story: str | None = None,
        key_attributes: list[str] | None = None,
        relationships: list[dict[str, Any]] | None = None,
        character_arc: str | None = None,
    ) -> WikiEntityOutput:
        """Output Function for entity summary generation.

        Streaming (``ctx.partial_output``) returns an empty default instance.
        """
        if ctx.partial_output:
            return WikiEntityOutput(narrative_summary="", key_attributes=[], relationships=[])
        return WikiEntityOutput(
            narrative_summary=narrative_summary,
            role_in_story=role_in_story,
            key_attributes=key_attributes or [],
            relationships=relationships or [],
            character_arc=character_arc,
        )

    # ------------------------------------------------------------------
    # Public API: generate_entity
    # ------------------------------------------------------------------

    async def generate_entity(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
    ) -> WikiEntityOutput:
        """Generate a wiki summary for a single KB entity.

        Loads the entity_summary prompt for the deps language, substitutes
        variables, and runs the entity agent.

        Args:
            deps: Generation dependencies with entity context.
            stream: If True, use ``run_stream()`` for streaming output.

        Returns:
            Structured entity wiki summary.
        """
        prompt_text = self._load_entity_prompt(deps)
        if stream:
            async with self._agent.run_stream(prompt_text, deps=deps) as stream_result:
                return cast("WikiEntityOutput", await stream_result.get_output())
        result = await self._agent.run(prompt_text, deps=deps)
        return cast("WikiEntityOutput", result.output)

    # ------------------------------------------------------------------
    # Public API: generate_chapter
    # ------------------------------------------------------------------

    async def generate_chapter(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
    ) -> WikiChapterOutput:
        """Generate a wiki summary for a single chapter.

        Loads the chapter_summary prompt for the deps language, substitutes
        variables, and delegates to WikiChapterGenerator.

        Args:
            deps: Generation dependencies with chapter context.
            stream: If True, use ``run_stream()`` for streaming output.

        Returns:
            Structured chapter wiki summary.
        """
        prompt_text = self._load_chapter_prompt(deps)
        return await self._chapter_generator.generate(prompt_text, deps, stream=stream)

    # ------------------------------------------------------------------
    # Prompt loading
    # ------------------------------------------------------------------

    def _load_entity_prompt(self, deps: WikiGenerationDeps) -> str:
        """Load the entity_summary prompt, process it, and substitute variables."""
        raw = WikiPromptLoader.read_bundled_prompt("wiki", deps.language, "entity_summary")
        return WikiPromptLoader.render_prompt(raw, deps)

    def _load_chapter_prompt(self, deps: WikiGenerationDeps) -> str:
        """Load the chapter_summary prompt, process it, and substitute variables."""
        raw = WikiPromptLoader.read_bundled_prompt("wiki", deps.language, "chapter_summary")
        return WikiPromptLoader.render_prompt(raw, deps)
