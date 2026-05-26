"""KB Improve Service — orchestrates KBImproveAgent for entry improvement.

Analyzes existing KB entries and returns structured improvement suggestions.
Builds agent deps from entry content + world context, runs KBImproveAgent,
and maps output to response schemas. Uses PromptComposer (RULE-02).
"""

from __future__ import annotations

import uuid as _uuid
from typing import TYPE_CHECKING

import structlog

from narrare_core.agents.kb_improve_agent import KBImproveAgent
from narrare_core.agents.kb_improve_types import KBImproveDeps, KBImproveOutput
from narrare_core.llm.intents import LLMIntent

from .improve_contracts import (
    ImproveSuggestionResponse,
    KBImproveAnalysisResponse,
    KBImproveApplyResponse,
)
from .template_fields import get_template_fields

if TYPE_CHECKING:
    from uuid import UUID

    # narrare: allow-direct-llm reason="TYPE_CHECKING only — return type of _get_model()"
    from pydantic_ai.models import Model

    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService
    from narrare_core.context.contracts import ProactiveContextProtocol
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class KBImproveService:
    """Orchestrates KBImproveAgent for analyzing and improving KB entries.

    Coordinates KBImproveAgent (LLM analysis), ProactiveContextService
    (world context), template registry, PromptComposer, KBRepository
    + KBService, and RelationshipRepository.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        proactive_context: ProactiveContextProtocol,
        prompt_composer: PromptComposer,
        kb_repo: KBRepository,
        kb_service: KBService,
        rel_repo: RelationshipRepository,
        kb_agent: object | None = None,
    ) -> None:
        from narrare_core.agents.kb_agent import KBAgent

        self._registry = registry
        self._config = config
        self._proactive_context = proactive_context
        self._prompt_composer = prompt_composer
        self._kb_repo = kb_repo
        self._kb_service = kb_service
        self._rel_repo = rel_repo
        self._kb_agent = kb_agent if isinstance(kb_agent, KBAgent) else None

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

        world_context = ""
        try:
            suggestions = await self._proactive_context.suggest(
                f"{entry.name} ({entry.entity_type})",
                novel_id=novel_id,
                entity_names=[entry.name],
                max_results=5,
            )
            if suggestions:
                world_context = "\n".join(
                    f"- {s.name} ({s.entry_type}): relevance {s.relevance_score:.2f}"
                    for s in suggestions
                )
        except Exception:
            logger.warning("proactive_context_unavailable", exc_info=True)

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

    async def _build_system_prompt(
        self,
        entity_type: str,
        entry_content: dict[str, object],
    ) -> str:
        """Build system prompt via PromptComposer (RULE-02)."""
        from narrare_core.prompts.context import PromptContext

        ctx = PromptContext(
            language="en",
            genre="",
            project_title="",
            mode=LLMIntent.KB_IMPROVE.value,
            extra={
                "entity_type": entity_type,
                "entry_content": str(entry_content),
            },
        )
        composed = await self._prompt_composer.build(LLMIntent.KB_IMPROVE, ctx)
        return composed.system

    async def _get_model(self) -> Model:
        """Resolve the LLM model lazily from the registry."""
        return await self._registry.get_model(self._config)

    async def analyze(
        self,
        *,
        novel_id: UUID,
        entry_id: UUID,
    ) -> KBImproveAnalysisResponse:
        """Analyze an existing KB entry and return improvement suggestions."""
        deps = await self._build_deps(novel_id=novel_id, entry_id=entry_id)
        system_prompt = await self._build_system_prompt(
            entity_type=deps.entity_type,
            entry_content=deps.entry_content or {},
        )

        model = await self._get_model()
        agent = KBImproveAgent(
            model=model,
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
            prompt=user_prompt, deps=deps
        )  # narrare: allow-agent reason="KBImproveAgent orchestrates entry improvement analysis"

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

        return KBImproveAnalysisResponse(
            suggestions=suggestions,
            overall_assessment=result.overall_assessment,
            completeness_score=result.completeness_score,
        )

    async def apply(
        self,
        *,
        novel_id: UUID,
        entry_id: UUID,
        suggestion_ids: list[int],
    ) -> KBImproveApplyResponse:
        """Apply selected improvement suggestions.

        Re-runs analysis and applies field changes + relationship
        connections. Operates directly on repositories (internal tool).
        """
        analysis = await self.analyze(novel_id=novel_id, entry_id=entry_id)
        selected = [s for s in analysis.suggestions if s.suggestion_id in suggestion_ids]

        if not selected:
            return KBImproveApplyResponse(
                success=False,
                entry_id=str(entry_id),
                applied_count=0,
                message="No valid suggestions selected.",
            )

        entry = await self._kb_repo.get_by_id(entry_id)
        if entry is None:
            from narrare_core.shared.errors import NotFoundError

            raise NotFoundError("KBEntry", identifier=str(entry_id))

        # Apply field changes (add_field, expand, reorganize)
        metadata_updates: dict[str, object] = {}
        for suggestion in selected:
            if (
                suggestion.type in ("add_field", "expand", "reorganize")
                and suggestion.proposed_content is not None
            ):
                metadata_updates[suggestion.target] = suggestion.proposed_content

        update_data: dict[str, object] = {}
        if metadata_updates:
            current_metadata = dict(entry.metadata_ or {})
            current_metadata.update(metadata_updates)
            update_data["metadata_"] = current_metadata

        if update_data:
            await self._kb_repo.update(entry, update_data)

        # Apply relationship connections (connect suggestions)
        connect_count = 0
        for suggestion in selected:
            if suggestion.type == "connect" and suggestion.related_entity_id:
                try:
                    from narrare.kb.models import KBRelationship

                    target_id = _uuid.UUID(suggestion.related_entity_id)
                    rel = KBRelationship(
                        source_id=entry_id,
                        target_id=target_id,
                        rel_type="related_to",
                        direction="directed",
                    )
                    await self._rel_repo.create(rel)
                    connect_count += 1
                except Exception:
                    logger.warning(
                        "relationship_creation_failed",
                        entry_id=str(entry_id),
                        related_id=suggestion.related_entity_id,
                        exc_info=True,
                    )

        total_applied = len(selected)
        return KBImproveApplyResponse(
            success=True,
            entry_id=str(entry_id),
            applied_count=total_applied,
            message=str(total_applied)
            + " improvement(s) applied ("
            + str(connect_count)
            + " new connection(s)).",
        )
