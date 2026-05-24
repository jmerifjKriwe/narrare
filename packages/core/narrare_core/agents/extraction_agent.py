"""ExtractionAgent — Extracts entities, facts, and relationships from chapter text.

Produces structured ExtractionOutput with confidence scoring, dedup detection,
and conflict identification.

Composes with KBAgent for entity lookup when available.

Usage:
    model = await registry.get_model(config)
    agent = ExtractionAgent(model=model, kb_agent=kb_agent)
    deps = ExtractionDeps(
        language="en",
        genre="Fantasy",
        chapter_title="Chapter 5: The Crossing",
        existing_entity_names=["Anna", "The Tower"],
    )
    result = await agent.run(prompt=chapter_text, deps=deps)
    for item in result.results:
        print(f"{item.item_type}: {item.name} (confidence={item.confidence})")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals
from pydantic_ai.capabilities import ToolSearch, Toolset

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.extraction_types import ExtractionOutput

if TYPE_CHECKING:
    from narrare_core.agents.kb_agent import KBAgent


class ExtractionDeps:
    """Dependencies for ExtractionAgent.

    Attributes:
        language: Output language code (default "en").
        genre: Project genre for context.
        novel_id: Novel identifier for context.
        existing_entity_names: Names of known entities for dedup detection.
        chapter_title: Title of the chapter being analyzed.
    """

    def __init__(
        self,
        language: str = "en",
        genre: str = "",
        novel_id: str = "",
        existing_entity_names: list[str] | None = None,
        chapter_title: str = "",
    ) -> None:
        self.language = language
        self.genre = genre
        self.novel_id = novel_id
        self.existing_entity_names = existing_entity_names or []
        self.chapter_title = chapter_title


class ExtractionAgent(NarrareAgent[ExtractionDeps, ExtractionOutput]):
    """Agent for extracting entities, facts, and relationships from chapter text.

    Composes with KBAgent for entity verification when available.
    When no KBAgent is provided, relies on existing_entity_names for dedup.
    """

    def __init__(
        self,
        model: Any,
        kb_agent: KBAgent | None = None,
        system_prompt: str | None = None,
    ) -> None:
        # Build capabilities: ToolSearch + KBAgent tools when available
        capabilities: list[Any] = []
        if kb_agent is not None:
            capabilities.append(ToolSearch(strategy="keywords"))
            capabilities.append(Toolset(kb_agent.get_toolset()))

        super().__init__(
            model=model,
            deps_type=ExtractionDeps,
            output_type=[self._process_output, ExtractionOutput],
            capabilities=capabilities,
            system_prompt=system_prompt,
        )

    async def _process_output(
        self,
        ctx: RunContext[ExtractionDeps],
        results: list[dict[str, Any]] | None = None,
        analysis_notes: str = "",
    ) -> ExtractionOutput:
        """Output Function — structures the LLM response into ExtractionOutput.

        During streaming (ctx.partial_output), returns minimal result.
        """
        if ctx.partial_output:
            return ExtractionOutput()

        from narrare_core.agents.extraction_types import ExtractionItem

        items: list[ExtractionItem] = []
        for r in results or []:
            items.append(ExtractionItem.model_validate(r))

        return ExtractionOutput(
            results=items,
            analysis_notes=analysis_notes,
        )

    async def run(
        self,
        prompt: str,
        deps: ExtractionDeps,
        **kwargs: Any,
    ) -> ExtractionOutput:
        """Execute the extraction agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
