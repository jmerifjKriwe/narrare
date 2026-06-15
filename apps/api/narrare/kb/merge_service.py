"""KB merge service — calls KBMergeAgent for entity deduplication.

Pattern: Service → Core Agent (RULE-01b). Gathers novel context and
candidate pairs, then runs the KBMergeAgent to produce merge decisions.
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
from narrare_core.ai_invocation import ManualInjectionDeclaration
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.novels.repository import NovelRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry

logger = structlog.get_logger(__name__)

# ADR-048 Mode 2 declaration: KBMergeAgent composes its prompt internally
# from KBMergeDeps (entity type, genre, language, candidate pairs).
_MERGE_MANUAL_INJECTION = ManualInjectionDeclaration(
    reason=(
        "KBMergeAgent composes its prompt internally from KBMergeDeps "
        "(entity type, genre, language) and the candidate-pairs user prompt."
    ),
    variables=("entity_type", "genre", "candidate_pairs"),
    injection_mechanism="agent_deps",
)


class KBMergeService:
    """Service for KB entity merge analysis.

    Evaluates candidate duplicate pairs and recommends merge strategies
    by running the KBMergeAgent.

    Args:
        novel_repo: For novel metadata (genre, language).
        model_registry: Shared LLM model registry.
        model_config: Resolved model config (provider + model ID).
        api_key: Optional API key override.
        base_url: Optional base URL override.
        invocation_pipeline: Optional pipeline for invocation evidence.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._registry = model_registry
        self._config = model_config
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
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        # Get model from registry — None config falls back to default
        from narrare_core.agents.merge_agent import KBMergeAgent, KBMergeDeps

        if self._config is None:
            raise NotFoundError("Model config", identifier="no_model_config")

        model = await self._registry.get_model(self._config)

        # Compose invocation (Mode 2 — agent-internal) and record evidence
        # (ADR-048). Replaces the former placeholder-evidence path.
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.ai_invocation import compose_invocation
        from narrare_core.llm.intents import LLMIntent

        invocation_context = build_invocation_context(
            feature_id="kb_merge",
            intent=LLMIntent.KB_CONSISTENCY,
            project_id=novel_id,
            user_id=user_id,
        )
        try:
            await compose_invocation(
                invocation_pipeline=self._invocation_pipeline,
                invocation_context=invocation_context,
                manual_injection=_MERGE_MANUAL_INJECTION,
            )
        except Exception:
            logger.warning(
                "invocation_composition_failed",
                feature_id="kb_merge",
                exc_info=True,
            )

        # Build deps
        deps = KBMergeDeps(
            entity_type=request.entity_type,
            genre=novel.genre or "",
            language=novel.writing_language or "en",
        )

        # Format candidate pairs for the agent prompt
        pairs_text = "\n".join(
            f"  Pair {i + 1}: {pair}" for i, pair in enumerate(request.candidate_pairs)
        )

        agent = KBMergeAgent(model=model)
        result = await agent.run(
            prompt=(
                f"Analyze merge candidates for '{novel.title}'.\n"
                f"Entity type: {request.entity_type}\n"
                f"Candidate pairs:\n{pairs_text}"
            ),
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
