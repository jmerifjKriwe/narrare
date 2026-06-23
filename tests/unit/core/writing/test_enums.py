"""Tests for writing/_enums.py — GenerationMode, GenerationStatus, StreamStatus,
ConnectionState enums.

Covers:
1. All GenerationMode values
2. All GenerationStatus values
3. StrEnum behavior (values are strings)
4. StreamStatus (ADR-052) — single-turn streaming lifecycle
5. ConnectionState (ADR-052) — transport connection lifecycle for recovery
"""

from __future__ import annotations

from narrare_core.writing._enums import (
    ConnectionState,
    GenerationMode,
    GenerationStatus,
    StreamStatus,
)


class TestGenerationMode:
    """GenerationMode has all expected values."""

    def test_full_draft(self) -> None:
        assert GenerationMode.FULL_DRAFT == "full_draft"

    def test_extend(self) -> None:
        assert GenerationMode.EXTEND == "extend"

    def test_rewrite(self) -> None:
        assert GenerationMode.REWRITE == "rewrite"

    def test_scene_by_scene(self) -> None:
        assert GenerationMode.SCENE_BY_SCENE == "scene_by_scene"

    def test_interview_assisted(self) -> None:
        assert GenerationMode.INTERVIEW_ASSISTED == "interview_assisted"

    def test_interactive_session(self) -> None:
        assert GenerationMode.INTERACTIVE_SESSION == "interactive_session"

    def test_all_values_count(self) -> None:
        assert len(list(GenerationMode)) == 7  # +CO_AUTHOR (b18d571)

    def test_values_are_strings(self) -> None:
        for mode in GenerationMode:
            assert isinstance(mode, str)


class TestGenerationStatus:
    """GenerationStatus has all expected lifecycle values."""

    def test_pending(self) -> None:
        assert GenerationStatus.PENDING == "pending"

    def test_streaming(self) -> None:
        assert GenerationStatus.STREAMING == "streaming"

    def test_completed(self) -> None:
        assert GenerationStatus.COMPLETED == "completed"

    def test_stopped(self) -> None:
        assert GenerationStatus.STOPPED == "stopped"

    def test_failed(self) -> None:
        assert GenerationStatus.FAILED == "failed"

    def test_all_values_count(self) -> None:
        assert len(list(GenerationStatus)) == 5

    def test_values_are_strings(self) -> None:
        for status in GenerationStatus:
            assert isinstance(status, str)


class TestStreamStatus:
    """StreamStatus (ADR-052) — single-turn streaming lifecycle.

    Transitions: idle -> streaming -> completed | stopped | failed
    """

    def test_members(self) -> None:
        assert {m.value for m in StreamStatus} == {
            "idle",
            "streaming",
            "stopped",
            "completed",
            "failed",
        }

    def test_round_trip(self) -> None:
        for m in StreamStatus:
            assert StreamStatus(m.value) is m

    def test_values_are_strings(self) -> None:
        for status in StreamStatus:
            assert isinstance(status, str)

    def test_idle_is_default_start(self) -> None:
        assert StreamStatus("idle") is StreamStatus.IDLE


class TestConnectionState:
    """ConnectionState (ADR-052) — transport connection lifecycle.

    A reattach request is only valid when the cached state is ``connected``
    or ``disconnected`` (not ``expired``).
    """

    def test_members(self) -> None:
        assert {m.value for m in ConnectionState} == {
            "connected",
            "disconnected",
            "reattaching",
            "expired",
        }

    def test_round_trip(self) -> None:
        for m in ConnectionState:
            assert ConnectionState(m.value) is m

    def test_values_are_strings(self) -> None:
        for state in ConnectionState:
            assert isinstance(state, str)
