"""Extraction Service — orchestrates ExtractionAgent for chapter → KB extraction.

Manages the full extraction flow:
1. Verify the caller owns the novel (IDOR fix S10) — BEFORE any load
2. Fetch chapter content from the chapter repository
3. Fetch existing KB entries: dedup names, typed ID roster, world context
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

from narrare.kb._extraction_position import resolve_chapter_position
from narrare.kb._novel_gate import verify_novel_owned
from narrare_core.agents.extraction_agent import ExtractionAgent, ExtractionDeps

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

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
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import PromptComposer

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
        session: Request-scoped AsyncSession for the apply step (optional;
            needed for apply — ExtractionApplyService wraps each item in a
            SAVEPOINT on this session).
        invocation_pipeline: Optional pipeline for invocation evidence.
        api_key: Optional per-user provider API key override (model-routing
            cascade) — injected into ``ModelRegistry.prepare``.
        base_url: Optional per-user provider base URL override.
        run_limit_resolver: Optional run-limit resolver (ADR-045 Decision 4).
            When wired (production DI), ``usage_limits`` and
            ``model_settings["max_tokens"]`` are enforced at the
            ``agent.run`` boundary so output generation is bounded even on
            thinking models with ``tool_choice: required``. ``None``
            (legacy/test default) applies no output caps.
        retries: Retry budget forwarded to the ExtractionAgent (tool-call
            and output validation failures). Defaults to 3 because
            pydantic-ai's default of 1 gives the model too few chances at
            schema-valid output for intermittently schema-invalid models.
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
        session: AsyncSession | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
        retries: int = 3,
    ) -> None:
        self._registry = registry
        self._config = config
        self._chapter_repo = chapter_repo
        self._kb_repo = kb_repo
        self._composer = composer
        self._novel_repo = novel_repo
        self._kb_service = kb_service
        self._rel_repo = rel_repo
        self._session = session
        self._invocation_pipeline = invocation_pipeline
        self._api_key = api_key
        self._base_url = base_url
        self._run_limit_resolver = run_limit_resolver
        self._retries = retries

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
        #    derive the dedup name list, the typed ID roster, and the
        #    curated world context from the same result set. Single fetch
        #    keeps this O(1) repo reads.
        from narrare.kb._extraction_context import (
            build_extraction_prompt_context,
            fetch_existing_entries_graceful,
            format_entity_roster,
        )
        from narrare.kb._extraction_invocation import compose_and_prepare
        from narrare.kb._world_context import format_world_context

        existing_entries = await fetch_existing_entries_graceful(self._kb_repo, novel_id, user_id)
        existing_names = [e.name for e in existing_entries if e.name]
        # Typed ID roster (`- name (type) [id=...]`) — lets the agent
        # reference existing entities via target_entity_id (KB-007 entity
        # resolution). Rendered from the COMPLETE entry list (uncapped).
        entity_roster = format_entity_roster(existing_entries)
        # Curated project world context aids entity disambiguation. Mirrors
        # the kb merge/assist/improve world-context mechanism and degrades
        # to empty when the KB is empty/unavailable (RULE-11). Avoidance data
        # is not handled here — it reaches the prompt via ``user_preferences``.
        world_context = format_world_context(existing_entries)

        # 3-5. Compose system prompt (Mode 1, ADR-048, graceful fallback) +
        # resolve ADR-045 run limits + prepare via the single assembly
        # point — the invocation scaffolding lives in the dedicated
        # module (RULE-04/RULE-06).
        system_prompt, prepared = await compose_and_prepare(
            composer=self._composer,
            invocation_pipeline=self._invocation_pipeline,
            registry=self._registry,
            config=self._config,
            api_key=self._api_key,
            base_url=self._base_url,
            run_limit_resolver=self._run_limit_resolver,
            novel_id=novel_id,
            user_id=user_id,
            prompt_context=build_extraction_prompt_context(
                chapter_title=chapter.title or "",
                existing_entity_roster=entity_roster,
                world_context=world_context,
            ),
        )

        agent = ExtractionAgent(
            model=prepared.model,
            system_prompt=system_prompt,
            retries=self._retries,
        )
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
            usage_limits=prepared.usage_limits,
            model_settings=prepared.model_settings,
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
        chapter_id: UUID | None = None,
    ) -> ApplyExtractionResponse:
        """Apply endorsed extraction items to the Knowledge Base.

        Ownership gate first (IDOR remediation S13, carried from S10):
        the caller must own ``novel_id`` BEFORE the apply service is
        constructed or any KB write happens. Without the gate a foreign
        caller could create/update entries in the victim's KB — and the
        per-item error swallowing in ``ExtractionApplyService`` would
        have logged (not surfaced) the downstream denials.

        Delegates to ExtractionApplyService for per-item handling.

        Args:
            novel_id: Novel to apply items to.
            user_id: Requesting user.
            items: Endorsed extraction items to apply.
            chapter_id: Chapter the items were extracted from, when known;
                its ordering position is resolved via the chapter
                repository for provenance stamping (ADR-085 §5). ``None``
                (old clients / old run artifacts) applies unchanged.

        Returns:
            ApplyExtractionResponse with created and updated entries.

        Raises:
            NotFoundError: Novel unknown or owned by another user.
            ValueError: If required dependencies not configured.
        """
        await verify_novel_owned(self._novel_repo, novel_id, user_id)

        if self._kb_service is None or self._rel_repo is None:
            raise ValueError(
                "KBService and RelationshipRepository must be configured for apply_extraction"
            )
        if self._session is None:
            raise ValueError("Session must be configured for apply_extraction")

        from narrare.kb.extraction_apply_service import ExtractionApplyService

        apply_service = ExtractionApplyService(
            kb_service=self._kb_service,
            rel_repo=self._rel_repo,
            kb_repo=self._kb_repo,
            session=self._session,
        )
        chapter_position = await resolve_chapter_position(self._chapter_repo, novel_id, chapter_id)
        return await apply_service.apply(
            novel_id=novel_id,
            user_id=user_id,
            items=items,
            chapter_position=chapter_position,
        )
