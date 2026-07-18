"""Unit tests for the mem0 learning-layer store hook (CR-AUFG-03-10).

Tests that :class:`DismissedFindingService` forwards dismissals to a
:class:`ConsistencyFeedbackCollector` after the DB persist succeeds, and
that the forward is best-effort (RULE-11): mem0 failures never break the
DB dismiss, and ``feedback_memory=None`` disables the forward entirely.

These tests live alongside ``test_dismissed_service.py`` (which covers the
DB-persistence CRUD) — split out to keep both files focused (RULE-04).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from narrare.kb.consistency_contracts import (
    DismissedFindingsResponse,
    DismissFindingRequest,
)
from narrare.kb.dismissed_service import (
    DismissedFindingService,
    _build_dismissal_record,
    _parse_fingerprint,
)

if TYPE_CHECKING:
    from narrare_core.memory.consistency_models import ConsistencyDismissalRecord


# ---------------------------------------------------------------------------
# Fake repository (reused shape from test_dismissed_service.py)
# ---------------------------------------------------------------------------


class _FakeRepo:
    """Minimal in-memory repo matching DismissedFindingRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[tuple[UUID, str], str | None] = {}

    async def dismiss(
        self,
        novel_id: UUID,
        fingerprint: str,
        reason: str | None = None,
    ) -> None:
        self._store[(novel_id, fingerprint)] = reason

    async def list_dismissed(self, novel_id: UUID) -> list[str]:
        return [fp for (nid, fp) in self._store if nid == novel_id]

    async def undismiss(self, novel_id: UUID, fingerprint: str) -> bool:
        key = (novel_id, fingerprint)
        existed = key in self._store
        self._store.pop(key, None)
        return existed


# ---------------------------------------------------------------------------
# Tests: fingerprint parsing
# ---------------------------------------------------------------------------


class TestParseFingerprint:
    """Tests for the fingerprint → (description, entity_names) parser."""

    def test_parse_standard_fingerprint(self) -> None:
        """description::entity1,entity2 splits cleanly."""
        description, entities = _parse_fingerprint("Ages conflict::Alice,Bob")
        assert description == "Ages conflict"
        assert entities == ["Alice", "Bob"]

    def test_parse_without_separator_returns_all_as_description(self) -> None:
        """No '::' → whole string is the description, entities empty."""
        description, entities = _parse_fingerprint("just-a-description")
        assert description == "just-a-description"
        assert entities == []

    def test_parse_splits_on_first_separator_only(self) -> None:
        """Only the first '::' is the separator; later '::' stay in entities.

        The frontend fingerprint format is ``{description}::{entities}`` where
        entities are comma-joined. If a description itself contains ``::`` the
        partition-on-first-``::`` strategy cannot distinguish it — the tail
        bleeds into the entities string. This is an accepted format
        limitation (descriptions rarely contain ``::``); the test pins the
        actual behaviour so future refactors stay honest about it.
        """
        description, entities = _parse_fingerprint("weird::name::Alice,Bob")
        assert description == "weird"
        assert entities == ["name::Alice", "Bob"]

    def test_parse_empty_entities_after_separator(self) -> None:
        """'desc::' yields empty entity list, non-empty description."""
        description, entities = _parse_fingerprint("desc::")
        assert description == "desc"
        assert entities == []

    def test_parse_strips_empty_entity_tokens(self) -> None:
        """Trailing/empty entity tokens are dropped."""
        description, entities = _parse_fingerprint("d::Alice,,Bob,")
        assert description == "d"
        assert entities == ["Alice", "Bob"]


# ---------------------------------------------------------------------------
# Tests: record building
# ---------------------------------------------------------------------------


class TestBuildDismissalRecord:
    """Tests for _build_dismissal_record()."""

    def test_record_carries_parsed_description_and_entities(self) -> None:
        """The record's description + entity_names come from the fingerprint."""
        user_id = uuid4()
        project_id = uuid4()
        record = _build_dismissal_record(
            user_id=str(user_id),
            project_id=project_id,
            request=DismissFindingRequest(
                fingerprint="Eye colour mismatch::Anna,Bram",
                reason="Intentional.",
            ),
        )
        assert record.user_id == user_id
        assert record.project_id == project_id
        assert record.fingerprint == "Eye colour mismatch::Anna,Bram"
        assert record.finding_description == "Eye colour mismatch"
        assert record.entity_names == ["Anna", "Bram"]
        assert record.reason == "Intentional."

    def test_record_marks_category_and_severity_unknown(self) -> None:
        """Category/severity are unknown at dismiss time (fingerprint-only)."""
        record = _build_dismissal_record(
            user_id=str(uuid4()),
            project_id=uuid4(),
            request=DismissFindingRequest(fingerprint="x::y"),
        )
        assert record.category == "unknown"
        assert record.severity == "unknown"

    def test_record_user_id_must_be_valid_uuid_string(self) -> None:
        """A non-UUID user_id raises ValueError (auth should guarantee validity)."""
        with pytest.raises(ValueError):
            _build_dismissal_record(
                user_id="not-a-uuid",
                project_id=uuid4(),
                request=DismissFindingRequest(fingerprint="x::y"),
            )


# ---------------------------------------------------------------------------
# Tests: store hook integration in DismissedFindingService
# ---------------------------------------------------------------------------


class TestDismissStoreHook:
    """Tests for the mem0 forward inside dismiss_finding()."""

    async def test_dismiss_calls_record_dismissal_after_db_persist(
        self,
    ) -> None:
        """A successful DB dismiss triggers record_dismissal on the collector."""
        repo = _FakeRepo()
        feedback_memory = AsyncMock()
        service = DismissedFindingService(repo, feedback_memory=feedback_memory)
        novel_id = uuid4()
        user_id = uuid4()
        request = DismissFindingRequest(
            fingerprint="Eye colour mismatch::Anna",
            reason="False positive.",
        )

        result = await service.dismiss_finding(
            novel_id=novel_id, request=request, user_id=str(user_id)
        )

        assert isinstance(result, DismissedFindingsResponse)
        feedback_memory.record_dismissal.assert_awaited_once()
        # The forwarded record carries the parsed description + identity.
        call = feedback_memory.record_dismissal.call_args
        assert call.args[0] == str(user_id)  # method-level user_id
        assert call.args[1] == novel_id  # method-level project_id
        record: ConsistencyDismissalRecord = call.args[2]
        assert record.finding_description == "Eye colour mismatch"
        assert record.entity_names == ["Anna"]
        assert record.user_id == user_id
        assert record.project_id == novel_id

    async def test_dismiss_does_not_raise_when_record_dismissal_fails(
        self,
    ) -> None:
        """A mem0 failure must not break the DB dismiss (RULE-11)."""
        repo = _FakeRepo()
        feedback_memory = AsyncMock()
        feedback_memory.record_dismissal = AsyncMock(
            side_effect=RuntimeError("mem0 down"),
        )
        service = DismissedFindingService(repo, feedback_memory=feedback_memory)
        novel_id = uuid4()
        request = DismissFindingRequest(fingerprint="fp-1::Alice")

        # Must not raise — DB dismiss is the source of truth.
        result = await service.dismiss_finding(
            novel_id=novel_id, request=request, user_id=str(uuid4())
        )

        # DB dismiss still happened.
        assert "fp-1::Alice" in result.fingerprints
        feedback_memory.record_dismissal.assert_awaited_once()

    async def test_dismiss_with_feedback_memory_none_skips_mem0(self) -> None:
        """feedback_memory=None → no mem0 call, DB dismiss still works."""
        repo = _FakeRepo()
        service = DismissedFindingService(repo, feedback_memory=None)
        novel_id = uuid4()

        result = await service.dismiss_finding(
            novel_id=novel_id,
            request=DismissFindingRequest(fingerprint="fp-1::Alice"),
            user_id=str(uuid4()),
        )

        assert "fp-1::Alice" in result.fingerprints

    async def test_dismiss_with_user_id_none_skips_mem0_forward(self) -> None:
        """user_id=None → no mem0 call (no identity to scope by)."""
        repo = _FakeRepo()
        feedback_memory = AsyncMock()
        service = DismissedFindingService(repo, feedback_memory=feedback_memory)

        await service.dismiss_finding(
            novel_id=uuid4(),
            request=DismissFindingRequest(fingerprint="fp-1::Alice"),
            user_id=None,
        )

        feedback_memory.record_dismissal.assert_not_awaited()

    async def test_dismiss_with_invalid_user_id_still_persists_to_db(
        self,
    ) -> None:
        """A non-UUID user_id is caught (RULE-11); DB dismiss still succeeds."""
        repo = _FakeRepo()
        feedback_memory = AsyncMock()
        service = DismissedFindingService(repo, feedback_memory=feedback_memory)
        novel_id = uuid4()

        result = await service.dismiss_finding(
            novel_id=novel_id,
            request=DismissFindingRequest(fingerprint="fp-1::Alice"),
            user_id="not-a-uuid",
        )

        # DB dismiss succeeded; mem0 forward was attempted but swallowed.
        assert "fp-1::Alice" in result.fingerprints
        feedback_memory.record_dismissal.assert_not_awaited()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
