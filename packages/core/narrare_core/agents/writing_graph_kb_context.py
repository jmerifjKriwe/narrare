"""KB context assembly and prompt enrichment for WritingGraph steps.

Extracted from ``writing_graph_prompts.py`` for RULE-04 (modularise, never
compress — the module had reached the 400-line hard limit; the functions
were promoted from module-private to public per the extracted-helper-module
convention, cf. ``writing/_helpers.py``). One responsibility (RULE-06):
assemble a :class:`WritingContext` for a graph step (graceful-None per
RULE-11) and splice the KB variable set into a :class:`PromptContext`.

See:
    ``writing/_helpers.py`` ``kb_context_extras`` (KB variable SSOT),
    CONSTRAINTS.md RULE-04 / RULE-06 / RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import structlog

from narrare_core.writing._helpers import kb_context_extras

if TYPE_CHECKING:
    from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
    from narrare_core.prompts.context import PromptContext
    from narrare_core.writing.models import WritingContext

logger = structlog.get_logger(__name__)


async def assemble_writing_context(
    deps: WritingDeps,
    state: WritingState,
) -> WritingContext | None:
    """Try to assemble WritingContext for KB-enriched prompts.

    Used by the review_draft and write_draft steps.  Gracefully returns
    None if context assembly fails — the step proceeds without KB context
    (better than blocking).  Follows RULE-11 (no silent failures): errors
    are logged via structlog.
    """
    if deps.context_assembler is None:
        return None

    if not state.chapter_id or not state.novel_id:
        return None

    try:
        from uuid import UUID

        result = await deps.context_assembler.assemble(
            chapter_id=UUID(state.chapter_id),
            project_id=UUID(state.novel_id),
            mode="full_draft",
        )
        return cast("WritingContext", result)
    except Exception as exc:
        logger.warning(
            "review_context_assembly_failed",
            error=str(exc),
            chapter_id=state.chapter_id,
        )
        return None


def enrich_prompt_context_with_kb(
    context: PromptContext,
    writing_context: WritingContext,
) -> None:
    """Populate PromptContext.extra with KB data from WritingContext.

    Supplies the full ten-variable KB set via the ``kb_context_extras``
    SSOT (``writing/_helpers.py``); empty fields coalesce to ``""`` so
    templates with placeholders render empty instead of raising
    PromptVariableError on routes without optional-variable fallbacks.
    """
    context.extra.update(kb_context_extras(writing_context))
    if writing_context.recent_chapters:
        context.extra["recent_chapters"] = writing_context.recent_chapters
    if writing_context.user_preferences:
        context.extra["user_preferences"] = writing_context.user_preferences
    # R2-A: cross_session_context reaches the graph path the same way —
    # the apps service fetches it (writing/service.py prepare_generation_context)
    # and the assembler carries it on WritingContext; mirror the conditional
    # user_preferences pattern (empty → absent, graceful when no memory layer).
    if writing_context.cross_session_context:
        context.extra["cross_session_context"] = writing_context.cross_session_context
