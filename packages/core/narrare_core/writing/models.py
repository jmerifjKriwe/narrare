"""Data models for the writing subsystem.

Defines dataclasses used across the writing pipeline.
Enums live in ``_enums.py`` (RULE-04).

These are pure data containers — no I/O, no side-effects, no knowledge
of HTTP, users, or database sessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from narrare_core.writing._enums import GenerationMode
    from narrare_core.writing.context_models import ContextMetadata

# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class WritingContext:
    """Assembled context for a writing generation call.

    Contains all five tiers of context information ready for prompt
    injection.  Percentages are *budget guidelines* — actual allocation
    is handled by the context assembler.
    """

    # Tier 1 — Immediate context (30 % budget)
    chapter_content: str = ""
    chapter_frontmatter: str = ""
    chapter_outline: str = ""

    # Tier 2 — Recent history (20 % budget)
    recent_chapters: str = ""
    recent_chapter_count: int = 0

    # Tier 3 — KB entities referenced from frontmatter (25 % budget)
    kb_characters: str = ""
    kb_locations: str = ""
    kb_factions: str = ""

    # Tier 4 — KB entities via similarity suggestion (15 % budget)
    kb_suggested: str = ""

    # Tier 5 — Pinned items (10 % budget, bypass limits)
    kb_pinned: str = ""

    # Metadata
    project_title: str = ""
    genre: str = ""
    language: str = "en"  # prompt file selection (en/de/fr)
    tone: str = "balanced"
    word_target: int | None = None
    writing_language: str = "en"  # output language (freetext)

    # Character voice profiles (extracted from KB character speech metadata)
    character_voice_profiles: str = ""

    # Memory layer
    user_preferences: str = ""
    avoidance_patterns: str = ""

    # Context metadata (populated by assembler)
    character_names: list[str] = field(default_factory=lambda: [])
    location_names: list[str] = field(default_factory=lambda: [])
    faction_names: list[str] = field(default_factory=lambda: [])
    total_budget_tokens: int = 0

    # Flags
    is_first_chapter: bool = False
    is_sparse_kb: bool = False

    def to_metadata(self) -> ContextMetadata:
        """Extract a lightweight metadata summary for client display."""
        from narrare_core.writing.context_models import ContextMetadata

        return ContextMetadata(
            kb_characters_count=self.kb_characters.count("### ") if self.kb_characters else 0,
            kb_locations_count=self.kb_locations.count("### ") if self.kb_locations else 0,
            kb_factions_count=self.kb_factions.count("### ") if self.kb_factions else 0,
            kb_suggested_count=self.kb_suggested.count("### ") if self.kb_suggested else 0,
            kb_pinned_count=self.kb_pinned.count("### ") if self.kb_pinned else 0,
            recent_chapter_count=self.recent_chapter_count,
            character_names=list(self.character_names),
            location_names=list(self.location_names),
            faction_names=list(self.faction_names),
            is_first_chapter=self.is_first_chapter,
            has_user_preferences=bool(self.user_preferences.strip()),
            tone=self.tone,
            total_budget_tokens=self.total_budget_tokens,
        )

    def to_prompt_variables(self) -> dict[str, str]:
        """Map writing context to prompt template variables.

        Returns a flat dictionary suitable for ``str.format_map()`` or
        Jinja-style template substitution.  ``None``-valued fields are
        rendered as empty strings so templates never see ``None``.
        """
        return {
            "chapter_content": self.chapter_content,
            "chapter_frontmatter": self.chapter_frontmatter,
            "chapter_outline": self.chapter_outline,
            "recent_chapters": self.recent_chapters,
            "recent_chapter_count": str(self.recent_chapter_count),
            "kb_characters": self.kb_characters,
            "kb_locations": self.kb_locations,
            "kb_factions": self.kb_factions,
            "kb_suggested": self.kb_suggested,
            "kb_pinned": self.kb_pinned,
            "character_voice_profiles": self.character_voice_profiles,
            "project_title": self.project_title,
            "genre": self.genre,
            "tone": self.tone,
            "writing_language": self.writing_language,
            "word_target": str(self.word_target) if self.word_target else "",
            "user_preferences": self.user_preferences,
            "avoidance_patterns": self.avoidance_patterns,
            "is_first_chapter": str(self.is_first_chapter).lower(),
            "is_sparse_kb": str(self.is_sparse_kb).lower(),
        }


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Input for a generation request.

    ``id`` is auto-generated but can be overridden for replay / testing.
    """

    chapter_id: UUID
    project_id: UUID
    user_id: UUID
    mode: GenerationMode
    outline: str | None = None
    prompt: str | None = None
    auto_continue: bool = False
    word_target: int | None = None
    tone: str = "balanced"
    writing_language: str = "en"
    id: UUID = field(default_factory=uuid4)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SessionState:
    """State of an interactive writing session.

    Tracks the conversation history and accumulated prose buffer for a
    single ``interactive_session`` or ``interview_assisted`` writing flow.
    """

    session_id: UUID
    chapter_id: UUID
    project_id: UUID
    user_id: UUID
    conversation_history: list[dict[str, str]] = field(
        default_factory=list[dict[str, str]],
    )
    prose_buffer: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SceneState:
    """State of a single scene in scene-by-scene mode.

    ``generated_text`` is empty until the scene is produced.  Once the
    user accepts the scene, ``is_accepted`` is set to ``True``.
    """

    scene_number: int
    outline: str
    generated_text: str = ""
    is_accepted: bool = False
