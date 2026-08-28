"""Extraction Service — orchestrates ExtractionAgent for chapter → KB extraction.

Manages the full extraction flow:
1. Verify the caller owns the novel (IDOR fix S10) — BEFORE any load
2. Fetch chapter content from the chapter repository
3. Fetch existing KB entity names for dedup
4. Build system prompt via PromptComposer
5. Run ExtractionAgent over the chapter text
6. Return structured ExtractionOutput

Also provides ``apply_extraction()`` that delegates to
ExtractionApplyService for the apply step (KB-007).

Uses ModelRegistry + PromptComposer (RULE-01b, RULE-02).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb._extraction_entries import list_existing_entries_graceful
from narrare.kb._novel_gate import verify_novel_owned
from narrare_core.agents.extraction_agent import ExtractionAgent, ExtractionDeps

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.schemas_extraction import ApplyExtractionItem, ApplyExtractionResponse
    from narrare.kb.service import KBService
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.agents.extraction_types import ExtractionOutput
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.context import PromptContext

logger = structlog.get_logger(__name__)


class ExtractionService:
    """Orchestrates ExtractionAgent for chapter content → KB extraction.

    Args:
        registry: ModelRegistry for LLM model resolution.
        config: ResolvedModelConfig for model selection.
        chapter_repo: Chapter repository for reading chapter content.
        kb_repo: KB repository for fetching existing entity names (dedup).
        composer: PromptComposer for bundled system prompts (RULE-02).
        novel_repo: Novel repository — the novel ownership gate (IDOR
            fix S10); extraction verifies the caller owns the novel
            before the chapter content load.
        kb_service: KBService for the apply step (optional, needed for apply).
        rel_repo: RelationshipRepository for the apply step (optional).
        invocation_pipeline: Optional pipeline for invocation evidence.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        chapter_repo: ChapterRepositoryProtocol,
        kb_repo: KBRepositoryProtocol,
        composer: PromptComposer,
        novel_repo: NovelRepositoryProtocol,
        kb_service: KBService | None = None,
        rel_repo: RelationshipRepository | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._registry = registry
        self._config = config
        self._chapter_repo = chapter_repo
        self._kb_repo = kb_repo
        self._composer = composer
        self._novel_repo = novel_repo
        self._kb_service = kb_service
        self._rel_repo = rel_repo
        self._invocation_pipeline = invocation_pipeline

    async def extract_from_chapter(
        self,
        novel_id: UUID,
        chapter_id: UUID,
        user_id: UUID,
    ) -> ExtractionOutput:
        """Extract entities, facts, and relationships from a chapter.

        Ownership gate first (IDOR fix S10): the caller must own
        ``novel_id`` — BEFORE the chapter content load, the KB dedup
        read, prompt composition, or any LLM call. A ``novel_id`` path
        segment is addressing, not authorization.

        Args:
            novel_id: Novel identifier (scopes the chapter + KB lookup).
            chapter_id: Chapter to analyze.
            user_id: Requesting user — the novel ownership gate input.

        Returns:
            Structured ExtractionOutput with results and analysis notes.

        Raises:
            NotFoundError: Novel unknown or owned by another user.
            ValueError: Chapter not found in the novel or has no content.
        """
        await verify_novel_owned(self._novel_repo, novel_id, user_id)

        # 1. Get chapter content — chapter∈novel linkage (data integrity);
        #    the user scope was enforced by the ownership gate above.
        chapter = await self._chapter_repo.get_by_id(chapter_id, novel_id)
        if chapter is None:
            raise ValueError(f"Chapter {chapter_id} not found")

        chapter_content = chapter.content or ""
        if not chapter_content.strip():
            raise ValueError(f"Chapter {chapter_id} has no content")

        # 2. Fetch existing KB entries once (graceful on repo failure) and
        #    derive both the dedup name list and the curated world context
        #    from the same result set. Single fetch keeps this O(1) repo reads.
        from narrare.kb._world_context import format_world_context

        existing_entries = await list_existing_entries_graceful(self._kb_repo, novel_id, user_id)
        existing_names = [e.name for e in existing_entries if e.name]
        # Curated project world context aids entity disambiguation. Mirrors
        # the kb merge/assist/improve world-context mechanism and degrades
        # to empty when the KB is empty/unavailable (RULE-11). Avoidance data
        # is not handled here — it reaches the prompt via ``user_preferences``.
        world_context = format_world_context(existing_entries)

        # 3. Compose prompt via compose_invocation (Mode 1 — composer-driven,
        #    ADR-048). Enrichment flows through the composer into the system
        #    prompt.
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.ai_invocation import compose_invocation
        from narrare_core.llm.intents import LLMIntent

        prompt_context = self._build_prompt_context(
            chapter_title=chapter.title or "",
            existing_entity_names=existing_names,
            world_context=world_context,
        )
        invocation_context = build_invocation_context(
            feature_id="kb_extract",
            intent=LLMIntent.KB_EXTRACT,
            user_id=user_id,
            project_id=novel_id,
        )
        try:
            invocation_result = await compose_invocation(
                invocation_pipeline=self._invocation_pipeline,
                invocation_context=invocation_context,
                composer=self._composer,
                prompt_context=prompt_context,
                intent=LLMIntent.KB_EXTRACT,
            )
            assert invocation_result.composed_prompt is not None  # Mode 1 always composes
            system_prompt = invocation_result.composed_prompt.system
        except Exception:
            logger.warning(
                "invocation_composition_failed",
                feature_id="kb_extract",
                exc_info=True,
            )
            composed = await self._composer.build(LLMIntent.KB_EXTRACT, prompt_context)
            system_prompt = composed.system

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

    async def apply_extraction(
        self,
        novel_id: UUID,
        user_id: UUID,
        items: list[ApplyExtractionItem],
    ) -> ApplyExtractionResponse:
        """Apply endorsed extraction items to the Knowledge Base.

        Delegates to ExtractionApplyService for per-item handling.

        Args:
            novel_id: Novel to apply items to.
            user_id: Requesting user.
            items: Endorsed extraction items to apply.

        Returns:
            ApplyExtractionResponse with created and updated entries.

        Raises:
            ValueError: If required dependencies not configured.
        """
        if self._kb_service is None or self._rel_repo is None:
            raise ValueError(
                "KBService and RelationshipRepository must be configured for apply_extraction"
            )

        from narrare.kb.extraction_apply_service import ExtractionApplyService

        apply_service = ExtractionApplyService(
            kb_service=self._kb_service,
            rel_repo=self._rel_repo,
            kb_repo=self._kb_repo,
        )
        return await apply_service.apply(
            novel_id=novel_id,
            user_id=user_id,
            items=items,
        )

    def _build_prompt_context(
        self,
        *,
        chapter_title: str,
        existing_entity_names: list[str],
        world_context: str = "",
    ) -> PromptContext:
        """Build PromptContext for the extraction prompt (RULE-02).

        Prompt construction is retained here; composition happens via
        ``compose_invocation`` in the caller. The Narrare meta-prompt is
        injected automatically by NarrareMeta Capability (ADR-026).
        """
        from narrare_core.prompts.context import PromptContext

        return PromptContext(
            language="en",
            mode="extract",
            chapter_title=chapter_title,
            extra={
                "existing_entity_names": "\n".join(existing_entity_names),
                "world_context": world_context,
            },
        )
