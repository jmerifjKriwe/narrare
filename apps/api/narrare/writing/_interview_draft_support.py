"""Interview-draft prompt/invocation-context builders + novel supply.

Pure assembly extracted from ``InterviewDraftGenerator`` static helpers
when the draft prompt gained the novel title/genre supply (#10 re-slice)
— the generator sat at the 300-line RULE-04 limit, so the builders moved
to a support module (family precedent: ``_ws_turn_support`` — the
service orchestrates; the support module assembles).

``build_prompt_context`` threads the ownership-resolved novel metadata
into the first-class ``PromptContext`` fields (``project_title`` /
``genre``) — HTTP parity with the b2faa851 generation supply and the #10
WS-turn seam — and supplies the ``new_chapter`` route-required extras
(``chapter_outline`` / ``kb_characters`` / ``kb_locations`` /
``word_target_line``) as RULE-11 empty degrades: on the real composer a
bare context RAISES ``PromptVariableError`` at message time (probe-proven;
the unit suite's stub composers masked it). This path is KB-blind — it
does not run the WS turn assembler — so the KB-derived slots stay empty.

``resolve_draft_novel_context`` fetches the title/genre the dispatch
owns: the draft flow holds no repository (transport-agnostic generator,
message-time dispatch), so the fetch follows the WS short-lived-session
precedent (``ws_session_config`` / ``WsWritingContextAssembler``) and
reuses :func:`narrare.writing._writing_support.resolve_novel_context`
(HTTP shape — the row is re-scoped by user as defense in depth; any
failure degrades to empty strings, RULE-11).

See: ADR-045, CONSTRAINTS.md RULE-02a/RULE-04/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext

logger = structlog.get_logger(__name__)

#: Feature identifier for interview-assisted draft generation. Distinct from
#: interactive turns (``writing_interactive_turn``) so adoption evidence can
#: correlate each production path independently (ADR-045 Decision 2).
#: Moved here with ``build_invocation_context`` (its only consumer).
INTERVIEW_DRAFT_FEATURE_ID: str = "writing_interview_draft"

#: ``new_chapter`` route-required extras this KB-blind path degrades to
#: empty (probe-enumerated against the real composer; optional template
#: variables render empty without supply, required ones raise — hence the
#: explicit keys). Built per call so no mutable dict is shared.
_DRAFT_EMPTY_EXTRA_KEYS: Final[tuple[str, ...]] = (
    "chapter_outline",
    "kb_characters",
    "kb_locations",
    "word_target_line",
)


def build_prompt_context(
    transcript: str,
    *,
    project_title: str = "",
    genre: str = "",
) -> PromptContext:
    """Build the PromptContext for draft generation (mode ``new_chapter``).

    The transcript becomes ``author_instructions`` — the
    runtime-input channel (RULE-02a). System/task prompts are built
    by the PromptComposer cascade, not here. The novel metadata
    feeds the first-class ``project_title`` / ``genre`` fields so the
    governed template renders ``- Project:`` / ``- Genre:`` populated;
    missing metadata renders empty (RULE-11).
    """
    from narrare_core.prompts.context import PromptContext

    return PromptContext(
        language="en",
        mode="new_chapter",
        author_instructions=(
            "Based on the following interview transcript, "
            "write a complete chapter draft:\n\n"
            f"{transcript}"
        ),
        project_title=project_title,
        genre=genre,
        extra=dict.fromkeys(_DRAFT_EMPTY_EXTRA_KEYS, ""),
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


async def resolve_draft_novel_context(
    *,
    user_id: UUID,
    project_id: UUID,
) -> tuple[str, str]:
    """Ownership-aware novel title/genre supply for the WS draft prompt.

    Session handling follows the WS-handshake precedent
    (``ws_session_config`` / ``WsWritingContextAssembler``): a
    short-lived session per fetch — a WebSocket connection has no
    request-scoped session. Ownership was already gated at the
    handshake; :func:`resolve_novel_context` re-scopes the row by user
    (defense in depth, HTTP shape) and degrades to empty strings on any
    fetch failure (RULE-11) — the draft proceeds without novel context.
    A session-acquisition failure degrades the same way (logged), so a
    DB outage never blocks drafting.
    """
    from narrare._app.database import get_async_session
    from narrare.novels.repository import NovelRepository
    from narrare.writing._writing_support import resolve_novel_context

    try:
        session_gen = get_async_session()
        session = await session_gen.__anext__()
    except Exception as exc:
        logger.warning(
            "draft_novel_session_failed",
            project_id=str(project_id),
            error=str(exc),
        )
        return "", ""
    try:
        return await resolve_novel_context(
            NovelRepository(session),
            project_id,
            str(user_id),
        )
    finally:
        await session_gen.aclose()
