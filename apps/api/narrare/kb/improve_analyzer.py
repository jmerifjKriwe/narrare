"""KB Improve Analyzer — LLM-driven entry improvement analysis.

Extracted from ``improve_service.py`` for RULE-04 compliance.
Handles the agent interaction side of KB improvement: builds deps,
builds system prompt via PromptComposer, runs KBImproveAgent,
and caches results via KBImproveCache.

See:
    :class:`narrare.kb.improve_service.KBImproveService`
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare_core.agents.kb_improve_agent import KBImproveAgent
from narrare_core.agents.kb_improve_types import KBImproveDeps, KBImproveOutput
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import DefaultRunLimitResolver

from .improve_contracts import (
    ImproveSuggestionResponse,
    KBImproveAnalysisResponse,
)
from .template_fields import get_template_fields

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare.kb.improve_cache import KBImproveCache
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm._prepared_call import PreparedModelCall
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.context import PromptContext

logger = structlog.get_logger(__name__)


class KBImproveAnalyzer:
    """Orchestrates KBImproveAgent for entry improvement analysis.

    Builds agent deps from entry content + world context, runs
    KBImproveAgent, and maps output to response schemas.
    Uses PromptComposer (RULE-02).  Caches results via KBImproveCache.

    Args:
        registry: Model registry for resolving LLM models.
        config: Resolved model configuration.
        kb_context_provider: Single source for curated world context
            (ADR-067). Renders existing entries of the entity type as
            ``- name (type): brief`` and degrades to empty (RULE-11).
        prompt_composer: PromptComposer for building system prompts.
        kb_repo: KB entry repository.
        rel_repo: Relationship repository.
        improve_cache: Optional in-memory cache for 10min TTL (ADR-080).
        kb_agent: Optional KBAgent for cross-agent tool access.
        api_key: Optional per-user provider API key override (model-routing
            cascade) — injected into ``ModelRegistry.prepare``.
        base_url: Optional per-user provider base URL override.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        kb_context_provider: KBContextProviderProtocol,
        prompt_composer: PromptComposer,
        kb_repo: KBRepository,
        rel_repo: RelationshipRepository,
        improve_cache: KBImproveCache | None = None,
        kb_agent: object | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        from narrare_core.agents.kb_agent import KBAgent

        self._registry = registry
        self._config = config
        self._kb_context_provider = kb_context_provider
        self._prompt_composer = prompt_composer
        self._kb_repo = kb_repo
        self._rel_repo = rel_repo
        self._improve_cache = improve_cache
        self._kb_agent = kb_agent if isinstance(kb_agent, KBAgent) else None
        self._invocation_pipeline = invocation_pipeline
        self._api_key = api_key
        self._base_url = base_url
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    async def _build_deps(
        self,
        novel_id: UUID,
        entry_id: UUID,
    ) -> KBImproveDeps:
        """Build KBImproveDeps with entry content + world context."""
        entry = await self._kb_repo.get_by_id(entry_id)
        if entry is None:
            from narrare_core.shared.errors import NotFoundError

            raise NotFoundError("KBEntry", identifier=str(entry_id))

        template_fields = get_template_fields(entry.entity_type)
        template_structure = {f.field_key: f.label for f in template_fields}

        entry_content: dict[str, object] = {
            "name": entry.name,
            "entity_type": entry.entity_type,
            "metadata": dict(entry.metadata_ or {}),
            "body": (entry.body[:5000] if entry.body else ""),
            "tags": list(entry.tags) if entry.tags else [],
        }

        relationships = await self._rel_repo.list_for_entry(entry_id)
        existing_relationships = [
            {
                "id": str(r.id),
                "source_id": str(r.source_id),
                "target_id": str(r.target_id),
                "rel_type": r.rel_type,
            }
            for r in relationships
        ]

        # Single source for KB world context (ADR-067): existing entries of
        # the entry's entity type, rendered as ``- name (type): brief``. The
        # provider owns RULE-11 degradation (empty string on missing/empty KB).
        world_context = await self._kb_context_provider.fetch_world_context(
            novel_id,
            entity_type=entry.entity_type,
        )

        adjacency_map: dict[str, set[str]] | None = None
        try:
            adj = await self._rel_repo.get_adjacency_map(
                novel_id=novel_id,
                entity_ids={entry_id},
            )
            adjacency_map = adj
        except Exception:
            logger.warning("adjacency_map_unavailable", exc_info=True)

        return KBImproveDeps(
            language="en",
            entity_type=entry.entity_type,
            template_structure=template_structure,
            entry_content=entry_content,
            existing_relationships=existing_relationships,
            world_context=world_context or None,
            adjacency_map=adjacency_map,
        )

    def _build_prompt_context(
        self,
        entity_type: str,
        entry_content: dict[str, object],
    ) -> PromptContext:
        """Build PromptContext for the improve prompt (RULE-02).

        Prompt construction is retained here; composition happens via
        ``compose_invocation`` in ``analyze``.
        """
        from narrare_core.prompts.context import PromptContext

        return PromptContext(
            language="en",
            genre="",
            project_title="",
            mode=LLMIntent.KB_IMPROVE.value,
            extra={
                "entity_type": entity_type,
                "entry_content": str(entry_content),
            },
        )

    async def _prepare(self) -> PreparedModelCall:
        """Resolve the coherent call triple lazily from the registry.

        Single assembly point (Task 6c — Task 4/5 pattern): model +
        intent-aware runtime settings + usage limits as one result.
        Per-user credentials are injected so the user's
        wizard-configured provider is used (model-routing cascade), not
        the operator env.
        """
        resolved = self._run_limit_resolver.resolve(
            config=self._config, budget=None, invocation_id=uuid4()
        )
        return await self._registry.prepare(
            self._config,
            intent=LLMIntent.KB_IMPROVE,
            usage_limits=resolved.usage_limits,
            api_key=self._api_key,
            base_url=self._base_url,
        )

    async def has_cached_analysis(self, entry_id: UUID) -> bool:
        """Check whether a cached analysis exists for the given entry.

        Returns ``False`` when no cache backend is configured or when
        the key does not exist.
        """
        if not self._improve_cache:
            return False
        data = await self._improve_cache.get(str(entry_id))
        return data is not None

    async def get_cached_analysis(
        self,
        entry_id: UUID,
    ) -> KBImproveAnalysisResponse | None:
        """Return the cached analysis for an entry, or ``None``."""
        if not self._improve_cache:
            return None
        data = await self._improve_cache.get(str(entry_id))
        if data is None:
            return None
        return KBImproveAnalysisResponse.model_validate_json(data)

    async def invalidate_cache(self, entry_id: UUID) -> None:
        """Delete the cached analysis for an entry (if any)."""
        if self._improve_cache:
            await self._improve_cache.delete(str(entry_id))

    async def analyze(
        self,
        *,
        novel_id: UUID,
        entry_id: UUID,
    ) -> KBImproveAnalysisResponse:
        """Analyze an existing KB entry and return improvement suggestions.

        Checks the cache first (10min TTL).  On a cache miss, runs the
        KBImproveAgent and stores the result for subsequent calls.
        """
        entry_id_str = str(entry_id)

        # Check cache first
        if self._improve_cache:
            cached = await self._improve_cache.get(entry_id_str)
            if cached is not None:
                return KBImproveAnalysisResponse.model_validate_json(cached)

        deps = await self._build_deps(novel_id=novel_id, entry_id=entry_id)
        prompt_context = self._build_prompt_context(
            entity_type=deps.entity_type,
            entry_content=deps.entry_content or {},
        )

        # Compose prompt via compose_invocation (Mode 1 — composer-driven,
        # ADR-048). Enrichment flows through the composer into the system prompt.
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.ai_invocation import compose_invocation

        invocation_context = build_invocation_context(
            feature_id="kb_improve",
            intent=LLMIntent.KB_IMPROVE,
            project_id=novel_id,
        )
        try:
            invocation_result = await compose_invocation(
                invocation_pipeline=self._invocation_pipeline,
                invocation_context=invocation_context,
                composer=self._prompt_composer,
                prompt_context=prompt_context,
                intent=LLMIntent.KB_IMPROVE,
            )
            assert invocation_result.composed_prompt is not None  # Mode 1 always composes
            system_prompt = invocation_result.composed_prompt.system
        except Exception:
            logger.warning(
                "invocation_composition_failed",
                feature_id="kb_improve",
                exc_info=True,
            )
            composed = await self._prompt_composer.build(LLMIntent.KB_IMPROVE, prompt_context)
            system_prompt = composed.system

        prepared = await self._prepare()
        agent = KBImproveAgent(
            model=prepared.model,
            kb_agent=self._kb_agent,
            system_prompt=system_prompt,
        )

        entry_name = (deps.entry_content or {}).get("name", "unknown")
        user_prompt = (
            "Analyze the " + str(deps.entity_type) + " entry "
            "'" + str(entry_name) + "' "
            "and identify improvement opportunities."
        )
        result: KBImproveOutput = await agent.run(
            prompt=user_prompt,
            deps=deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )

        suggestions = [
            ImproveSuggestionResponse(
                type=s.type.value,
                target=s.target,
                description=s.description,
                proposed_content=s.proposed_content,
                related_entity_id=s.related_entity_id,
                related_entity_name=s.related_entity_name,
                confidence=s.confidence,
                reasoning=s.reasoning,
                suggestion_id=idx,
            )
            for idx, s in enumerate(result.suggestions)
        ]

        response = KBImproveAnalysisResponse(
            suggestions=suggestions,
            overall_assessment=result.overall_assessment,
            completeness_score=result.completeness_score,
        )

        # Store in cache for subsequent calls (10min TTL)
        if self._improve_cache:
            await self._improve_cache.set(entry_id_str, response.model_dump_json())

        return response
