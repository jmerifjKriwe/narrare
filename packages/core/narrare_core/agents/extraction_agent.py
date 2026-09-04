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

from pydantic_ai import (
    ModelRetry,
    RunContext,
)
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
            output_type=ExtractionOutput,
            capabilities=capabilities,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[ExtractionDeps],
        output: ExtractionOutput,
    ) -> ExtractionOutput:
        """Validate deterministic invariants for extraction output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - entity_type required when item_type is new_entity or update_entity
        - source_text non-empty for all items
        - relationship items need relationship_type AND related_entity_name
        - conflict items need conflict_description
        - No duplicate items (same name + item_type)
        - Filter out items with empty names
        """
        # Filter out items with empty names
        valid_items = [item for item in output.results if item.name.strip()]

        for item in valid_items:
            # source_text must be non-empty for all items
            if not item.source_text.strip():
                raise ModelRetry(
                    f"Item '{item.name}' has empty source_text — "
                    "every extraction must reference source text"
                )

            # entity_type required for new/update entities
            if item.item_type in ("new_entity", "update_entity") and (
                not item.entity_type or not item.entity_type.strip()
            ):
                raise ModelRetry(
                    f"Item '{item.name}' ({item.item_type}) must have a non-empty entity_type"
                )

            # relationship items need both relationship_type and related_entity_name
            if item.item_type == "relationship":
                if not item.relationship_type or not item.relationship_type.strip():
                    raise ModelRetry(
                        f"Relationship item '{item.name}' must have a non-empty relationship_type"
                    )
                if not item.related_entity_name or not item.related_entity_name.strip():
                    raise ModelRetry(
                        f"Relationship item '{item.name}' must have a non-empty related_entity_name"
                    )

            # conflict items need conflict_description
            if item.item_type == "conflict" and (
                not item.conflict_description or not item.conflict_description.strip()
            ):
                raise ModelRetry(
                    f"Conflict item '{item.name}' must have a non-empty conflict_description"
                )

        # Check for duplicates (same name + item_type)
        seen: set[tuple[str, str]] = set()
        for item in valid_items:
            key = (item.name.strip(), item.item_type)
            if key in seen:
                raise ModelRetry(f"Duplicate extraction item: '{item.name}' ({item.item_type})")
            seen.add(key)

        return output.model_copy(update={"results": valid_items})

    async def run(
        self,
        prompt: str,
        deps: ExtractionDeps,
        **kwargs: Any,
    ) -> ExtractionOutput:
        """Execute the extraction agent and return structured output."""
        return await super().run(prompt, deps, **kwargs)
