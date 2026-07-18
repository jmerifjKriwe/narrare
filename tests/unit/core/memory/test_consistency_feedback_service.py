"""Tests for memory/consistency_feedback_service.py — ConsistencyFeedbackService.

Service-behavior tests for the cross-run consistency-dismissal learning layer
(CR-AUFG-03-10): recording dismissals to mem0 and the store-path contract.
Retrieve-path (find_similar_dismissals) tests live in
``test_consistency_feedback_find.py`` — split to respect RULE-04.

Privacy (ADR-045 Decision 8, RULE-22): only the finding *description* (a
structural analysis output) and linkage metadata are recorded — never raw
draft prose. Mirrors ``test_feedback_service.py`` / ``test_session_memory_service.py``.

See: ADR-045 Decision 8, CONSTRAINTS.md RULE-08/RULE-11/RULE-22.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from narrare_core.memory._null_client import NullMemoryClient
from narrare_core.memory.consistency_feedback_service import (
    ConsistencyFeedbackService,
)
from narrare_core.memory.consistency_models import ConsistencyDismissalRecord

_DISMISSAL_TYPE = "consistency_dismissal"


def _make_record(
    *,
    finding_description: str = "Aria's eye colour changes from blue to green.",
    entity_names: list[str] | None = None,
    category: str = "entry_internal",
    severity: str = "major",
    reason: str | None = None,
    project_id: UUID | None = None,
    user_id: UUID | None = None,
) -> ConsistencyDismissalRecord:
    """Build a ConsistencyDismissalRecord with sensible defaults."""
    return ConsistencyDismissalRecord(
        user_id=user_id if user_id is not None else uuid4(),
        project_id=project_id if project_id is not None else uuid4(),
        fingerprint=f"{finding_description}::{'|'.join(entity_names or [])}",
        finding_description=finding_description,
        entity_names=entity_names if entity_names is not None else ["Aria"],
        category=category,
        severity=severity,
        reason=reason,
    )


class TestRecordDismissal:
    """Tests for ConsistencyFeedbackService.record_dismissal()."""

    async def test_record_calls_mem0_add_with_correct_message(self) -> None:
        """record_dismissal() forwards a natural-language message to mem0.add()."""
        mem0 = AsyncMock()
        service = ConsistencyFeedbackService(mem0_client=mem0)
        record = _make_record(
            finding_description="Eye colour mismatch.",
            entity_names=["Aria", "Bram"],
            category="entry_internal",
        )

        await service.record_dismissal(record.user_id, record.project_id, record)

        mem0.add.assert_awaited_once()
        call_kwargs = mem0.add.call_args[1]
        assert call_kwargs["messages"] == (
            "Consistency finding dismissed as false positive: Eye colour mismatch. "
            "(entities: Aria, Bram, category: entry_internal)"
        )

    async def test_record_scopes_mem0_by_record_identity(self) -> None:
        """record_dismissal() scopes mem0 via the record's user_id/project_id.

        Mirrors FeedbackService which scopes via the event's identity fields.
        """
        mem0 = AsyncMock()
        service = ConsistencyFeedbackService(mem0_client=mem0)
        record = _make_record()

        await service.record_dismissal(record.user_id, record.project_id, record)

        call_kwargs = mem0.add.call_args[1]
        assert call_kwargs["user_id"] == str(record.user_id)
        assert call_kwargs["agent_id"] == str(record.project_id)

    async def test_record_forwards_metadata_to_mem0(self) -> None:
        """record_dismissal() attaches the full linkage + payload metadata."""
        mem0 = AsyncMock()
        service = ConsistencyFeedbackService(mem0_client=mem0)
        record = _make_record(reason="Not a real inconsistency.")

        await service.record_dismissal(record.user_id, record.project_id, record)

        call_kwargs = mem0.add.call_args[1]
        assert call_kwargs["metadata"] == {
            "type": _DISMISSAL_TYPE,
            "novel_id": str(record.project_id),
            "user_id": str(record.user_id),
            "fingerprint": record.fingerprint,
            "category": record.category,
            "severity": record.severity,
            "finding_description": record.finding_description,
            "reason": record.reason,
        }

    async def test_record_message_omits_entities_when_empty(self) -> None:
        """With no entity names, the message drops the ``entities:`` clause."""
        mem0 = AsyncMock()
        service = ConsistencyFeedbackService(mem0_client=mem0)
        record = _make_record(entity_names=[])

        await service.record_dismissal(record.user_id, record.project_id, record)

        message = mem0.add.call_args[1]["messages"]
        assert "entities:" not in message
        assert message == (
            "Consistency finding dismissed as false positive: "
            "Aria's eye colour changes from blue to green. (category: entry_internal)"
        )

    async def test_record_appends_reason_when_present(self) -> None:
        """A user-provided reason is surfaced in the memory message."""
        mem0 = AsyncMock()
        service = ConsistencyFeedbackService(mem0_client=mem0)
        record = _make_record(reason="Already explained in ch.3.")

        await service.record_dismissal(record.user_id, record.project_id, record)

        message = mem0.add.call_args[1]["messages"]
        assert "— reason: Already explained in ch.3." in message

    async def test_record_does_not_raise_on_mem0_failure(self) -> None:
        """record_dismissal() must not raise when mem0 fails (graceful degradation)."""
        mem0 = AsyncMock()
        mem0.add.side_effect = RuntimeError("mem0 down")
        service = ConsistencyFeedbackService(mem0_client=mem0)
        record = _make_record()

        # Must not raise — mem0 failure is a warning, not an error.
        await service.record_dismissal(record.user_id, record.project_id, record)
        mem0.add.assert_awaited_once()

    async def test_record_with_null_memory_client_does_not_raise(self) -> None:
        """record_dismissal() with NullMemoryClient succeeds silently."""
        null_client = NullMemoryClient()
        service = ConsistencyFeedbackService(mem0_client=null_client)
        record = _make_record()

        await service.record_dismissal(record.user_id, record.project_id, record)


class TestFindGracefulDegradation:
    """RULE-11 graceful-degradation tests for find_similar_dismissals().

    The retrieve path must never crash the consistency check when mem0 is
    unavailable: it logs a warning and returns ``[]``. (Mapping/filtering
    logic tests live in ``test_consistency_feedback_find.py``.)
    """

    async def test_find_returns_empty_when_no_results(self) -> None:
        """find_similar_dismissals() returns [] when mem0 has no results."""
        mem0 = AsyncMock()
        mem0.search.return_value = {"results": []}
        service = ConsistencyFeedbackService(mem0_client=mem0)

        matches = await service.find_similar_dismissals(uuid4(), uuid4(), finding_description="q")
        assert matches == []

    async def test_find_returns_empty_on_mem0_failure(self) -> None:
        """find_similar_dismissals() returns [] when mem0 raises (graceful)."""
        mem0 = AsyncMock()
        mem0.search.side_effect = RuntimeError("pgvector down")
        service = ConsistencyFeedbackService(mem0_client=mem0)

        matches = await service.find_similar_dismissals(uuid4(), uuid4(), finding_description="q")
        assert matches == []

    async def test_find_with_null_memory_client_returns_empty(self) -> None:
        """find_similar_dismissals() with NullMemoryClient returns []."""
        null_client = NullMemoryClient()
        service = ConsistencyFeedbackService(mem0_client=null_client)

        matches = await service.find_similar_dismissals(uuid4(), uuid4(), finding_description="q")
        assert matches == []
