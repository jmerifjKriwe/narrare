"""Pure operations on KB creation sessions.

Extracted from session_service.py for RULE-04 (file size limit):
effective field-value extraction and the status guard shared by every
lifecycle operation. No I/O, no store access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare.kb.session_models import KBCreationSession


def extract_filled_fields(session: KBCreationSession) -> dict[str, str]:
    """Collect each field's effective value (final → user → AI suggestion)."""
    result: dict[str, str] = {}
    for field in session.fields:
        value = field.final_value or field.user_value or field.ai_suggested_value
        if value:
            result[field.field_key] = value
    return result


def validate_session_status(session: KBCreationSession, *allowed: str) -> None:
    """Raise ValueError when the session status is not in ``allowed``."""
    if session.status not in allowed:
        raise ValueError(
            f"Session {session.id} has status '{session.status}', expected one of {allowed}"
        )
