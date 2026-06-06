"""KB consistency enricher — checks KB consistency during invocation.

Runs after PreferenceContextEnricher and KBSuggestedContextEnricher,
before budget resolution. Delegates to the
:class:`~narrare_core.ai_invocation.consistency.KBConsistencyCheck` protocol
and writes structured results into ``dynamic_inputs``.

Graceful degradation: when no consistency checker is configured or no
project_id is available, records ``"not_applicable"`` status.

See:
    ADR-040, ADR-038, INFRA-013, CONSTRAINTS.md RULE-03/RULE-06/RULE-11.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.ai_invocation.consistency import (
        KBConsistencyCheck,
        KBConsistencyResult,
    )
    from narrare_core.ai_invocation.models import PromptInvocationContext

logger = structlog.get_logger(__name__)

#: Well-known key for KB consistency status in dynamic_inputs.
KB_CONSISTENCY_KEY: str = "kb_consistency"

#: Well-known key for KB consistency detail JSON in dynamic_inputs.
KB_CONSISTENCY_DETAIL_KEY: str = "kb_consistency_detail"


def _build_detail_payload(result: KBConsistencyResult) -> str:
    """Serialize consistency detail to a JSON string for dynamic_inputs.

    ``dynamic_inputs`` is ``dict[str, str]``, so structured detail is
    stored as a JSON string rather than a nested dict.
    """
    return json.dumps(
        {
            "has_all_required_types": result.has_all_required_types,
            "has_orphan_references": result.has_orphan_references,
            "has_stale_profiles": result.has_stale_profiles,
            "entity_types_checked": len(result.entity_type_checks),
            "orphan_count": len(result.orphan_references),
        },
    )


def _not_applicable_update(
    context: PromptInvocationContext,
) -> PromptInvocationContext:
    """Return context with ``kb_consistency`` set to ``"not_applicable"``."""
    return context.model_copy(
        update={
            "dynamic_inputs": {
                **context.dynamic_inputs,
                KB_CONSISTENCY_KEY: "not_applicable",
            },
        },
    )


class KBConsistencyEnricher:
    """Enricher that checks KB consistency during invocation.

    Runs after :class:`PreferenceContextEnricher` and
    :class:`KBSuggestedContextEnricher`, before budget resolution.

    Gracefully degrades when no consistency checker is configured
    (records ``"not_applicable"`` evidence).

    Implements:
        ContextEnricher Protocol.

    Args:
        consistency_check: A :class:`KBConsistencyCheck` implementation,
            or ``None`` for graceful degradation.
    """

    def __init__(
        self,
        consistency_check: KBConsistencyCheck | None = None,
    ) -> None:
        self._check = consistency_check

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        """Enrich context with KB consistency data.

        Args:
            context: The current invocation context.

        Returns:
            A new ``PromptInvocationContext`` with consistency status in
            ``dynamic_inputs["kb_consistency"]`` and optional detail in
            ``dynamic_inputs["kb_consistency_detail"]``.
        """
        if self._check is None:
            logger.debug(
                "kb_consistency_enricher_noop",
                reason="no_checker",
                feature_id=context.feature_id,
            )
            return _not_applicable_update(context)

        if context.project_id is None:
            logger.debug(
                "kb_consistency_enricher_noop",
                reason="no_project_id",
                feature_id=context.feature_id,
            )
            return _not_applicable_update(context)

        result = await self._check.check_consistency(context.project_id)

        status = "consistent" if result.is_consistent else "inconsistent"

        logger.debug(
            "kb_consistency_enricher_result",
            feature_id=context.feature_id,
            status=status,
            is_consistent=result.is_consistent,
        )

        return context.model_copy(
            update={
                "dynamic_inputs": {
                    **context.dynamic_inputs,
                    KB_CONSISTENCY_KEY: status,
                    KB_CONSISTENCY_DETAIL_KEY: _build_detail_payload(result),
                },
            },
        )
