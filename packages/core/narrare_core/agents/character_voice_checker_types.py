"""Output + dependency types for CharacterVoiceCheckerAgent (WRITE-010 / ADR-057).

Mirrors the governed ``voice_check`` template's JSON contract: a wrapper with a
``characters`` list, each entry carrying the qualitative fields the agent
derives by interpreting the stored *descriptive* profile together with a
deterministic metric-delta summary (the latter computed by
:mod:`narrare_core.analysis.voice_check_scoring` and supplied to the agent as
runtime context — the agent never recomputes metrics, ADR-021/ADR-057 Decision 2).

Decision 5 scope boundary: this checker is **flag+score only**. There is
deliberately NO ``suggested_rewrite`` field anywhere in this output type —
rewrite-on-flagged-line is a separate feature (WRITE-004). Adding such a field
here would fuse two concerns into one agent (RULE-06) and duplicate WRITE-004.

The agent's :attr:`~CharacterVoiceCheckerEntry.qualitative_sub_score` is the
qualitative half of the overall per-character match score. It feeds
:func:`narrare_core.analysis.voice_check_scoring.blend_scores` /
:meth:`narrare_core.analysis.voice_check_scoring.VoiceCheckScorer.score` which
combine it with the deterministic metric-delta sub-score into the blended
overall score — the blend is pure Core logic, not the agent's job.

See:
    ADR-057 — Voice-check checking-path contract (Decisions 2 and 5).
    ADR-035 — Agent output validation.
    ADR-021 — Deterministic analysis strategy (metrics are deterministic).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Qualitative match judgment — Literal mirrors the governed template's output
# contract verbatim (system.md "Output Format" / "Field semantics").
MatchJudgment = Literal["consistent", "mostly_consistent", "notable_drift", "off"]


class FlaggedLine(BaseModel):
    """A single dialogue line the agent flagged as inconsistent with the profile.

    Attributes:
        quote: A verbatim excerpt of the character's dialogue that reads as
            inconsistent with the stored profile (never a paraphrase).
        reason: Concise, profile-grounded explanation of the divergence, tied
            to a specific stored profile feature (register, vocabulary level,
            sentence profile, emotional range, cultural/regional markers, or a
            representative voice example). Never a generic "sounds off".
    """

    quote: str = ""
    reason: str = ""


class CharacterVoiceCheckerEntry(BaseModel):
    """Qualitative voice-check result for a single character (one LLM judgement).

    Attributes:
        character_name: The character's canonical name (exactly as supplied).
        match_judgment: The qualitative reading the metric-delta cannot produce:
            ``"consistent"`` (reads as the character), ``"mostly_consistent"``
            (minor divergences), ``"notable_drift"`` (several lines break with
            the profile), or ``"off"`` (the voice reads as a different character).
        qualitative_sub_score: Float ``0.0``-``100.0`` — the qualitative half of
            the overall per-character match score (100 = reads fully as the
            character; 0 = reads as someone else). The deterministic metric-delta
            supplies the other half; the blend is computed outside the agent.
        flagged_lines: The specific dialogue lines that read as inconsistent with
            the stored profile, each with a profile-grounded ``reason``. A
            character whose dialogue fully matches its profile has an empty list.

    Note:
        There is intentionally NO ``suggested_rewrite`` field. ADR-057 Decision 5
        scopes this checker to flag+score only; rewrite reuse of WRITE-004 is a
        later, separate concern.
    """

    character_name: str = ""
    match_judgment: MatchJudgment = "consistent"
    qualitative_sub_score: float = Field(default=100.0, ge=0.0, le=100.0)
    # Mirrors CharacterVoiceOutput.characters (list of a custom BaseModel) —
    # ``= []`` keeps pyright strict happy (Field(default_factory=list) would
    # surface as list[Unknown] for a custom-element list).
    flagged_lines: list[FlaggedLine] = []


class CharacterVoiceCheckerOutput(BaseModel):
    """Structured output wrapper from CharacterVoiceCheckerAgent.

    A single LLM call judges all supplied characters, so the contract is a
    wrapper with a ``characters`` list — exactly the template's JSON shape.
    """

    characters: list[CharacterVoiceCheckerEntry] = []


class CharacterVoiceCheckerDeps:
    """Dependencies for CharacterVoiceCheckerAgent.

    A plain class (not Pydantic) — follows the established
    :class:`~narrare_core.agents.character_voice_types.CharacterVoiceDeps`,
    ``CoreferenceDeps``, ``POVDeps``, ``ReadabilityDeps`` pattern. The governed
    ``voice_check`` template is the system prompt (resolved Mode 1 by the Layer-3
    service via :class:`~narrare_core.prompts.composer.PromptComposer` and passed
    to the agent constructor, RULE-02b). The attributed dialogue + stored
    descriptive profile + metric-delta summary flow as category-3 runtime content
    in the agent run prompt (user channel, RULE-02a); the same data is carried
    here for structured access.

    The KB world-context variables (``kb_characters`` / ``kb_locations`` /
    ``kb_factions`` / ``kb_relationships``) and ``user_preferences`` /
    ``avoidance_patterns`` are resolved by the composer into the governed system
    prompt (the template references them); they are NOT agent runtime content and
    therefore are not duplicated on these Deps — mirroring
    :class:`CharacterVoiceDeps`.

    Attributes:
        attributed_dialogue: Speaker-tagged chapter dialogue text (runtime
            content — the text being checked).
        descriptive_profile_summary: The stored *descriptive* voice profile(s)
            per character, rendered as a text block (from
            :attr:`~narrare_core.profiles.models.CharacterVoiceProfile.speech_summary`).
            This is the profile the agent checks against (runtime content).
        metric_delta_summary: The deterministic metric-delta per character,
            rendered from
            :func:`~narrare_core.analysis.voice_check_scoring.voice_metric_distances`
            / :func:`~narrare_core.analysis.voice_check_scoring.metric_delta_subscore`
            (runtime content). Supplied to the model; the agent interprets it,
            never recomputes it (ADR-021).
        character_names: The characters to check in this run.
        project_title: Project title (prompt context).
        genre: Project genre (prompt context).
        writing_language: Output language code (``"en"``, ``"de"``, ``"fr"``).
        chapter_title: Chapter title (prompt context).
    """

    def __init__(
        self,
        *,
        attributed_dialogue: str = "",
        descriptive_profile_summary: str = "",
        metric_delta_summary: str = "",
        character_names: list[str] | None = None,
        project_title: str = "",
        genre: str = "",
        writing_language: str = "en",
        chapter_title: str = "",
    ) -> None:
        self.attributed_dialogue = attributed_dialogue
        self.descriptive_profile_summary = descriptive_profile_summary
        self.metric_delta_summary = metric_delta_summary
        self.character_names = list(character_names) if character_names else []
        self.project_title = project_title
        self.genre = genre
        self.writing_language = writing_language
        self.chapter_title = chapter_title
