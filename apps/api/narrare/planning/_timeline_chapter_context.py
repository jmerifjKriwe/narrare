"""Timeline chapter-context formatting (RULE-04 extraction).

Builds the compact chapter-summary context string the timeline analysis
prompt consumes. Extracted from ``timeline_analysis_service.py`` to keep it
under the 300-line service limit (RULE-04). Pure formatting — no I/O, no
instance state.

The returned string is runtime data (RULE-02a category 3): it populates the
governed timeline template's ``{{chapter_summaries}}`` variable AND serves as
the agent run prompt (the user channel) in ``TimelineAnalysisService``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare.chapters.models import Chapter


def format_chapter_context(chapters: Sequence[Chapter]) -> str:
    """Format a novel's chapters into a compact prompt-ready context string.

    Each chapter is rendered as ``Chapter N: <title>`` plus its summary and
    timeline position, with ``"(no summary yet)"`` / ``"(not set)"``
    fallbacks for missing values. Empty input yields an empty string.

    Args:
        chapters: The novel's chapters (callers typically pass them in
            position order from the repository).

    Returns:
        A newline-separated context block, one entry per chapter.
    """
    return "\n\n".join(
        f"Chapter {ch.position + 1}: {ch.title}\n"
        f"Summary: {ch.summary or '(no summary yet)'}\n"
        f"Timeline: {ch.timeline_position or '(not set)'}"
        for ch in chapters
    )
