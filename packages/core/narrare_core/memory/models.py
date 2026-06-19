"""Data models for the memory subsystem.

Defines feedback events (user interactions with AI suggestions) and
preference profiles (aggregated user preferences derived from feedback).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class FeedbackAction(StrEnum):
    """User action in response to an AI suggestion."""

    ACCEPT = "accept"
    REJECT = "reject"
    MODIFY = "modify"


@dataclass(frozen=True, slots=True)
class FeedbackEvent:
    """A single user feedback event on an AI suggestion.

    Captures what the user did with a suggestion (accept, reject, modify),
    along with enough context to derive writing preferences over time.
    """

    user_id: UUID
    project_id: UUID
    suggestion_id: UUID
    action: FeedbackAction
    intent: str
    suggestion_text: str
    modification: str = ""
    rating: int | None = None  # 1-5, optional user rating
    context: dict[str, object] = field(default_factory=dict[str, object])
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )


@dataclass(slots=True)
class PreferenceProfile:
    """Aggregated user preferences derived from feedback history.

    Tracks style, content, and constraint preferences for a user/project
    pair. Provides ``to_prompt_text()`` for inclusion in LLM prompts.
    """

    user_id: UUID
    project_id: UUID
    event_count: int = 0
    confidence: float = 0.0
    last_updated: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )
    style: dict[str, str] = field(default_factory=dict[str, str])
    content: dict[str, str] = field(default_factory=dict[str, str])
    constraints: list[str] = field(default_factory=list[str])

    def to_prompt_text(self) -> str:
        """Format preferences as markdown-like text for prompt injection.

        Returns an empty string when ``event_count`` is zero (no data yet).
        Each section (style, content, constraints) is only included if it
        has entries. Keys are humanised: ``short_sentences`` → ``Short sentences``.
        """
        if self.event_count == 0:
            return ""

        parts: list[str] = []

        if self.style:
            lines = ["## Style preferences"]
            for key, value in self.style.items():
                lines.append(f"- {_humanise_key(key)}: {value}")
            parts.append("\n".join(lines))

        if self.content:
            lines = ["## Content preferences"]
            for key, value in self.content.items():
                lines.append(f"- {_humanise_key(key)}: {value}")
            parts.append("\n".join(lines))

        if self.constraints:
            lines = ["## Constraints"]
            for constraint in self.constraints:
                lines.append(f"- {constraint}")
            parts.append("\n".join(lines))

        return "\n\n".join(parts)


class MemoryPrecedenceLevel(StrEnum):
    """Source precedence for a memory entry."""

    LEARNED_MEMORY = "learned_memory"
    DETAIL_MEMORY = "detail_memory"
    CORE_MEMORY = "core_memory"


class LearningEventKind(StrEnum):
    """ADT-style variant tag — what triggered this learning event.

    See ADR-045 Decision 8 for the full taxonomy and the precedence/privacy
    boundaries that apply to each kind. Every kind resolves to
    ``MemoryPrecedenceLevel.LEARNED_MEMORY``: learned preferences never
    override current instructions, curated KB, or objective facts. The
    ``suggestion_accepted``/``suggestion_rejected``/``suggestion_modified``
    ADR kinds are represented upstream via ``FeedbackAction`` and the
    ``FeedbackService`` translation path, so they do not appear here.
    """

    SUGGESTION_MODIFIED = "suggestion_modified"
    """User edited an AI suggestion before accepting it — a style/structure
    preference extracted from deltas, never raw prose by default."""

    REPEATED_STEERING = "repeated_steering"
    """High-confidence style/process preference repeated across sessions
    (e.g. 'shorter paragraphs', 'ask before adding lore')."""

    KB_INTERVIEW_STYLE = "kb_interview_style"
    """Interaction style only; never factual world data.

    Captures how the user prefers KB interview prompts to be framed
    (e.g. 'prefers concise questions') — a style marker, not world lore.
    """

    ANALYSIS_CALIBRATION = "analysis_calibration"
    """Reviewer lens; cannot suppress evidence/confidence gates.

    Captures how the user wants analysis feedback calibrated
    (e.g. 'prioritizes pacing feedback') — a tone preference that never
    weakens objective evidence or confidence thresholds.
    """


@dataclass(frozen=True, slots=True)
class LearningEvent:
    """A learning event extracted from a user interaction.

    Records what was learned (the preference_summary) without exposing
    raw prose (raw_excerpt must not be included in memory_text).
    """

    user_id: UUID
    project_id: UUID
    kind: LearningEventKind
    intent: str
    mode: str
    preference_summary: str
    source_event_id: UUID | None = None
    raw_excerpt: str | None = None
    confidence: float = 1.0

    def to_memory_text(self) -> str:
        """Build privacy-safe memory text (no raw_excerpt)."""
        prefix = (
            "learned preference"
            if self.precedence_level == MemoryPrecedenceLevel.LEARNED_MEMORY
            else "memory"
        )
        return f"[{prefix}] {self.preference_summary}"

    @property
    def precedence_level(self) -> MemoryPrecedenceLevel:
        """Derive precedence from event kind."""
        return MemoryPrecedenceLevel.LEARNED_MEMORY

    def to_mem0_metadata(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "precedence_level": self.precedence_level.value,
            "confidence": self.confidence,
        }


def _humanise_key(key: str) -> str:
    """Convert a snake_case key to a human-readable label.

    Examples::

        >>> _humanise_key("short_sentences")
        'Short sentences'
        >>> _humanise_key("pov")
        'Pov'
    """
    return re.sub(r"_", " ", key).capitalize()
