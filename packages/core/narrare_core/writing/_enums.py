"""Generation enums for the writing subsystem.

Extracted from ``models.py`` for RULE-04 compliance.
"""

from __future__ import annotations

from enum import StrEnum


class GenerationMode(StrEnum):
    """Supported generation modes.

    Each mode drives a different pipeline configuration in the prompt
    composer and determines which context tiers receive the most budget.
    """

    FULL_DRAFT = "full_draft"
    EXTEND = "extend"
    REWRITE = "rewrite"
    CO_AUTHOR = "co_author"
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


class StreamStatus(StrEnum):
    """Lifecycle of a single streaming turn within a writing session (ADR-052).

    Distinct from :class:`GenerationStatus`: ``GenerationStatus`` tracks the
    overall generation request lifecycle (used by the writing pipeline),
    whereas ``StreamStatus`` tracks one streaming turn of an interactive
    session for stop/recovery purposes.

    Transitions::

        idle → streaming → completed
                         ↘ stopped    (server-side cancel)
                         ↘ failed     (error)
    """

    IDLE = "idle"
    STREAMING = "streaming"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


class ConnectionState(StrEnum):
    """Transport connection state for a writing session (ADR-052).

    A reattach request is only valid when the cached state is ``connected``
    or ``disconnected`` (not ``expired``).  Mutated by the backend transport
    layer (``ws_handler``); core treats this field as opaque state on
    :class:`SessionState`.
    """

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    REATTACHING = "reattaching"
    EXPIRED = "expired"
