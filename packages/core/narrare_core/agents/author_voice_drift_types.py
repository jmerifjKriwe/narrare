"""Dependency type for AuthorVoiceDriftAgent (ANAL-009 Phase 2B / ADR-074).

The author-voice analogue of
:class:`~narrare_core.agents.character_voice_drift_types.CharacterVoiceDriftDeps`.
The OUTPUT shape is **reused** — the agent returns the locked
:class:`~narrare_core.agents.character_voice_drift_types.VoiceDriftResult`
(the narrator trend is classified into the same drift_type / confidence /
reasons / per_chapter_notes / suggested_attention contract as a character
trend). Only the DEPENDENCY type is new: it carries the rendered
AuthorVoiceProfile descriptive group (not a per-character profile) + the
precomputed narrator trend + jumps + chapter metadata as category-3 runtime
content (RULE-02a).

Measurement is already done by
:mod:`narrare_core.analysis.author_voice_drift_scoring` (signals (i) + (iii),
with author-metric deltas MERGED into each TrendPoint); the agent ONLY
classifies the trend qualitatively (ADR-021 hybrid tier — mirrors Phase 1).

Decision 5 scope boundary (same as the character agent): this agent is
**read-only classification only**. There is deliberately no
``suggested_rewrite`` / ``new_profile`` field (the reused
:class:`VoiceDriftResult` carries none) — drift classification is analysis,
not profiling (ANAL-007) or rewriting (WRITE-004).

See:
    ADR-074 — Author Voice Storage Contract.
    ADR-073 — Character Voice Drift (the Phase 1 parallel mirrored here).
    ADR-035 — Agent output validation.
    ADR-021 — Deterministic analysis strategy (metrics deterministic, LLM
        interprets qualitatively).
    narrare_core.analysis.author_voice_drift_scoring — the precomputed trend
        + jumps (author-metric deltas merged into per_metric_deltas).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.agents.character_voice_drift_types import ChapterMeta
    from narrare_core.analysis.voice_drift_scoring import JumpPoint, TrendPoint


class AuthorVoiceDriftDeps:
    """Dependencies for AuthorVoiceDriftAgent.

    A plain class (not Pydantic) — mirrors the established
    :class:`CharacterVoiceDriftDeps`, :class:`AuthorVoiceDeps`,
    ``CoreferenceDeps``, ``ReadabilityDeps`` pattern. The governed
    ``author_voice_drift`` template is the system prompt (resolved Mode 1 by
    the Layer-3 service via
    :class:`~narrare_core.prompts.composer.PromptComposer` and passed to the
    agent constructor, RULE-02b). The precomputed narrator trend + jumps +
    the stored descriptive author-voice profile + chapter metadata flow as
    category-3 runtime content in the agent run prompt (user channel,
    RULE-02a); the same data is carried here for structured access + ADR-035
    validation.

    Differs from :class:`CharacterVoiceDriftDeps` in two binding ways:
    - **No ``character_name``** — the trend is narrator-scoped (one author
      voice across the book, not per-character).
    - ``descriptive_profile`` carries the rendered
      :class:`~narrare_core.profiles.author_voice.AuthorVoiceProfile`
      descriptive group (via
      :func:`~narrare_core.profiles.author_voice.render_author_voice_for_generation`),
      not a per-character speech summary.

    Attributes:
        descriptive_profile: The stored *descriptive* author-voice profile
            (the narrator's voice rendered into text — formality register,
            vocabulary level, sentence profile, emotional range, markers, voice
            examples, author examples). This is the profile the agent
            classifies against (runtime content). Metrics NEVER reach the LLM
            as raw numbers — only the descriptive profile + the trend subscores
            do (ADR-074 "metrics never reach generation" preserved on the
            author-drift path, mirroring ADR-055 for character voice).
        trend: The precomputed per-chapter match trend (signal i) from
            :func:`~narrare_core.analysis.author_voice_drift_scoring.trend_against_author_profile`
            — each TrendPoint's ``per_metric_deltas`` carries the MERGED voice
            + author deltas.
        jumps: The precomputed adjacent-chapter jump points (signal iii) from
            :func:`~narrare_core.analysis.author_voice_drift_scoring.detect_adjacent_author_jumps`.
        chapter_meta: Per-chapter metadata (id + title + optional summary) for
            the chapters in the trend — grounds the agent's per-chapter notes
            and ``suggested_attention`` in real chapter ids.
        project_title: Project title (prompt context).
        genre: Project genre (prompt context).
        writing_language: Output language code (``"en"``, ``"de"``, ``"fr"``).
    """

    def __init__(
        self,
        *,
        descriptive_profile: str = "",
        trend: list[TrendPoint] | None = None,
        jumps: list[JumpPoint] | None = None,
        chapter_meta: list[ChapterMeta] | None = None,
        project_title: str = "",
        genre: str = "",
        writing_language: str = "en",
    ) -> None:
        self.descriptive_profile = descriptive_profile
        # Defensive copy (mirrors CharacterVoiceDriftDeps) — the value objects
        # themselves are frozen Pydantic models, but the list containers are
        # copied so a caller mutating its source list does not leak into the
        # agent's deps.
        self.trend = list(trend) if trend else []
        self.jumps = list(jumps) if jumps else []
        self.chapter_meta = list(chapter_meta) if chapter_meta else []
        self.project_title = project_title
        self.genre = genre
        self.writing_language = writing_language
