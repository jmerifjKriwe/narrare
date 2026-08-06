"""Series-consistency prompt resolution helper (Mode 1, ADR-054 / Spec 4 Task 2).

Extracted from ``series_consistency_service.py`` for RULE-04 compliance
(service < 300 lines). Owns the single responsibility of resolving the governed
``series_consistency`` system prompt via :func:`compose_invocation` Mode 1
(``LLMIntent.ANALYSE`` + ``context_mode="series_consistency"``).

The governed ``_bundled/analysis/{locale}/series_consistency/system.md``
template carries the canon-contradiction task framing (detect passages that
contradict the series Canon KB) + project metadata variables. No inline
f-string feature prompt is assembled (RULE-02 / RULE-02b). The Canon entries +
chapter texts flow as runtime data in the agent run prompt (user channel,
RULE-02a category 3) — not here.

Mirrors :mod:`narrare.analysis.author_voice_drift_prompt` (the analysis-lane
precedent for this extraction).

See:
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    ADR-075 — Series Foundation (Canon KB scope).
    RULE-04 — Modularise, never compress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.prompts.composer import PromptComposer


async def resolve_series_consistency_prompt(
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    *,
    novel_title: str,
    genre: str | None,
    language: str,
    novel_id: UUID,
    user_id: UUID,
) -> str:
    """Resolve the governed ``series_consistency`` system prompt (Mode 1).

    Builds a :class:`PromptContext` with ``mode="series_consistency"`` and the
    project metadata, then composes the governed system prompt via
    :func:`compose_invocation` Mode 1 (``composer=`` + ``prompt_context=`` +
    ``intent=LLMIntent.ANALYSE``). The KB-context variables are declared
    explicitly (empty) so the template's optional placeholders render rather
    than crash the variable engine (RULE-11 graceful degradation). The
    authoritative cross-novel facts are the Canon entries supplied at runtime
    as user input — not these per-novel KB context variables (mirrors
    :func:`resolve_author_voice_drift_prompt`).

    Args:
        composer: PromptComposer for the cascade (RULE-02b).
        invocation_pipeline: Optional pipeline for invocation evidence
            (Mode 1 prepare/finalize, ADR-045).
        novel_title: The band's (novel's) title (template ``project_title``).
        genre: The novel's genre (template ``genre``).
        language: Writing language code.
        novel_id: The novel id (invocation context project_id).
        user_id: The requesting user id (invocation context user_id).

    Returns:
        The composed system-prompt string.

    Raises:
        ConfigurationError: If Mode 1 composition produces no system prompt
            (Mode 1 invariant — should not happen; guarded per RULE-11).
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare_core.ai_invocation import compose_invocation
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext

    ctx = PromptContext(
        language=language,
        writing_language=language,
        project_title=novel_title,
        genre=genre or "",
        mode="series_consistency",
        extra={
            # The authoritative cross-novel facts are the Canon entries supplied
            # at runtime as user input — not these per-novel KB context
            # variables. Declared explicitly (empty) so the template's optional
            # placeholders render as empty rather than crash the variable
            # engine (mirrors resolve_author_voice_drift_prompt).
            "kb_characters": "",
            "kb_locations": "",
            "kb_factions": "",
            "kb_relationships": "",
            # NOTE: {{user_preferences}} / {{avoidance_patterns}} are NOT
            # declared here. They are PromptContext dataclass fields
            # (populated by the adaptive enricher) AND members of
            # _COMMON_OPTIONAL_VARIABLES (route_table.py), so the variable
            # engine resolves them without an extra= entry — exactly as
            # resolve_author_voice_drift_prompt does. Critically, extra=
            # OVERRIDES dataclass fields (PromptContext.as_variables), so a
            # literal "" here would suppress enricher-supplied preferences.
        },
    )

    invocation_context = build_invocation_context(
        feature_id="series_consistency",
        intent=LLMIntent.ANALYSE,
        project_id=novel_id,
        user_id=user_id,
        language=language,
    )
    invocation = await compose_invocation(
        invocation_pipeline=invocation_pipeline,
        invocation_context=invocation_context,
        composer=composer,
        prompt_context=ctx,
        intent=LLMIntent.ANALYSE,
    )
    composed_prompt = invocation.composed_prompt
    # Mode 1 guarantees composed_prompt is set; the guard documents the
    # invariant and satisfies the type-checker (RULE-11: no silent None).
    if composed_prompt is None:  # pragma: no cover - Mode 1 invariant
        raise ConfigurationError(
            "Prompt composition produced no system prompt for series-consistency analysis.",
            code="COMPOSITION_EMPTY",
        )
    return composed_prompt.system
