"""Output + dependency types for CharacterVoiceDriftAgent (ANAL-009 / ADR-073).

Mirrors the governed ``voice_drift`` template's JSON contract: a single flat
:class:`VoiceDriftResult` object (NOT a wrapper with a list — the agent
classifies ONE character per call, ADR-073 Decision 3/5). The agent derives
the result by interpreting the precomputed longitudinal trend + jump points
+ the stored *descriptive* voice profile (all supplied as runtime content —
the agent never recomputes metrics, ADR-021/ADR-073 Decision 2).

Measurement is already done by :mod:`narrare_core.analysis.voice_drift_scoring`
(signals (i) + (iii)); the agent ONLY classifies the trend qualitatively
(ADR-021 hybrid tier — mirrors ANAL-003/008/057). The deterministic
:class:`TrendPoint` / :class:`JumpPoint` value objects are produced by the
scoring layer and flow into the agent deps unchanged.

Decision 5 scope boundary: this agent is **read-only classification only**.
There is deliberately NO ``suggested_rewrite`` / ``new_profile`` field anywhere
in this output type — drift classification is analysis, not profiling
(ANAL-008) or rewriting (WRITE-004). Adding such a field would fuse concerns
into one agent (RULE-06).

See:
    ADR-073 — Character Voice Drift (Decision 3 agent role, Decision 5 scope).
    ADR-035 — Agent output validation.
    ADR-021 — Deterministic analysis strategy (metrics deterministic, LLM
        interprets qualitatively).
    narrare_core.analysis.voice_drift_scoring — the precomputed trend + jumps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from narrare_core.analysis.voice_drift_scoring import JumpPoint, TrendPoint

# Drift classification — Literal mirrors the governed template's output
# contract verbatim (system.md "Output Format" / "Field semantics"). The
# single best-fitting label for the longitudinal pattern; no hedging.
DriftType = Literal["evolution", "context", "inconsistency"]


class ChapterMeta(BaseModel):
    """Per-chapter metadata supplied to the drift agent (runtime content).

    Carried on the agent deps so the agent can ground its per-chapter notes
    and ``suggested_attention`` in real chapter ids + titles. The chapter ids
    MUST match those in the supplied :class:`TrendPoint` / :class:`JumpPoint`
    lists (the caller — Layer 3 service — guarantees this by construction).

    Attributes:
        chapter_id: The chapter identifier (matches TrendPoint.chapter_id).
        title: The chapter title (may be empty when untitled).
        summary: Optional short chapter summary (context the agent may use to
            distinguish ``context`` drift from ``inconsistency``). ``None`` when
            no summary is available.
    """

    model_config = {"frozen": True}

    chapter_id: str
    title: str = ""
    summary: str | None = None


class ChapterNote(BaseModel):
    """A single per-chapter note in the drift result (sparse commentary).

    Attributes:
        chapter_id: The chapter the note refers to (drawn from the supplied
            trend — never invented).
        note: Short note tied to this chapter's data (a jump point, a notable
            low score, an arc beat). Never a generic filler.
    """

    chapter_id: str = ""
    note: str = ""


class VoiceDriftResult(BaseModel):
    """Structured longitudinal drift classification for one character.

    The locked output shape Frontend + Backend consume (ADR-073 Decision 3).
    A single flat object — the agent classifies one character per call.

    Attributes:
        drift_type: Exactly one of ``"evolution"`` (intentional arc-driven
            change), ``"context"`` (chapter-context-driven variation), or
            ``"inconsistency"`` (unexplained drift). The single best-fitting
            label — no hedging.
        confidence: Float ``0.0``-``1.0`` capturing how confident the
            classification is given the trend + jumps + profile.
        longitudinal_reasons: Concrete observations that justify the
            classification, each tied to a specific trend feature (a declining
            metric, a jump at a specific chapter, an oscillation). May be empty
            only when ``confidence`` is ``0.0`` (the empty-trend convention).
        per_chapter_notes: Sparse per-chapter commentary — only chapters with
            something concrete to say appear. Empty when no chapter warrants
            individual commentary.
        suggested_attention: Chapter ids (drawn from the supplied trend) most
            worth the author's review. Empty when the voice is stable.
    """

    drift_type: DriftType = "evolution"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    longitudinal_reasons: list[str] = Field(default_factory=list)
    # Mirrors CharacterVoiceCheckerEntry.flagged_lines — ``= []`` keeps pyright
    # strict happy (Field(default_factory=list) would surface as
    # list[Unknown] for a custom-element list).
    per_chapter_notes: list[ChapterNote] = []
    suggested_attention: list[str] = Field(default_factory=list)


class CharacterVoiceDriftDeps:
    """Dependencies for CharacterVoiceDriftAgent.

    A plain class (not Pydantic) — follows the established
    :class:`~narrare_core.agents.character_voice_types.CharacterVoiceDeps`,
    :class:`~narrare_core.agents.character_voice_checker_types.CharacterVoiceCheckerDeps`,
    ``CoreferenceDeps``, ``ReadabilityDeps`` pattern. The governed
    ``voice_drift`` template is the system prompt (resolved Mode 1 by the
    Layer-3 service via :class:`~narrare_core.prompts.composer.PromptComposer`
    and passed to the agent constructor, RULE-02b). The precomputed trend +
    jumps + stored descriptive profile + chapter metadata flow as category-3
    runtime content in the agent run prompt (user channel, RULE-02a); the same
    data is carried here for structured access + ADR-035 validation.

    The KB world-context variables (``kb_characters`` / ``kb_locations`` /
    ``kb_factions`` / ``kb_relationships``) and ``user_preferences`` /
    ``avoidance_patterns`` are resolved by the composer into the governed
    system prompt (the template references them); they are NOT agent runtime
    content and therefore are not duplicated on these Deps — mirroring
    :class:`CharacterVoiceCheckerDeps`.

    Attributes:
        character_name: The canonical name of the character being classified.
        descriptive_profile: The stored *descriptive* voice profile for the
            character (from
            :attr:`~narrare_core.profiles.models.CharacterVoiceProfile.speech_summary`).
            This is the profile the agent classifies against (runtime content).
            Metrics NEVER reach the LLM as raw numbers — only the descriptive
            profile + the trend subscores do (ADR-055 "metrics never reach
            generation" preserved on the drift path).
        trend: The precomputed per-chapter match trend (signal i) from
            :func:`~narrare_core.analysis.voice_drift_scoring.trend_against_profile`.
        jumps: The precomputed adjacent-chapter jump points (signal iii) from
            :func:`~narrare_core.analysis.voice_drift_scoring.detect_adjacent_jumps`.
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
        character_name: str = "",
        descriptive_profile: str = "",
        trend: list[TrendPoint] | None = None,
        jumps: list[JumpPoint] | None = None,
        chapter_meta: list[ChapterMeta] | None = None,
        project_title: str = "",
        genre: str = "",
        writing_language: str = "en",
    ) -> None:
        self.character_name = character_name
        self.descriptive_profile = descriptive_profile
        # Defensive copy (mirrors CharacterVoiceCheckerDeps.character_names) —
        # the value objects themselves are frozen Pydantic models, but the
        # list containers are copied so a caller mutating its source list does
        # not leak into the agent's deps.
        self.trend = list(trend) if trend else []
        self.jumps = list(jumps) if jumps else []
        self.chapter_meta = list(chapter_meta) if chapter_meta else []
        self.project_title = project_title
        self.genre = genre
        self.writing_language = writing_language
