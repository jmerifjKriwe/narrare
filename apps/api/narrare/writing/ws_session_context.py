"""Connection-scoped context for WebSocket writing sessions.

The handler creates this value object after accepting a WebSocket and
creating the session. Message routers and transport dispatchers receive the
context instead of reading mutable state from ``WritingSessionHandler``.

See: ADR-045, CONSTRAINTS.md RULE-04/RULE-06/RULE-12.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class WritingSessionContext:
    """Identifiers and mode for a single WebSocket writing session.

    Attributes:
        session_id: WebSocket session identifier.
        user_id: Authenticated user identifier.
        project_id: Project identifier used by invocation enrichment.
        chapter_id: Chapter being written.
        mode: Session mode, e.g. ``interactive_session`` or
            ``interview_assisted``.
    """

    session_id: UUID
    user_id: UUID
    project_id: UUID
    chapter_id: UUID
    mode: str
