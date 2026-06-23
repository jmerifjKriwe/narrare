"""Tests for WritingSessionControlProtocol (ADR-052 Phase 1 contract).

Verifies the runtime-checkable Protocol is satisfied by a class that
implements both ``stop_generation`` and ``reattach_session``, and NOT by
a class missing either method.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.writing.contracts import (
    ReattachOutcomeKind,
    StopGenerationStatus,
    WritingSessionControlProtocol,
)

if TYPE_CHECKING:
    from uuid import UUID


class _FullControl:
    """Satisfies the full WritingSessionControlProtocol."""

    async def stop_generation(self, session_id: UUID, invocation_id: UUID) -> dict[str, object]:
        return {}

    async def reattach_session(
        self,
        session_id: UUID,
        user_id: UUID,
        project_id: UUID,
    ) -> dict[str, object]:
        return {}


class _MissingReattach:
    """Missing reattach_session — should NOT satisfy."""

    async def stop_generation(self, session_id: UUID, invocation_id: UUID) -> dict[str, object]:
        return {}


class TestWritingSessionControlProtocol:
    """Protocol structural checks."""

    def test_full_control_satisfies_protocol(self) -> None:
        assert isinstance(_FullControl(), WritingSessionControlProtocol)

    def test_missing_reattach_does_not_satisfy(self) -> None:
        assert not isinstance(_MissingReattach(), WritingSessionControlProtocol)


class TestStatusVocabularies:
    """StopGenerationStatus and ReattachOutcomeKind constants."""

    def test_stop_generation_status_values(self) -> None:
        assert StopGenerationStatus.STOPPED == "stopped"
        assert StopGenerationStatus.NO_ACTIVE_TURN == "no_active_turn"

    def test_reattach_outcome_kind_values(self) -> None:
        assert ReattachOutcomeKind.RECOVERED == "recovered"
        assert ReattachOutcomeKind.NOT_FOUND == "not_found"
        assert ReattachOutcomeKind.EXPIRED == "expired"
        assert ReattachOutcomeKind.OWNERSHIP_MISMATCH == "ownership_mismatch"
