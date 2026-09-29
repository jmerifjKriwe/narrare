"""Interview-draft prompt/invocation-context builders.

Pure assembly extracted from ``InterviewDraftGenerator`` static helpers
when the draft prompt gained the novel title/genre supply (#10 re-slice)
— the generator sat at the 300-line RULE-04 limit, so the builders moved
to a support module (family precedent: ``_ws_turn_support`` — the
service orchestrates; the support module assembles).

``build_prompt_context`` mirrors ``_ws_turn_support.build_prompt_context``:
an assembled :class:`~narrare_core.writing.models.WritingContext` (from
the production ``WsWritingContextAssembler`` at the dispatch seam) is
spread into the PromptContext via the ``kb_context_extras`` SSOT plus
``chapter_outline`` / ``timeline_position`` / ``recent_chapters`` and the
``new_chapter`` route-required ``word_target_line`` (label-in-value);
``project_title`` / ``genre`` feed the first-class fields — HTTP parity
with the b2faa851 generation supply. ``writing_context=None`` (assembly
failure degrade, RULE-11) yields the KB-blind render — byte-identical to
the pre-slice R3 baseline (pinned in ``test_interview_draft_kb_context``).

See: ADR-045, CONSTRAINTS.md RULE-02a/RULE-04/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext
    from narrare_core.writing.models import WritingContext

#: Feature identifier for interview-assisted draft generation. Distinct from
#: interactive turns (``writing_interactive_turn``) so adoption evidence can
#: correlate each production path independently (ADR-045 Decision 2).
INTERVIEW_DRAFT_FEATURE_ID: str = "writing_interview_draft"


def build_prompt_context(
    transcript: str,
    *,
    writing_context: WritingContext | None = None,
) -> PromptContext:
    """Build the PromptContext for draft generation (mode ``new_chapter``).

    The transcript becomes ``author_instructions`` — the
    runtime-input channel (RULE-02a). System/task prompts are built
    by the PromptComposer cascade, not here. The assembled KB context
    supplies the ``kb_context_extras`` SSOT spread, ``chapter_outline``
    / ``timeline_position`` / ``recent_chapters``, and the
    route-required ``word_target_line`` (label-in-value; the draft
    carries no word target, so it renders empty). ``None`` context →
    every KB slot empty (RULE-11 — the KB-blind R3 floor).
    """
    from narrare_core.prompts.context import PromptContext
    from narrare_core.writing._helpers import kb_context_extras, word_target_line
    from narrare_core.writing.models import WritingContext

    kb_source = writing_context if writing_context is not None else WritingContext()
    extra: dict[str, str] = kb_context_extras(kb_source)
    extra["chapter_outline"] = kb_source.chapter_outline
    extra["timeline_position"] = kb_source.timeline_position
    extra["recent_chapters"] = kb_source.recent_chapters
    extra["word_target_line"] = word_target_line(kb_source.word_target, label="Word target: ")
    return PromptContext(
        language="en",
        mode="new_chapter",
        author_instructions=(
            "Based on the following interview transcript, "
            "write a complete chapter draft:\n\n"
            f"{transcript}"
        ),
        project_title=kb_source.project_title,
        genre=kb_source.genre,
        extra=extra,
    )


def build_invocation_context(
    *,
    intent: LLMIntent,
    prompt_ctx: PromptContext,
    user_id: UUID,
    project_id: UUID,
    chapter_id: UUID,
    session_id: UUID,
    invocation_id: UUID,
) -> PromptInvocationContext:
    """Build the PromptInvocationContext with all identifiers.

    ADR-045 Decision 6: user and project IDs are mandatory in the
    invocation context. Chapter and session IDs are carried as
    dynamic inputs so enrichers and evidence can correlate them.
    """
    from narrare_core.ai_invocation.models import PromptInvocationContext

    return PromptInvocationContext(
        feature_id=INTERVIEW_DRAFT_FEATURE_ID,
        intent=intent,
        mode="new_chapter",
        invocation_id=invocation_id,
        user_id=user_id,
        project_id=project_id,
        language=prompt_ctx.language,
        streaming=True,
        dynamic_inputs={
            "chapter_id": str(chapter_id),
            "session_id": str(session_id),
        },
        prompt_context=prompt_ctx,
    )
