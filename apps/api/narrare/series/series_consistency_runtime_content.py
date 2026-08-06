"""Series-consistency runtime-content formatting helpers (Spec 4 Task 2).

Extracted from ``series_consistency_service.py`` for RULE-04 compliance
(service < 300 lines). Owns the formatting of the Canon entries + chapter texts
that flow to the :class:`SeriesConsistencyAgent` run prompt (user channel,
RULE-02a category 3). Mirrors :mod:`narrare.analysis.author_voice_drift_runtime_content`
(the analysis-lane precedent for this extraction).

The governed ``series_consistency`` system prompt (resolved via
:mod:`narrare.series.series_consistency_prompt`) carries the task framing; the
Canon entries + chapter texts flow as runtime data here — never as prompt
instructions (RULE-02).
"""

from __future__ import annotations

from typing import Any


def format_canon_entries(entries: Any) -> list[str]:
    """Format Canon entries as the runtime content the agent + deps receive.

    One string per entry: ``[<slug>] <name> — <body>``. The slug is emitted
    verbatim so the agent can copy it into ``canon_entry_slug``; the body is
    the fact to check against (falls back to the name when absent). Accepts any
    object with ``slug`` / ``name`` / ``body`` attributes (the Core
    :class:`SeriesKBEntry` or a test double).
    """
    formatted: list[str] = []
    for entry in entries:
        slug = getattr(entry, "slug", "") or ""
        name = getattr(entry, "name", "") or ""
        body = getattr(entry, "body", None) or ""
        fact = body if body else name
        formatted.append(f"[{slug}] {name} — {fact}".rstrip(" —"))
    return formatted


def format_run_prompt(formatted_canon: list[str], chapter_texts: list[str]) -> str:
    """Compose the agent run prompt (user-channel runtime content).

    Combines the formatted Canon entries + the chapter texts under explicit
    section headers so the agent can separate "facts to check against" from
    "passages to inspect". Mirrors how analysis agents receive their passage
    and how ``BandSummaryAgent`` receives the numbered chapter summaries.
    """
    canon_block = "\n".join(f"- {line}" for line in formatted_canon)
    chapter_block = "\n\n".join(
        f"### Chapter {i}\n{text}" for i, text in enumerate(chapter_texts, start=1)
    )
    return (
        "## Series Canon Entries (facts to check against)\n\n"
        f"{canon_block}\n\n"
        "## Chapter Text (passages to inspect for contradictions)\n\n"
        f"{chapter_block}"
    )
