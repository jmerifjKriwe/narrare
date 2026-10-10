"""Request, session, and scene data models for the writing subsystem.

Extracted from ``models.py`` (RULE-04) — these are input / state types,
not part of the context assembly pipeline.

Pure data containers — no I/O, no side-effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from narrare_core.writing._enums import ConnectionState, StreamStatus

if TYPE_CHECKING:
    from narrare_core.planning.models import ScenePlanData
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
    # Structured scene plans (PLAN-001 spec §8.1): when non-empty, the
    # scene-by-scene pipeline renders these directly instead of parsing
    # ``outline``. Default keeps every pre-scene constructor valid.
    scenes: tuple[SceneSpec, ...] | None = None


@dataclass(frozen=True, slots=True)
class SceneSpec:
    """Structured scene input for scene-by-scene generation (spec §8.1).

    Identity-free plan data — the writer needs names and beats, not KB
    linkage or database ids. ``present_characters`` holds ``(name, goal)``
    pairs. Use :func:`scene_spec_from_plan` to adapt a planning
    ``ScenePlanData`` snapshot; API-layer schemas map into this directly.
    """

    title: str = ""
    pov_character_name: str = ""
    location_name: str = ""
    present_characters: tuple[tuple[str, str], ...] = ()
    purpose: str = ""
    conflict: str = ""
    resolution: str = ""
    beats: tuple[str, ...] = ()
    status: str = "planned"


def scene_spec_from_plan(scene: ScenePlanData) -> SceneSpec:
    """Adapt a planning ``ScenePlanData`` snapshot into a ``SceneSpec``.

    Core-internal adapter (spec §8.1): keeps the API layer free of mapping
    logic. ``ScenePresence`` entries flatten to ``(name, goal)`` pairs;
    ``status`` maps to its plain string value.
    """
    return SceneSpec(
        title=scene.title,
        pov_character_name=scene.pov_character_name,
        location_name=scene.location_name,
        present_characters=tuple((p.name, p.goal) for p in scene.present_characters),
        purpose=scene.purpose,
        conflict=scene.conflict,
        resolution=scene.resolution,
        beats=scene.beats,
        # str() covers both SceneStatus members (StrEnum → value) and raw
        # strings sneaking in via unvalidated dataclass construction.
        status=str(scene.status),
    )


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SessionState:
    """State of an interactive writing session.

    Tracks the conversation history and accumulated prose buffer for a
    single ``interactive_session`` or ``interview_assisted`` writing flow.

    Recovery fields (ADR-052) are populated by the backend control service
    during streaming/stop/reattach; core treats them as opaque state on
    the dataclass.  They do not drive any core behaviour directly — they
    exist so that a serialized session survives a transport reconnect with
    its active-turn metadata intact.
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

    # --- ADR-052 recovery fields (safe defaults for legacy payloads) ---
    active_invocation_id: UUID | None = None
    stream_status: StreamStatus = StreamStatus.IDLE
    last_sequence: int = 0
    active_partial_prose: str = ""
    connection_state: ConnectionState = ConnectionState.CONNECTED


# ---------------------------------------------------------------------------
# Reattach outcome (ADR-052 Phase 2 Core)
# ---------------------------------------------------------------------------

# The ``kind`` literal field is the discriminator for ``ReattachOutcome``.
# Each variant is a frozen dataclass so callers can pattern-match on the
# union and the backend can serialize the ``kind`` straight into a WS
# ``session_recovered`` / ``recovery_failed`` message payload.


@dataclass(frozen=True, slots=True, kw_only=True)
class Reattached:
    """Successful reattach — the session is live and owned by the caller."""

    session_id: UUID
    chapter_id: UUID
    project_id: UUID
    user_id: UUID
    stream_status: StreamStatus
    last_sequence: int
    active_partial_prose: str
    active_invocation_id: UUID | None
    kind: Literal["recovered"] = "recovered"


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionNotFound:
    """No cached state exists for the requested session id."""

    session_id: UUID
    kind: Literal["not_found"] = "not_found"


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionExpired:
    """The session cache entry exists but ``is_active`` is False."""

    session_id: UUID
    kind: Literal["expired"] = "expired"


@dataclass(frozen=True, slots=True, kw_only=True)
class OwnershipMismatch:
    """The session exists and is active but belongs to a different user/project."""

    session_id: UUID
    user_id: UUID
    project_id: UUID
    kind: Literal["ownership_mismatch"] = "ownership_mismatch"


#: Discriminated union returned by ``SessionManager.reattach_session``.
ReattachOutcome = Reattached | SessionNotFound | SessionExpired | OwnershipMismatch


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
