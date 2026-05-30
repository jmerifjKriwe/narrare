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
