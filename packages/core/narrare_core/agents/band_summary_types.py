"""Dependency + output types for BandSummaryAgent (SERIES-002 / Spec 2 Task 2).

BandSummaryAgent aggregiert vor-generierte Kapitel-Zusammenfassungen (der
Output von ChapterSummaryAgent) in eine novel-level Band-Zusammenfassung mit
zwei Feldern:

- ``full_summary``  — mehrere Absätze; injiziert für Bände im recency window
  der SeriesHistoryTier (Spec 2 Task 6).
- ``short_summary`` — ein Satz; injiziert für ältere Bände außerhalb des
  recency window.

``BandSummaryDeps`` ist eine plain class (kein Pydantic-Modell) — folgt dem
etablierten Pattern von ``SummaryDeps`` / ``TimelineDeps`` /
``DialogueCoachDeps`` / ``FactExtractorDeps``. Die chapter_summaries fließen
als runtime content (category-3 user-channel) in den agent-run-prompt, exakt
wie coreference / voice / readability die analysierte Passage als runtime
input erhalten (ADR-055 D4 §analysis convention). Gleichzeitig werden sie
hier für strukturierten Zugriff durch Validatoren / Tools vorgehalten (mirror
von ``DialogueCoachDeps.text_to_analyze``).

See:
    SERIES-002 (Spec 2 Task 2),
    ADR-015 Phase 2.1 (Output Types),
    ADR-035 (agent output validation),
    ADR-055 D4 (analysis mode convention: runtime content as run prompt).
"""

from __future__ import annotations

from pydantic import BaseModel


class BandSummaryOutput(BaseModel):
    """Structured output of a BandSummaryAgent run.

    Attributes:
        full_summary: Multi-paragraph summary of the novel's complete plot
            arc — main events, character development, world-state changes.
            Injected for bands inside the series recency window.
        short_summary: Single-sentence distillation of the novel. Injected
            for older bands outside the recency window.
    """

    full_summary: str = ""
    short_summary: str = ""


class BandSummaryDeps:
    """Dependencies for BandSummaryAgent.

    A plain class (not Pydantic) — follows the established pattern used by
    ``SummaryDeps``, ``TimelineDeps``, ``DialogueCoachDeps``, and
    ``FactExtractorDeps``.

    The governed ``band_summary`` template (resolved via PromptComposer by
    the Layer-3 service) is the system prompt. The chapter summaries flow
    as runtime content in the agent run prompt (user channel, RULE-02a
    category 3); the same data is carried here for structured access by
    validators / tools (mirrors ``DialogueCoachDeps.text_to_analyze``).

    Attributes:
        novel_title: Title of the novel (band) being summarised.
        genre: Story genre (e.g. "Fantasy").
        chapter_summaries: Pre-generated per-chapter summaries to aggregate
            into the band summary. Defensive copy is taken on construction.
    """

    def __init__(
        self,
        novel_title: str = "",
        genre: str = "",
        chapter_summaries: list[str] | None = None,
    ) -> None:
        self.novel_title = novel_title
        self.genre = genre
        self.chapter_summaries: list[str] = list(chapter_summaries) if chapter_summaries else []
