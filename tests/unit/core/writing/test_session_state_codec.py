"""Tests for session_state_codec — extracted serialize/deserialize (RULE-04, ADR-052).

Covers:
1. ``serialize_session_state`` includes the five ADR-052 recovery fields.
2. Round-trip (serialize → deserialize) preserves every field, including
   non-default values for the recovery fields.
3. Legacy payloads (cache entries written before ADR-052) that omit the
   recovery keys deserialize with safe defaults — backward compatibility.
4. ``SessionStateCodec`` object form delegates to the module-level functions.
5. ``serialize_session_state`` produces valid JSON (parseable by ``json.loads``).
"""

from __future__ import annotations

import json
from uuid import uuid4

from narrare_core.writing._enums import ConnectionState, StreamStatus
from narrare_core.writing.requests import SessionState
from narrare_core.writing.session_state_codec import (
    SessionStateCodec,
    deserialize_session_state,
    serialize_session_state,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides: object) -> SessionState:
    """Build a SessionState with random UUIDs and optional field overrides."""
    defaults: dict[str, object] = {
        "session_id": uuid4(),
        "chapter_id": uuid4(),
        "project_id": uuid4(),
        "user_id": uuid4(),
    }
    defaults.update(overrides)
    return SessionState(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Serialization includes recovery fields
# ---------------------------------------------------------------------------


class TestSerializeIncludesRecoveryFields:
    """serialize_session_state must emit the ADR-052 recovery keys."""

    def test_serialized_payload_contains_all_recovery_keys(self) -> None:
        state = _make_state()
        payload = json.loads(serialize_session_state(state))
        for key in (
            "active_invocation_id",
            "stream_status",
            "last_sequence",
            "active_partial_prose",
            "connection_state",
        ):
            assert key in payload, f"missing key in serialized payload: {key}"

    def test_active_invocation_id_serialized_as_string_or_null(self) -> None:
        invocation = uuid4()
        populated = _make_state(active_invocation_id=invocation)
        empty = _make_state(active_invocation_id=None)

        populated_payload = json.loads(serialize_session_state(populated))
        empty_payload = json.loads(serialize_session_state(empty))

        assert populated_payload["active_invocation_id"] == str(invocation)
        assert empty_payload["active_invocation_id"] is None

    def test_enums_serialized_as_their_string_values(self) -> None:
        state = _make_state(
            stream_status=StreamStatus.STREAMING,
            connection_state=ConnectionState.DISCONNECTED,
        )
        payload = json.loads(serialize_session_state(state))
        assert payload["stream_status"] == "streaming"
        assert payload["connection_state"] == "disconnected"

    def test_serialize_produces_valid_json_string(self) -> None:
        state = _make_state(
            last_sequence=42,
            active_partial_prose="partial text",
        )
        raw = serialize_session_state(state)
        assert isinstance(raw, str)
        # Round-trip through json.loads must not raise
        json.loads(raw)


# ---------------------------------------------------------------------------
# Round-trip preserves all fields
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """serialize → deserialize preserves every field."""

    def test_round_trip_preserves_all_fields(self) -> None:
        invocation = uuid4()
        original = _make_state(
            active_invocation_id=invocation,
            stream_status=StreamStatus.STREAMING,
            last_sequence=9,
            active_partial_prose="abc",
            connection_state=ConnectionState.DISCONNECTED,
        )
        round_tripped = deserialize_session_state(serialize_session_state(original))
        assert round_tripped.active_invocation_id == invocation
        assert round_tripped.stream_status is StreamStatus.STREAMING
        assert round_tripped.last_sequence == 9
        assert round_tripped.active_partial_prose == "abc"
        assert round_tripped.connection_state is ConnectionState.DISCONNECTED

    def test_round_trip_preserves_legacy_fields(self) -> None:
        original = _make_state()
        original.conversation_history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        original.prose_buffer = "some prose"
        original.is_active = False

        round_tripped = deserialize_session_state(serialize_session_state(original))

        assert round_tripped.session_id == original.session_id
        assert round_tripped.chapter_id == original.chapter_id
        assert round_tripped.project_id == original.project_id
        assert round_tripped.user_id == original.user_id
        assert round_tripped.conversation_history == original.conversation_history
        assert round_tripped.prose_buffer == "some prose"
        assert round_tripped.started_at == original.started_at
        assert round_tripped.last_activity == original.last_activity
        assert round_tripped.is_active is False

    def test_round_trip_preserves_null_invocation_id(self) -> None:
        original = _make_state(active_invocation_id=None)
        round_tripped = deserialize_session_state(serialize_session_state(original))
        assert round_tripped.active_invocation_id is None


# ---------------------------------------------------------------------------
# Backward compatibility — legacy payloads without recovery fields
# ---------------------------------------------------------------------------


class TestLegacyPayloadCompat:
    """Payloads written before ADR-052 (missing recovery keys) must still load."""

    @staticmethod
    def _legacy_payload() -> str:
        """A payload shape from before the recovery fields existed."""
        return json.dumps(
            {
                "session_id": str(uuid4()),
                "chapter_id": str(uuid4()),
                "project_id": str(uuid4()),
                "user_id": str(uuid4()),
                "conversation_history": [{"role": "user", "content": "legacy"}],
                "prose_buffer": "legacy prose",
                "started_at": "2026-01-01T00:00:00+00:00",
                "last_activity": "2026-01-01T00:00:00+00:00",
                "is_active": True,
            },
        )

    def test_legacy_payload_deserializes_with_default_recovery_fields(self) -> None:
        state = deserialize_session_state(self._legacy_payload())
        assert state.active_invocation_id is None
        assert state.stream_status is StreamStatus.IDLE
        assert state.last_sequence == 0
        assert state.active_partial_prose == ""
        assert state.connection_state is ConnectionState.CONNECTED

    def test_legacy_payload_preserves_legacy_fields(self) -> None:
        state = deserialize_session_state(self._legacy_payload())
        assert state.prose_buffer == "legacy prose"
        assert state.conversation_history == [{"role": "user", "content": "legacy"}]
        assert state.is_active is True

    def test_legacy_payload_then_reserialize_includes_recovery_keys(self) -> None:
        """A legacy payload, once loaded and re-serialized, must include the keys."""
        state = deserialize_session_state(self._legacy_payload())
        payload = json.loads(serialize_session_state(state))
        assert "active_invocation_id" in payload
        assert "stream_status" in payload
        assert "connection_state" in payload


# ---------------------------------------------------------------------------
# SessionStateCodec object form
# ---------------------------------------------------------------------------


class TestSessionStateCodec:
    """The object form delegates to the module-level functions."""

    def test_codec_serialize_matches_function(self) -> None:
        codec = SessionStateCodec()
        state = _make_state(last_sequence=3)
        assert codec.serialize(state) == serialize_session_state(state)

    def test_codec_deserialize_matches_function(self) -> None:
        codec = SessionStateCodec()
        state = _make_state(last_sequence=3)
        raw = serialize_session_state(state)
        assert codec.deserialize(raw) == deserialize_session_state(raw)

    def test_codec_round_trip_preserves_fields(self) -> None:
        codec = SessionStateCodec()
        original = _make_state(
            stream_status=StreamStatus.FAILED,
            connection_state=ConnectionState.REATTACHING,
            last_sequence=7,
            active_partial_prose="x",
        )
        round_tripped = codec.deserialize(codec.serialize(original))
        assert round_tripped == original
