"""Dependency + output types for SeriesConsistencyAgent (SERIES-004 / Spec 4 Task 1).

SeriesConsistencyAgent detects contradictions between a novel's chapter text
and the series **Canon KB** — the cross-novel fixed-facts layer established in
Spec 1. Unlike the per-novel ``ConsistencyAgent`` (CONS-001, which checks
*within* a novel: chapter vs. KB-entity vs. other chapters), this agent checks
*novel-vs-series-Canon*: does the chapter prose of Band N contradict anything
the series Canon records as fixed?

- ``CanonConflict``  — a single contradiction between a chapter passage and a
  Canon entry (``error`` = hard contradiction; ``warning`` = possible issue).
- ``SeriesConsistencyOutput`` — the structured agent output. An **empty**
  ``conflicts`` list means no contradictions were found.
- ``SeriesConsistencyDeps`` — runtime inputs carried for structured access
  (mirrors ``BandSummaryDeps`` / ``DialogueCoachDeps``).

``SeriesConsistencyDeps`` is a plain class (not Pydantic) — follows the
established pattern used by ``ConsistencyDeps``, ``BandSummaryDeps``,
``TimelineDeps``, ``DialogueCoachDeps``, and ``FactExtractorDeps``. The Canon
entries + chapter texts flow as runtime content (category-3 user-channel) in
the agent run prompt, exactly as coreference / readability / voice receive the
analysed passage as runtime input (ADR-055 D4 §analysis convention); the same
data is carried here for structured access by validators / tools.

See:
    SERIES-004 (Spec 4 Task 1),
    ADR-015 Phase 2.1 (Output Types),
    ADR-035 (agent output validation),
    ADR-055 D4 (analysis mode convention: runtime content as run prompt).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CanonConflict(BaseModel):
    """A single contradiction between a chapter passage and a Canon entry.

    Attributes:
        canon_entry_slug: Slug identifying the Canon entry that is contradicted
            (e.g. ``"character-elara-eye-color"``).
        canon_entry_name: Human-readable name of the Canon entry
            (e.g. ``"Elara — Eye Color"``).
        chapter_text_excerpt: The exact passage from the chapter text that
            contradicts Canon. Must be a verbatim quote, not a paraphrase.
        canon_statement: What Canon actually says (the contradicted fact).
        explanation: Why the excerpt and the Canon statement cannot both be
            true in the story world.
        severity: ``"error"`` = hard contradiction (the two statements cannot
            coexist); ``"warning"`` = possible issue that should be reviewed.
    """

    canon_entry_slug: str
    canon_entry_name: str
    chapter_text_excerpt: str
    canon_statement: str
    explanation: str
    severity: Literal["error", "warning"]


class SeriesConsistencyOutput(BaseModel):
    """Structured output of a SeriesConsistencyAgent run.

    Attributes:
        conflicts: List of canon contradictions found, ordered by severity
            (errors before warnings). An **empty list means no contradictions
            were found** — this is a valid and common result.
        summary: Overall assessment (1-2 sentences) of the band's consistency
            with the series Canon.
    """

    conflicts: list[CanonConflict] = []
    summary: str = ""


class SeriesConsistencyDeps:
    """Dependencies for SeriesConsistencyAgent.

    A plain class (not Pydantic) — follows the established pattern used by
    ``ConsistencyDeps``, ``BandSummaryDeps``, ``DialogueCoachDeps``, and
    ``FactExtractorDeps``.

    The governed ``series_consistency`` template (resolved via PromptComposer
    by the Layer-3 service) is the system prompt. The Canon entries and
    chapter texts flow as runtime content in the agent run prompt (user
    channel, RULE-02a category 3); the same data is carried here for
    structured access by validators / tools (mirrors
    ``DialogueCoachDeps.text_to_analyze`` and ``BandSummaryDeps.chapter_summaries``).

    Attributes:
        canon_entries: Formatted Canon KB entries to check the chapters against.
            Defensive copy is taken on construction.
        chapter_texts: Chapter content of the band (novel) being checked.
            Defensive copy is taken on construction.
        novel_title: Title of the novel (band) being checked.
    """

    def __init__(
        self,
        canon_entries: list[str] | None = None,
        chapter_texts: list[str] | None = None,
        novel_title: str = "",
    ) -> None:
        self.canon_entries: list[str] = list(canon_entries) if canon_entries else []
        self.chapter_texts: list[str] = list(chapter_texts) if chapter_texts else []
        self.novel_title = novel_title
