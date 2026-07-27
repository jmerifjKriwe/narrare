"""Author-voice prompt resolution helper (Mode 1, ADR-054).

Extracted from ``author_voice_service.py`` for RULE-04 compliance
(service < 300 lines). Owns the single responsibility of resolving the
governed ``author_voice`` system prompt via :func:`compose_invocation`
Mode 1 (``LLMIntent.VOICE`` + ``context_mode="author_voice"``).

The governed ``_bundled/analysis/{locale}/author_voice/system.md`` template
carries the task framing and project metadata variables. No inline f-string
feature prompt is assembled (RULE-02 / RULE-02b). The chapter prose +
precomputed metrics flow as runtime data in the agent run prompt (user
channel, RULE-02a category 3) — not here.

See:
    ADR-074 — Author Voice Storage Contract (the storage + boundary this
        prompt feeds).
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


async def resolve_author_voice_prompt(
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    *,
    novel: object,
    language: str,
    novel_id: UUID,
    user_id: UUID,
) -> ComposedPrompt:
    """Resolve the governed author_voice system prompt (Mode 1).

    Builds a :class:`PromptContext` with ``mode="author_voice"`` and the
    project metadata, then composes the governed system prompt via
    :func:`compose_invocation` Mode 1 (``composer=`` + ``prompt_context=`` +
    ``intent=LLMIntent.VOICE``). The KB-context variables are declared
    explicitly (empty) so the template's optional placeholders render rather
    than crash the variable engine (RULE-11 graceful degradation). Author
    voice is novel-scoped prose analysis — character relationships are not
    charakterprägend for the NARRATOR's voice (they are for character voice,
    which is why ``character_voice_prompt`` populates ``kb_relationships``).

    Args:
        composer: PromptComposer for the cascade (RULE-02b).
        invocation_pipeline: Optional pipeline for invocation evidence
            (Mode 1 prepare/finalize, ADR-045).
        novel: The novel object (title, genre read via getattr).
        language: Writing language code.
        novel_id: The novel id (invocation context project_id).
        user_id: The requesting user id (invocation context user_id).

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

    ctx = PromptContext(
        language=language,
        writing_language=language,
        project_title=getattr(novel, "title", ""),
        genre=getattr(novel, "genre", "") or "",
        mode="author_voice",
        extra={
            # Author voice profiles the NARRATOR (prose-level), not individual
            # characters — character-specific KB context is not relevant here.
            # The variables are declared explicitly (empty) so the template's
            # optional placeholders render as empty rather than crash the
            # variable engine (RULE-11 graceful degradation).
            "kb_characters": "",
            "kb_locations": "",
            "kb_factions": "",
            "kb_relationships": "",
        },
    )

    invocation_context = build_invocation_context(
        feature_id="analysis_author_voice",
        intent=LLMIntent.VOICE,
        project_id=novel_id,
        user_id=user_id,
        language=language,
    )
    invocation = await compose_invocation(
        invocation_pipeline=invocation_pipeline,
        invocation_context=invocation_context,
        composer=composer,
        prompt_context=ctx,
        intent=LLMIntent.VOICE,
    )
    composed_prompt = invocation.composed_prompt
    # Mode 1 guarantees composed_prompt is set; the guard documents the
    # invariant and satisfies the type-checker (RULE-11: no silent None).
    if composed_prompt is None:  # pragma: no cover - Mode 1 invariant
        raise ConfigurationError(
            "Prompt composition produced no system prompt for author-voice analysis.",
            code="COMPOSITION_EMPTY",
        )
    return composed_prompt
