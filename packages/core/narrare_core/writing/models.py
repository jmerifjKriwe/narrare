"""Data models for the writing subsystem.

Defines generation modes, status lifecycle, and dataclasses used across
the writing pipeline.  These are pure data containers — no I/O, no
side-effects, no knowledge of HTTP, users, or database sessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GenerationMode(StrEnum):
    """Four supported generation modes.

    Each mode drives a different pipeline configuration in the prompt
    composer and determines which context tiers receive the most budget.
    """

    FULL_DRAFT = "full_draft"
    SCENE_BY_SCENE = "scene_by_scene"
    INTERVIEW_ASSISTED = "interview_assisted"
    INTERACTIVE_SESSION = "interactive_session"


class GenerationStatus(StrEnum):
    """Status lifecycle for a generation request.

    A request transitions through these states in order::

        PENDING → STREAMING → COMPLETED
                              ↘ STOPPED
                              ↘ FAILED
    """

    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


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

    # Memory layer
    user_preferences: str = ""
    avoidance_patterns: str = ""

    # Flags
    is_first_chapter: bool = False
    is_sparse_kb: bool = False

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
