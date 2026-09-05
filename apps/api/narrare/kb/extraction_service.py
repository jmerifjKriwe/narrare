"""Extraction Service — orchestrates ExtractionAgent for chapter → KB extraction.

Manages the full extraction flow:
1. Fetch chapter content from the chapter repository
2. Fetch existing KB entries: dedup names, typed ID roster, world context
3. Build system prompt via PromptComposer
4. Run ExtractionAgent over the chapter text
5. Return structured ExtractionOutput

Also provides ``apply_extraction()`` that delegates to
ExtractionApplyService for the apply step (KB-007).

Uses ModelRegistry + PromptComposer (RULE-01b, RULE-02).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare_core.agents.extraction_agent import ExtractionAgent, ExtractionDeps

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.schemas_extraction import ApplyExtractionItem, ApplyExtractionResponse
    from narrare.kb.service import KBService
    from narrare_core.agents.extraction_types import ExtractionOutput
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.run_limits import DefaultRunLimitResolver, ResolvedRunLimits
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
        kb_service: KBService for the apply step (optional, needed for apply).
        rel_repo: RelationshipRepository for the apply step (optional).
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
        kb_service: KBService | None = None,
        rel_repo: RelationshipRepository | None = None,
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
        self._kb_service = kb_service
        self._rel_repo = rel_repo
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

        # 2. Fetch existing KB entries once (graceful on repo failure) and
        #    derive the dedup name list, the typed ID roster, and the
        #    curated world context from the same result set. Single fetch
        #    keeps this O(1) repo reads.
        from narrare.kb._extraction_context import (
            build_extraction_prompt_context,
            fetch_existing_entries_graceful,
            format_entity_roster,
        )
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

        # 3. Compose prompt via compose_invocation (Mode 1 — composer-driven,
        #    ADR-048). Enrichment flows through the composer into the system
        #    prompt.
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.ai_invocation import compose_invocation
        from narrare_core.llm.intents import LLMIntent

        prompt_context = build_extraction_prompt_context(
            chapter_title=chapter.title or "",
            existing_entity_roster=entity_roster,
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

        # 4. Resolve run limits first (ADR-045 Decision 4) so the prepared
        #    call can carry them: usage_limits (+ max_tokens mirrored into
        #    model_settings) bound generation even on thinking models with
        #    tool_choice: required. None (legacy/test default) applies no
        #    output caps.
        resolved_limits: ResolvedRunLimits | None = None
        if self._run_limit_resolver is not None:
            resolved_limits = self._run_limit_resolver.resolve(
                config=self._config,
                budget=None,
                invocation_id=uuid4(),
            )

        # 5. Single assembly point (ModelRegistry.prepare): resolves the
        #    model with per-user credentials injected (model-routing
        #    cascade — the user's wizard-configured provider is used) AND
        #    builds the runtime model_settings (intent-aware thinking
        #    policy + ADR-045 output cap) as one coherent triple. The
        #    historical duplicate get_model call and the fragmented
        #    settings assembly are impossible by construction now.
        prepared = await self._registry.prepare(
            self._config,
            intent=LLMIntent.KB_EXTRACT,
            usage_limits=resolved_limits.usage_limits if resolved_limits else None,
            api_key=self._api_key,
            base_url=self._base_url,
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
