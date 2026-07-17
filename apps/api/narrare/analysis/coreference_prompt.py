"""Coreference prompt resolution helper (Mode 1, ADR-054).

Extracted from ``coreference_service.py`` for RULE-04 compliance
(service < 300 lines). Owns the single responsibility of resolving the
governed ``coreference`` system prompt via :func:`compose_invocation`
Mode 1 (``LLMIntent.ANALYSE`` + ``context_mode="coreference"``).

The governed ``_bundled/analysis/{locale}/coreference/system.md``
template carries the task framing and project metadata variables. No
inline f-string feature prompt is assembled (RULE-02 / RULE-02b). The
chapter text flows as runtime data in the agent run prompt (user
channel, RULE-02a category 3) — not here. The KB-context variables
(``kb_characters`` / ``kb_locations`` / ``kb_factions`` /
``kb_relationships``) are supplied by the caller from the canonical
:class:`~narrare.kb.context_contracts.KBContextProvider` (ADR-067).

See:
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    RULE-04 — Modularise, never compress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer


async def resolve_coreference_prompt(
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    *,
    novel: object,
    chapter: object,
    language: str,
    novel_id: UUID,
    user_id: UUID,
    kb_vars: dict[str, str] | None = None,
) -> ComposedPrompt:
    """Resolve the governed coreference system prompt (Mode 1).

    Builds a :class:`PromptContext` with ``mode="coreference"`` and the
    project/chapter metadata, then composes the governed system prompt via
    :func:`compose_invocation` Mode 1 (``composer=`` + ``prompt_context=`` +
    ``intent=LLMIntent.ANALYSE``). The KB-context variables
    (``kb_characters`` / ``kb_locations`` / ``kb_factions`` /
    ``kb_relationships``) are supplied by the caller from the canonical
    :class:`~narrare.kb.context_contracts.KBContextProvider`
    (``kb_bundle.to_prompt_variables()``) so all four slots are fed from real
    KB context when it exists (ADR-067). They default to empty strings when
    no provider is wired or the KB is empty so the template's optional
    placeholders render rather than crash the variable engine (RULE-11
    graceful degradation).

    Args:
        composer: PromptComposer for the cascade (RULE-02b).
        invocation_pipeline: Optional pipeline for invocation evidence
            (Mode 1 prepare/finalize, ADR-045).
        novel: The novel object (title, genre read via getattr).
        chapter: The chapter object (title read via getattr).
        language: Writing language code.
        novel_id: The novel id (invocation context project_id).
        user_id: The requesting user id (invocation context user_id).
        kb_vars: KB-context prompt variables from the canonical provider
            (``kb_characters`` / ``kb_locations`` / ``kb_factions`` /
            ``kb_relationships``). When ``None`` (or a key is absent), the
            slot renders empty (RULE-11).

    Returns:
        The composed :class:`ComposedPrompt` (system + user channels).

    Raises:
        ConfigurationError: If Mode 1 composition produces no system prompt
            (Mode 1 invariant — should not happen; guarded per RULE-11).
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare_core.ai_invocation import compose_invocation
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext

    # Spread the provider's KB-context vars (all four keys present when the
    # caller passes the full ``to_prompt_variables()`` output). Spreading —
    # not a literal ``""`` assignment — keeps every slot fed from real KB
    # context (architectural-discipline §7) while still rendering empty when
    # the KB is empty (RULE-11).
    ctx = PromptContext(
        language=language,
        writing_language=language,
        project_title=getattr(novel, "title", ""),
        genre=getattr(novel, "genre", "") or "",
        chapter_title=getattr(chapter, "title", "") or "",
        mode="coreference",
        extra={
            **(kb_vars or {}),
        },
    )

    invocation_context = build_invocation_context(
        feature_id="analysis_coreference",
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
            "Prompt composition produced no system prompt for coreference analysis.",
            code="COMPOSITION_EMPTY",
        )
    return composed_prompt
