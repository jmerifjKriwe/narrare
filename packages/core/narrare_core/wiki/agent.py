"""WikiGenerationAgent — generates structured wiki summaries.

Extends NarrareAgent with two run paths:
- ``generate_entity`` → WikiEntityOutput (primary, uses NarrareAgent._agent)
- ``generate_chapter`` → WikiChapterOutput (delegates to WikiChapterGenerator)

Streaming support (RULE-13): Both paths accept ``stream: bool = False``.
When streaming, ``run_stream()`` is used and the strict model output
(WikiEntityOutput / WikiChapterOutput) is streamed directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from narrare_core.agents.base import NarrareAgent
from narrare_core.wiki.agent_chapter import WikiChapterGenerator
from narrare_core.wiki.prompt_loader import WikiPromptLoader
from narrare_core.wiki.types import WikiChapterOutput, WikiEntityOutput, WikiGenerationDeps

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import UsageLimits


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
            output_type=WikiEntityOutput,
            system_prompt=system_prompt,
        )
        self._model = model
        self._system_prompt = system_prompt
        self._chapter_generator = WikiChapterGenerator(model=model, system_prompt=system_prompt)

    # ------------------------------------------------------------------
    # Public API: generate_entity
    # ------------------------------------------------------------------

    async def generate_entity(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
        model_settings: ModelSettings | None = None,
        usage_limits: UsageLimits | None = None,
    ) -> WikiEntityOutput:
        """Generate a wiki summary for a single KB entity.

        Loads the entity_summary prompt for the deps language, substitutes
        variables, and runs the entity agent.

        Args:
            deps: Generation dependencies with entity context.
            stream: If True, use ``run_stream()`` for streaming output.
            model_settings: Settings half of the ModelRegistry.prepare()
                triple — forwarded to the pydantic-ai run.
            usage_limits: Usage limits from the prepared triple —
                forwarded to the pydantic-ai run.

        Returns:
            Structured entity wiki summary.
        """
        prompt_text = self._load_entity_prompt(deps)
        if stream:
            async with self._agent.run_stream(
                prompt_text,
                deps=deps,
                model_settings=model_settings,
                usage_limits=usage_limits,
            ) as stream_result:
                return cast("WikiEntityOutput", await stream_result.get_output())
        result = await self._agent.run(
            prompt_text,
            deps=deps,
            model_settings=model_settings,
            usage_limits=usage_limits,
        )
        return cast("WikiEntityOutput", result.output)

    # ------------------------------------------------------------------
    # Public API: generate_chapter
    # ------------------------------------------------------------------

    async def generate_chapter(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
        model_settings: ModelSettings | None = None,
        usage_limits: UsageLimits | None = None,
    ) -> WikiChapterOutput:
        """Generate a wiki summary for a single chapter.

        Loads the chapter_summary prompt for the deps language, substitutes
        variables, and delegates to WikiChapterGenerator.

        Args:
            deps: Generation dependencies with chapter context.
            stream: If True, use ``run_stream()`` for streaming output.
            model_settings: Settings half of the ModelRegistry.prepare()
                triple — forwarded to the chapter agent run.
            usage_limits: Usage limits from the prepared triple —
                forwarded to the chapter agent run.

        Returns:
            Structured chapter wiki summary.
        """
        prompt_text = self._load_chapter_prompt(deps)
        return await self._chapter_generator.generate(
            prompt_text,
            deps,
            stream=stream,
            model_settings=model_settings,
            usage_limits=usage_limits,
        )

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
