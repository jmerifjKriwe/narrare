"""Request, session, and scene data models for the writing subsystem.

Extracted from ``models.py`` (RULE-04) — these are input / state types,
not part of the context assembly pipeline.

Pure data containers — no I/O, no side-effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from narrare_core.writing._enums import GenerationMode


# ---------------------------------------------------------------------------
# Request
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
