"""KB merge service — calls KBMergeAgent for entity deduplication.

Prompt resolution is Mode 1 (composer-driven) per ADR-054 D3/D7/D8: the
service resolves its system prompt via
``compose_invocation(composer=..., prompt_context=PromptContext(mode="merge"),
intent=LLMIntent.KB_CONSISTENCY)``
and passes the composed system prompt to the ``KBMergeAgent`` constructor.

The candidate pairs and curated world context are runtime data but, per the
``MODE_REQUIRED_VARS["kb"]["merge"]`` gate, they are supplied as prompt
variables in the system template (system channel) — matching the
worldbuilding phase2 precedent — not inlined as the run prompt. The previous
inline f-string feature prompt and the false ADR-048 Mode 2
``_MERGE_MANUAL_INJECTION`` declaration were removed. Invocation-composition
errors now propagate (RULE-11).

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb.schemas_merge import (
    MergeDecisionResponse,
    MergeRequest,
    MergeResponse,
    MergeStrategyRequest,
)
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.novels.repository import NovelRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class KBMergeService:
    """Service for KB entity merge analysis.

    Evaluates candidate duplicate pairs and recommends merge strategies
    by running the KBMergeAgent.

    The merge prompt is resolved through ``PromptComposer`` in Mode 1
    (ADR-054 D3): the governed ``_bundled/kb/en/merge/system.md`` template
    carries the task framing, project metadata, entity type, world context,
    and candidate pairs. No inline f-string feature prompt is assembled in
    the service (RULE-02 / RULE-02a).

    Args:
        novel_repo: For novel metadata (genre, language).
        model_registry: Shared LLM model registry.
        model_config: Resolved model config (provider + model ID).
        composer: PromptComposer for resolving the governed merge system
            prompt via the cascade (RULE-02b / ADR-054 D3). Required for
            ``analyze_merge_candidates``.
        kb_repo: Optional KB entry repository used to populate the
            ``world_context`` prompt variable with curated project context
            (the existing entities of the type under analysis). When unset or
            unavailable, ``world_context`` degrades to empty (RULE-11) and
            merge proceeds with candidate pairs alone.
        api_key: Optional API key override.
        base_url: Optional base URL override.
        invocation_pipeline: Optional pipeline for invocation evidence.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        kb_repo: KBRepositoryProtocol | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._registry = model_registry
        self._config = model_config
        self._composer = composer
        self._kb_repo = kb_repo
        self._api_key = api_key
        self._base_url = base_url
        self._invocation_pipeline = invocation_pipeline

    async def analyze_merge_candidates(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: MergeRequest,
    ) -> MergeResponse:
        """Analyze candidate pairs for KB entity merging.

        Args:
            novel_id: UUID of the novel.
            user_id: UUID of the requesting user.
            request: Entity type and candidate pairs.

        Returns:
            Merge analysis with decisions and overall notes.

        Raises:
            NotFoundError: If the novel does not exist.
            ConfigurationError: If no PromptComposer is configured.
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        if self._config is None:
            raise NotFoundError("Model config", identifier="no_model_config")

        if self._composer is None:
            # Defensive: the factory always wires a composer, but fail loudly
            # (RULE-11) rather than silently falling back to inline assembly.
            raise ConfigurationError(
                "PromptComposer is not configured for KB merge analysis.",
                code="NO_COMPOSER",
            )

        # Format candidate pairs as the governed template expects them
        # (runtime data supplied as a system-channel variable per the
        # MODE_REQUIRED_VARS["kb"]["merge"] gate, ADR-054 D3).
        pairs_text = "\n".join(
            f"  Pair {i + 1}: {pair}" for i, pair in enumerate(request.candidate_pairs)
        )

        language = novel.writing_language or "en"

        # Curated project world context (existing entities of the type under
        # analysis) sourced from the KB repository. Mirrors the kb assist/
        # improve world-context mechanism and degrades gracefully (RULE-11)
        # when no KB repo is wired or it is unavailable. Avoidance data is
        # not handled here — it reaches the prompt via ``user_preferences``.
        from narrare.kb._world_context import fetch_world_context

        world_context = ""
        if self._kb_repo is not None:
            world_context = await fetch_world_context(
                self._kb_repo,
                novel_id,
                entity_type=request.entity_type,
            )

        # Resolve the governed merge system prompt via PromptComposer
        # (RULE-02 / ADR-054 D3). The ``_bundled/kb/en/merge/system.md``
        # template carries the task framing, project metadata, entity type,
        # world context, and candidate pairs.
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.agents.merge_agent import KBMergeAgent, KBMergeDeps
        from narrare_core.ai_invocation import compose_invocation
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

        ctx = PromptContext(
            language=language,
            writing_language=language,
            project_title=novel.title,
            genre=novel.genre or "",
            entity_type=request.entity_type,
            mode="merge",
            extra={
                "candidate_pairs": pairs_text,
                # Curated KB context (possibly empty when the project has no
                # entities or the repo is unavailable). Declared explicitly so
                # the template's variable substitution always succeeds.
                "world_context": world_context,
            },
        )

        invocation_context = build_invocation_context(
            feature_id="kb_merge",
            intent=LLMIntent.KB_CONSISTENCY,
            project_id=novel_id,
            user_id=user_id,
        )
        invocation = await compose_invocation(
            invocation_pipeline=self._invocation_pipeline,
            invocation_context=invocation_context,
            composer=self._composer,
            prompt_context=ctx,
            intent=LLMIntent.KB_CONSISTENCY,
        )
        composed_prompt = invocation.composed_prompt
        # Mode 1 guarantees composed_prompt is set; the guard documents the
        # invariant and satisfies the type-checker (RULE-11: no silent None).
        if composed_prompt is None:  # pragma: no cover - Mode 1 invariant
            raise ConfigurationError(
                "Prompt composition produced no system prompt for KB merge.",
                code="COMPOSITION_EMPTY",
            )

        model = await self._registry.get_model(self._config)

        # Build deps
        deps = KBMergeDeps(
            entity_type=request.entity_type,
            genre=novel.genre or "",
            language=language,
        )

        # pydantic-ai binds ``system_prompt`` at agent construction, so the
        # composed system prompt is supplied to the constructor (not to
        # ``run()``). All task framing + candidate data live in the governed
        # template; the run prompt carries no feature framing (RULE-02a).
        agent = KBMergeAgent(model=model, system_prompt=composed_prompt.system)
        result = await agent.run(
            prompt=composed_prompt.user or "",
            deps=deps,
        )

        # Map core output to API response
        decisions: list[MergeDecisionResponse] = []
        for d in result.merge_decisions:
            strategy = None
            if d.merge_strategy is not None:
                strategy = MergeStrategyRequest(
                    keep_name=d.merge_strategy.keep_name,
                    merge_fields=d.merge_strategy.merge_fields,
                    preserve_aliases=d.merge_strategy.preserve_aliases,
                    merge_relationships=d.merge_strategy.merge_relationships,
                )
            decisions.append(
                MergeDecisionResponse(
                    pair_id=d.pair_id,
                    decision=d.decision,
                    confidence=d.confidence,
                    reasoning=d.reasoning,
                    merge_strategy=strategy,
                )
            )

        return MergeResponse(
            merge_decisions=decisions,
            overall_notes=result.overall_notes,
        )
