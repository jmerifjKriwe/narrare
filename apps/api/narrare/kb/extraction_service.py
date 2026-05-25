"""Extraction Service — orchestrates ExtractionAgent for chapter → KB extraction.

Manages the full extraction flow:
1. Fetch chapter content from the chapter repository
2. Fetch existing KB entity names for dedup
3. Build system prompt via PromptComposer (with fallback)
4. Run ExtractionAgent over the chapter text
5. Return structured ExtractionOutput

Uses ModelRegistry + PromptComposer (RULE-01b, RULE-02).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.agents.extraction_agent import ExtractionAgent, ExtractionDeps

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare_core.agents.extraction_types import ExtractionOutput
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)

# Fallback system prompt when no bundled prompt is available.
_DEFAULT_SYSTEM_PROMPT = """You are a worldbuilding and narrative analysis assistant.
Analyze the provided chapter text and extract:

1. **New entities** — characters, locations, objects, factions, concepts, or systems that
   appear in the text and are NOT in the existing entities list.
2. **Entity updates** — new information about entities that already exist.
3. **Relationships** — meaningful connections between entities (ally, enemy, member_of,
   located_at, possesses, etc.).
4. **Conflicts** — contradictions or inconsistencies with the existing knowledge base.

For each extraction, provide:
- The exact source text that supports the extraction
- A confidence score (0.0-1.0)
- Entity type classification
- Proposed metadata where appropriate

Be thorough but precise. Only extract what is directly supported by the text.
"""


class ExtractionService:
    """Orchestrates ExtractionAgent for chapter content → KB extraction.

    Args:
        registry: ModelRegistry for LLM model resolution.
        config: ResolvedModelConfig for model selection.
        chapter_repo: Chapter repository for reading chapter content.
        kb_repo: KB repository for fetching existing entity names (dedup).
        composer: PromptComposer for bundled system prompts (RULE-02).
    """

    def __init__(
        self,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        chapter_repo: ChapterRepositoryProtocol,
        kb_repo: KBRepositoryProtocol,
        composer: PromptComposer,
    ) -> None:
        self._registry = registry
        self._config = config
        self._chapter_repo = chapter_repo
        self._kb_repo = kb_repo
        self._composer = composer

    async def extract_from_chapter(
        self,
        novel_id: UUID,
        chapter_id: UUID,
        user_id: UUID,
    ) -> ExtractionOutput:
        """Extract entities, facts, and relationships from a chapter.

        Args:
            novel_id: Novel identifier (scopes the chapter + KB lookup).
            chapter_id: Chapter to analyze.
            user_id: Requesting user (forwarded for ownership checks).

        Returns:
            Structured ExtractionOutput with results and analysis notes.

        Raises:
            ValueError: Chapter not found or has no content.
        """
        # 1. Get chapter content — scoped by novel_id for ownership.
        chapter = await self._chapter_repo.get_by_id(chapter_id, novel_id)
        if chapter is None:
            raise ValueError(f"Chapter {chapter_id} not found")

        chapter_content = chapter.content or ""
        if not chapter_content.strip():
            raise ValueError(f"Chapter {chapter_id} has no content")

        # 2. Get existing entity names for dedup.
        existing_names = await self._get_existing_entity_names(novel_id, user_id)

        # 3. Build system prompt via PromptComposer (fallback if no bundled prompt).
        system_prompt = await self._build_system_prompt()

        # 4. Get model from registry.
        model = await self._registry.get_model(self._config)

        # 5. Run ExtractionAgent over the chapter text.
        agent = ExtractionAgent(model=model, system_prompt=system_prompt)
        deps = ExtractionDeps(
            language="en",
            genre="",
            novel_id=str(novel_id),
            existing_entity_names=existing_names,
            chapter_title=chapter.title or "",
        )
        # narrare: allow-agent reason="ExtractionAgent analyzes chapter text"
        result = await agent.run(
            prompt=chapter_content,
            deps=deps,
        )

        logger.info(
            "kb_extraction_complete",
            chapter_id=str(chapter_id),
            items_count=len(result.results),
        )

        return result

    async def _get_existing_entity_names(
        self,
        novel_id: UUID,
        user_id: UUID,
    ) -> list[str]:
        """Fetch existing KB entry names for dedup.

        Retrieves all KB entries for the novel and extracts names.
        Gracefully degrades to empty list on failure so extraction
        can proceed without dedup.
        """
        try:
            entries, _ = await self._kb_repo.list_entries(
                novel_id=novel_id,
                entity_type=None,
                tags=None,
                page=1,
                page_size=1000,
            )
            return [entry.name for entry in entries if entry.name]
        except Exception:
            logger.warning("failed_to_fetch_existing_entities", exc_info=True)
            return []

    async def _build_system_prompt(self) -> str:
        """Build system prompt via PromptComposer, falling back to default.

        Uses PromptComposer with LLMIntent.KB_EXTRACT when a bundled
        prompt exists. Falls back to a hardcoded default prompt when
        no bundled prompt is registered yet.
        """
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext
        from narrare_core.shared.errors import PromptNotFoundError

        ctx = PromptContext(language="en", mode="extract")
        try:
            composed = await self._composer.build(LLMIntent.KB_EXTRACT, ctx)
            return composed.system
        except PromptNotFoundError:
            logger.info("no_bundled_extraction_prompt_using_default")
            return _DEFAULT_SYSTEM_PROMPT
