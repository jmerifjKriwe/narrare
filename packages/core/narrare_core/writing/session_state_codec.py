"""Serialize/deserialize :class:`SessionState` for the session cache.

Extracted from ``session_manager.py`` for RULE-04 (the manager was at 246
lines and the ADR-052 recovery fields would push it over the budget).

This module is the single source of truth for the JSON shape of a cached
session.  Both legacy payloads (written before ADR-052, missing the five
recovery keys) and ADR-052 payloads deserialize correctly — recovery
fields use ``data.get(key, default)`` so older cache entries load with
safe defaults.

See: docs/architecture/decisions/ADR-052-session-stop-recovery.md (ADR-052)
"""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from narrare_core.writing._enums import ConnectionState, StreamStatus
from narrare_core.writing.requests import SessionState

__all__ = [
    "SessionStateCodec",
    "deserialize_session_state",
    "serialize_session_state",
]


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def serialize_session_state(state: SessionState) -> str:
    """Serialize a :class:`SessionState` to a JSON string.

    The five ADR-052 recovery fields are included.  ``active_invocation_id``
    becomes ``None`` or its string form; the enums are stored as their
    ``.value`` strings so the payload is stable across Python versions.
    """
    return json.dumps(_state_to_dict(state))


def deserialize_session_state(raw: str) -> SessionState:
    """Deserialize a JSON string into a :class:`SessionState`.

    Uses ``data.get(key, default)`` for every recovery field so legacy
    payloads (written before ADR-052) load with safe defaults.
    """
    return _dict_to_state(json.loads(raw))


# ---------------------------------------------------------------------------
# Internal field mapping
# ---------------------------------------------------------------------------


def _state_to_dict(state: SessionState) -> dict[str, object]:
    """Map a SessionState to the cache payload dict."""
    invocation = state.active_invocation_id
    return {
        "session_id": str(state.session_id),
        "chapter_id": str(state.chapter_id),
        "project_id": str(state.project_id),
        "user_id": str(state.user_id),
        "conversation_history": list(state.conversation_history),
        "prose_buffer": state.prose_buffer,
        "started_at": state.started_at.isoformat(),
        "last_activity": state.last_activity.isoformat(),
        "is_active": state.is_active,
        # --- ADR-052 recovery fields ---
        "active_invocation_id": (str(invocation) if invocation is not None else None),
        "stream_status": state.stream_status.value,
        "last_sequence": state.last_sequence,
        "active_partial_prose": state.active_partial_prose,
        "connection_state": state.connection_state.value,
    }


def _dict_to_state(data: dict[str, object]) -> SessionState:
    """Map a cache payload dict back to a SessionState.

    Recovery fields use ``.get(...)`` so legacy payloads without those keys
    still load with defaults.
    """
    raw_invocation = data.get("active_invocation_id")
    raw_history = data.get("conversation_history")
    history: list[dict[str, str]] = (
        [dict(item) for item in raw_history]  # type: ignore[arg-type]
        if isinstance(raw_history, list)
        else []
    )
    return SessionState(
        session_id=UUID(str(data["session_id"])),
        chapter_id=UUID(str(data["chapter_id"])),
        project_id=UUID(str(data["project_id"])),
        user_id=UUID(str(data["user_id"])),
        conversation_history=history,
        prose_buffer=str(data.get("prose_buffer", "")),
        started_at=datetime.fromisoformat(str(data["started_at"])),
        last_activity=datetime.fromisoformat(str(data["last_activity"])),
        is_active=bool(data.get("is_active", True)),
        # --- ADR-052 recovery fields (safe defaults for legacy payloads) ---
        active_invocation_id=(UUID(str(raw_invocation)) if raw_invocation else None),
        stream_status=StreamStatus(str(data.get("stream_status", StreamStatus.IDLE.value))),
        last_sequence=int(str(data.get("last_sequence", 0))),
        active_partial_prose=str(data.get("active_partial_prose", "")),
        connection_state=ConnectionState(
            str(data.get("connection_state", ConnectionState.CONNECTED.value))
        ),
    )


# ---------------------------------------------------------------------------
# Object form (dependency-injectable)
# ---------------------------------------------------------------------------


class SessionStateCodec:
    """Object form of the serialize/deserialize helpers.

    Useful as an explicit dependency that can be injected (and swapped in
    tests) when a caller prefers a stateful codec object over module-level
    functions.  Both forms produce byte-identical output.
    """

    @staticmethod
    def serialize(state: SessionState) -> str:
        return serialize_session_state(state)

    @staticmethod
    def deserialize(raw: str) -> SessionState:
        return deserialize_session_state(raw)
