"""KB-suggested context enricher — adds KB-suggested data to invocation context.

Implements the ContextEnricher Protocol from
:mod:`narrare_core.ai_invocation.contracts`. Optionally queries a KB provider
for suggested context and injects it into ``dynamic_inputs["kb_suggested"]``
(formatted text, backward-compatible) and
``dynamic_inputs["kb_suggested_structured"]`` (structured
:class:`KBSuggestionResult`, for budget resolver + evidence) for downstream
prompt composition and budget resolution.

This enricher runs **before** the budget resolver so that the resolver can
decide whether to keep (token budget sufficient) or reject (token budget
exceeded) the KB-suggested content.

Separation of concerns (ADR-048 Q3, RULE-06):
    - :class:`KBSuggestedProvider` = data provision (returns structured
      :class:`KBSuggestionResult`).
    - :class:`KBSuggestedContextEnricher` = formatting (``_format_entities``)
      + injection into ``dynamic_inputs``.

Graceful degradation: if no provider is configured, the provider returns
an empty result (no entities), or the provider raises, enrichment is skipped
silently (debug-level log). The invocation continues without KB context rather
than injecting placeholder text.

See:
    ADR-039, ADR-038, ADR-048 Q3, INFRA-013,
    CONSTRAINTS.md RULE-03/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import structlog
from pydantic import BaseModel, ConfigDict, Field

from narrare_core.ai_invocation._enums import KBSuggestedRequirement

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import PromptInvocationContext

logger = structlog.get_logger(__name__)

#: Well-known key for KB-suggested formatted text in dynamic_inputs.
KB_SOURCE_KEY: str = "kb_suggested"

#: Well-known key for the structured KBSuggestionResult in dynamic_inputs.
KB_STRUCTURED_KEY: str = "kb_suggested_structured"


# ---------------------------------------------------------------------------
# Structured return models (ADR-048 Q3)
# ---------------------------------------------------------------------------


class KBSuggestedEntity(BaseModel):
    """A single KB entity suggested for context injection.

    Carries structured provenance so the enricher and evidence system
    can correlate which entities influenced the prompt.
    """

    model_config = ConfigDict(frozen=True)

    entity_id: str = Field(description="Stable identifier for the KB entity.")
    name: str = Field(description="Display name of the entity.")
    entity_type: str = Field(description="Entity type (character, location, faction, etc.).")
    summary: str = Field(description="Short summary/description of the entity.")
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Relevance/confidence score in [0.0, 1.0]. "
        "Derived from usage_count or semantic relevance.",
    )
    token_count: int = Field(
        ge=0,
        description="Approximate token count of the formatted entity representation. "
        "Enables per-entity budget decisions.",
    )
    provenance: str = Field(
        description="Provenance source identifier (e.g., 'kb_repository', "
        "'wiki_cache'). Used for evidence correlation.",
    )


class KBSuggestionResult(BaseModel):
    """Structured result from KBSuggestedProvider.get_suggested_context().

    Replaces the previous ``str`` return type. Carries an entity list with
    per-entity token counts and provenance, plus an aggregate token count
    for budget resolution.

    The enricher formats this into prompt text; the budget resolver uses
    per-entity token counts for precise budget decisions.
    """

    model_config = ConfigDict(frozen=True)

    entities: tuple[KBSuggestedEntity, ...] = Field(
        default=(),
        description="Suggested KB entities, ordered by relevance (descending).",
    )
    total_token_count: int = Field(
        ge=0,
        description="Sum of all entity token_counts. Pre-computed for budget resolver convenience.",
    )
    source: str = Field(
        description="Provider source identifier (e.g., 'kb_repository').",
    )
    query_metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Optional metadata about the query (e.g., total_entries_found, "
        "query_intent). Used for observability/evidence.",
    )


# ---------------------------------------------------------------------------
# Provider Protocol
# ---------------------------------------------------------------------------


class KBSuggestedProvider(Protocol):
    """Provides KB-suggested context for an AI invocation.

    Implementations query the knowledge base for relevant context
    (characters, locations, factions, plot threads, etc.) based on
    the invocation parameters.

    Returns structured data (:class:`KBSuggestionResult`); the enricher
    formats it into prompt text.
    """

    async def get_suggested_context(
        self,
        *,
        user_id: object | None = None,
        project_id: object | None = None,
        intent: str | None = None,
        mode: str | None = None,
    ) -> KBSuggestionResult:
        """Return structured KB-suggested context for the given parameters.

        Args:
            user_id: The user identifier, or None.
            project_id: The project identifier, or None.
            intent: The invocation intent value, or None.
            mode: The invocation mode, or None.

        Returns:
            KBSuggestionResult with entity list, token counts, and provenance.
            Returns an empty result (no entities) when no KB entries are found
            or the project_id is unresolvable.
        """
        ...


# ---------------------------------------------------------------------------
# Enricher
# ---------------------------------------------------------------------------


class KBSuggestedContextEnricher:
    """Adds KB-suggested context to the invocation context.

    Receives structured :class:`KBSuggestionResult` from the provider, formats
    it into prompt text via :meth:`_format_entities`, and injects into
    ``dynamic_inputs["kb_suggested"]`` (formatted text — backward compatible)
    and ``dynamic_inputs["kb_suggested_structured"]`` (the
    :class:`KBSuggestionResult` — for budget resolver + evidence).

    The formatted text is what reaches the PromptComposer via merge.
    The structured result is stored alongside for budget optimization and
    evidence correlation (ADR-048 Q3).

    Graceful degradation: when no provider is configured, the provider
    returns an empty result (no entities), or the provider raises, enrichment
    is skipped (context returned unchanged). A debug-level log is emitted for
    observability (RULE-11).

    The enricher returns a new :class:`PromptInvocationContext` via
    ``model_copy`` — the original context is never mutated (immutability
    guarantee).

    Implements:
        ContextEnricher Protocol.

    Args:
        kb_provider: A KBSuggestedProvider implementation, or ``None``
            for graceful degradation (enrichment skipped).
    """

    def __init__(self, kb_provider: KBSuggestedProvider | None = None) -> None:
        self._provider = kb_provider

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        """Enrich the context with KB-suggested data.

        Args:
            context: The current invocation context.

        Returns:
            A new PromptInvocationContext with KB-suggested data in
            ``dynamic_inputs["kb_suggested"]`` (formatted text) and
            ``dynamic_inputs["kb_suggested_structured"]`` (structured result),
            or the original context unchanged if kb_suggested is not
            applicable or the provider returns no entities.
        """
        # Check adoption policy — if not applicable, skip enrichment
        policy = context.adoption_policy
        if (
            policy is None
            or policy.kb_suggested_requirement == KBSuggestedRequirement.NOT_APPLICABLE
        ):
            logger.debug(
                "kb_suggested_enricher_skipped",
                reason="not_applicable",
                feature_id=context.feature_id,
            )
            return context

        # Skip if already populated (defensive — prevents double-enrichment)
        if KB_SOURCE_KEY in context.dynamic_inputs:
            logger.debug(
                "kb_suggested_enricher_already_populated",
                feature_id=context.feature_id,
            )
            return context

        try:
            if self._provider is not None:
                result = await self._provider.get_suggested_context(
                    user_id=context.user_id,
                    project_id=context.project_id,
                    intent=context.intent.value if context.intent else None,
                    mode=context.mode,
                )
            else:
                logger.debug(
                    "kb_suggested_enricher_noop",
                    reason="no_provider",
                    feature_id=context.feature_id,
                )
                return context

            # Provider returned no entities — skip enrichment (graceful degradation)
            if not result.entities:
                logger.debug(
                    "kb_suggested_enricher_skipped",
                    reason="empty_result",
                    feature_id=context.feature_id,
                    entity_count=0,
                )
                return context

            formatted_text = self._format_entities(result)

            logger.debug(
                "kb_suggested_enricher_success",
                feature_id=context.feature_id,
                entity_count=len(result.entities),
                total_token_count=result.total_token_count,
                formatted_length=len(formatted_text),
            )
        except Exception:
            logger.warning(
                "kb_suggested_enricher_provider_failed",
                feature_id=context.feature_id,
                exc_info=True,
            )
            return context

        return context.model_copy(
            update={
                "dynamic_inputs": {
                    **context.dynamic_inputs,
                    KB_SOURCE_KEY: formatted_text,
                    KB_STRUCTURED_KEY: result,
                },
            },
        )

    @staticmethod
    def _format_entities(result: KBSuggestionResult) -> str:
        """Format structured entities into prompt-ready text.

        This is the single str→text conversion point. The format mirrors
        the previous provider output for backward-compatible prompt content.
        """
        lines: list[str] = []
        for entity in result.entities:
            lines.append(
                f"{entity.name} ({entity.entity_type}), relevance: {entity.relevance_score:.2f}"
            )
        return "\n".join(lines)
