"""Public WebSocket payload builders for writing sessions.

The session-control service returns internal ADR-052 DTOs with backend-owned
field names (``status``, ``kind``, ``last_sequence``). This module is the
transport boundary that converts those DTOs into the public WebSocket contract
declared by the frontend ``SessionResponse`` type (RULE-17).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeIs

from narrare.writing.session_control_contracts import (
    ReattachOutcomeKind,
    StopGenerationStatus,
)

STOP_REASON_BY_STATUS: Mapping[str, str] = {
    StopGenerationStatus.STOPPED: "user_stop",
    StopGenerationStatus.NO_ACTIVE_TURN: "already_idle",
}

RECOVERY_REASON_BY_KIND: Mapping[str, str] = {
    ReattachOutcomeKind.NOT_FOUND: "session_not_found",
    ReattachOutcomeKind.EXPIRED: "session_expired",
    ReattachOutcomeKind.OWNERSHIP_MISMATCH: "ownership_mismatch",
}


def build_generation_stopped_payload(
    result: Mapping[str, object],
    *,
    fallback_invocation_id: str,
) -> dict[str, object]:
    """Build a public ``generation_stopped`` WebSocket payload.

    Args:
        result: Internal stop-generation DTO from the control service.
        fallback_invocation_id: Request invocation id used if the DTO is
            missing or corrupt.

    Returns:
        Payload matching the frontend ``SessionResponse`` contract.
    """
    return {
        "type": "generation_stopped",
        "invocation_id": _string_field(result.get("invocation_id"), fallback_invocation_id),
        "partial_prose": _string_field(result.get("partial_prose"), ""),
        "sequence": _integer_field(result.get("sequence"), 0),
        "reason": STOP_REASON_BY_STATUS.get(
            _string_field(result.get("status"), ""),
            "already_idle",
        ),
    }


def build_session_recovered_payload(outcome: Mapping[str, object]) -> dict[str, object]:
    """Build a public ``session_recovered`` WebSocket payload.

    Args:
        outcome: Internal reattach DTO from the control service.

    Returns:
        Payload matching the frontend ``SessionResponse`` contract.
    """
    return {
        "type": "session_recovered",
        "session_id": _string_field(outcome.get("session_id"), ""),
        "stream_status": _string_field(outcome.get("stream_status"), "idle"),
        "partial_prose": _string_field(outcome.get("active_partial_prose"), ""),
        "sequence": _integer_field(outcome.get("last_sequence"), 0),
        "transcript_tail": _transcript_tail(outcome.get("transcript_tail")),
    }


def build_recovery_failed_payload(outcome: Mapping[str, object]) -> dict[str, object]:
    """Build a public ``recovery_failed`` WebSocket payload.

    Args:
        outcome: Internal reattach failure DTO from the control service.

    Returns:
        Payload matching the frontend ``SessionResponse`` contract.
    """
    return {
        "type": "recovery_failed",
        "reason": RECOVERY_REASON_BY_KIND.get(
            _string_field(outcome.get("kind"), ""),
            "session_not_found",
        ),
    }


def _string_field(value: object, default: str) -> str:
    """Return ``value`` if it is a string, otherwise ``default``."""
    if isinstance(value, str):
        return value
    return default


def _integer_field(value: object, default: int) -> int:
    """Return ``value`` if it is an integer, otherwise ``default``."""
    if isinstance(value, int):
        return value
    return default


def _transcript_tail(value: object) -> list[dict[str, str]]:
    """Normalize a transcript-tail object into public transcript entries."""
    if not _is_object_list(value):
        return []

    normalized: list[dict[str, str]] = []
    for item in value:
        if not _is_object_mapping(item):
            continue
        role = item.get("role")
        if not isinstance(role, str):
            continue
        normalized_item = {"role": role}
        content = item.get("content")
        if isinstance(content, str):
            normalized_item["content"] = content
        prose = item.get("prose")
        if isinstance(prose, str):
            normalized_item["prose"] = prose
        normalized.append(normalized_item)
    return normalized


def _is_object_mapping(value: object) -> TypeIs[Mapping[object, object]]:
    """Return whether ``value`` is a mapping with object-typed keys/values."""
    return isinstance(value, Mapping)


def _is_object_list(value: object) -> TypeIs[list[object]]:
    """Return whether ``value`` is a list with object-typed items."""
    return isinstance(value, list)
