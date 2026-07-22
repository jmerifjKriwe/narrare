"""Output + dependency types for DialogueCoachAgent (ASSIST-004 / ADR-069).

Mirrors the governed ``ai_assist/en/dialogue_coach/system.md`` template's
JSON contract: a wrapper with an ``issues`` list + ``adaptive_summary``
field, each issue carrying the diagnosis, severity, speaker attribution,
and (in improve mode) one or more alternatives.

ADR-055/057 boundary: ``DialogueCoachDeps`` carries the descriptive
``voice_profiles_text`` (when populated by the service) but NEVER
``voice_metrics``. The numeric metrics are checking-path only.

See:
    ADR-069 Decision 6 (voice boundary), Decision 9 (before/after blocks),
    ADR-055/057 (voice_metrics stay checking-path only),
    ADR-035 (agent output validation).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Enumerations from the governed template's output contract.
DialogueIssueType = Literal[
    "voice_mismatch",
    "subtext_absent",
    "exposition_overload",
    "tag_overuse",
    "redundancy",
    "unnatural_cadence",
    "inconsistency",
]

DialogueSeverity = Literal["low", "medium", "high"]


class DialogueAlternative(BaseModel):
    """One proposed rewrite for a DialogueIssue (improve mode only).

    Per ADR-069 Decision 9, the rewrite is a full-string replacement
    (not a char-level diff). The frontend renders original -> rewrite as
    stacked before/after blocks and applies by string find-and-replace.

    Attributes:
        rewrite: The full replacement string. Non-empty.
        explanation: Why this rewrite addresses the issue.
    """

    model_config = ConfigDict(frozen=True)

    rewrite: str = Field(min_length=1)
    explanation: str = ""


class DialogueIssue(BaseModel):
    """One diagnosed dialogue issue (analyze or improve mode).

    Attributes:
        issue_type: One of the seven enumerated types.
        speaker: Canonical name from the {{characters}} roster. Empty
            string when the speaker cannot be determined.
        original_quote: Verbatim substring of the supplied dialogue.
            Required for every issue (Quality Rule).
        diagnosis: 1-3 sentences explaining what is wrong.
        severity: low / medium / high.
        alternatives: Optional list (present iff mode=improve). When
            absent, the issue is analyze-mode only.
    """

    model_config = ConfigDict(frozen=True)

    issue_type: DialogueIssueType
    speaker: str = ""
    original_quote: str = Field(min_length=1)
    diagnosis: str = Field(min_length=1)
    severity: DialogueSeverity = "low"
    alternatives: list[DialogueAlternative] | None = None


class DialogueCoachOutput(BaseModel):
    """Structured output wrapper from DialogueCoachAgent.

    A single LLM call analyses the supplied passage and returns all
    issues at once -- the contract is a wrapper with an ``issues`` list
    and an ``adaptive_summary`` (transparency note for the dashboard).

    Attributes:
        issues: Diagnosed dialogue issues. May be empty (the passage had
            no issues).
        adaptive_summary: 1-2 sentences noting how the active preferences
            / voice profiles shaped this analysis. Empty string when no
            signals were active.
    """

    model_config = ConfigDict(frozen=True)

    issues: list[DialogueIssue] = []
    adaptive_summary: str = ""


class DialogueCoachDeps:
    """Dependencies for DialogueCoachAgent.

    A plain class (not Pydantic) -- follows the established
    ``CharacterVoiceDeps`` / ``CoreferenceDeps`` pattern. The governed
    ``dialogue_coach`` template is the system prompt (resolved Mode 1 by
    the Layer-3 service and passed to the agent constructor, RULE-02b).
    The selection text + mode + canonical speaker roster flow as runtime
    content in the agent run prompt (user channel, RULE-02a category 3);
    the same data is carried here for structured access by tools /
    validators.

    ADR-055/057 boundary: this class carries the descriptive
    ``voice_profiles_text`` only (when supplied). The numeric
    ``voice_metrics`` NEVER appear on this dataclass.

    Attributes:
        text_to_analyze: The user's selected dialogue passage.
        mode: "analyze" or "improve".
        characters: Canonical speaker roster (from DialogueParser attribution).
        project_title: Project title (prompt context).
        genre: Project genre (prompt context).
        writing_language: Language code ("en", "de", "fr").
        voice_profiles_text: Descriptive character voice profiles text
            (mirrors AdaptiveContext.voice_profiles_text -- speech_summary
            only, never voice_metrics).
    """

    def __init__(
        self,
        *,
        text_to_analyze: str = "",
        mode: str = "analyze",
        characters: list[str] | None = None,
        project_title: str = "",
        genre: str = "",
        writing_language: str = "en",
        voice_profiles_text: str = "",
    ) -> None:
        self.text_to_analyze = text_to_analyze
        self.mode = mode
        self.characters = list(characters) if characters else []
        self.project_title = project_title
        self.genre = genre
        self.writing_language = writing_language
        self.voice_profiles_text = voice_profiles_text
