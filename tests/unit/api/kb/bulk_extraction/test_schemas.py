"""Wire-model invariants for the bulk extraction job (F2, ADR-092)."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError as PydanticValidationError

from narrare.kb.bulk_extraction.contracts import BULK_EXTRACT_MAX_CHAPTERS, BULK_JOB_TTL
from narrare.kb.bulk_extraction.schemas import (
    BulkChapterState,
    BulkChapterStatusView,
    BulkExtractionResultChapter,
    BulkExtractionStartRequest,
    BulkExtractionStatusView,
    BulkJobStatus,
)
from narrare_core.agents.extraction_types import ExtractionOutput

_NOT_DONE_STATES = ["pending", "running", "failed"]


def _chapter_payload(**overrides: object) -> dict[str, object]:
    """Minimal valid chapter row shared by status/result invariants tests."""
    payload: dict[str, object] = {
        "chapter_id": str(uuid.uuid4()),
        "title": "T",
        "position": 0,
        "state": "pending",
    }
    payload.update(overrides)
    return payload


class TestContracts:
    def test_protocol_constants_pinned(self) -> None:
        assert BULK_EXTRACT_MAX_CHAPTERS == 200
        assert BULK_JOB_TTL.total_seconds() == 24 * 3600


class TestEnums:
    def test_chapter_states_are_the_normative_set(self) -> None:
        assert [s.value for s in BulkChapterState] == ["pending", "running", "done", "failed"]

    def test_job_statuses_are_the_normative_set(self) -> None:
        assert [s.value for s in BulkJobStatus] == [
            "pending",
            "running",
            "cancelling",
            "completed",
            "cancelled",
            "failed",
        ]


class TestStartRequest:
    def test_rejects_unknown_field(self) -> None:
        with pytest.raises(PydanticValidationError):
            BulkExtractionStartRequest.model_validate(
                {"chapter_ids": [uuid.uuid4()], "scope": "novel"}
            )

    def test_rejects_empty_and_over_cap(self) -> None:
        with pytest.raises(PydanticValidationError):
            BulkExtractionStartRequest.model_validate({"chapter_ids": []})
        with pytest.raises(PydanticValidationError):
            BulkExtractionStartRequest.model_validate(
                {"chapter_ids": [uuid.uuid4()] * (BULK_EXTRACT_MAX_CHAPTERS + 1)}
            )


class TestStatusView:
    def test_item_count_defaults_to_none(self) -> None:
        view = BulkExtractionStatusView.model_validate(
            {
                "job_id": "j",
                "novel_id": str(uuid.uuid4()),
                "status": "running",
                "created_at": "2026-10-03T10:00:00Z",
                "updated_at": "2026-10-03T10:00:00Z",
                "totals": {"total": 1, "done": 0, "failed": 0, "remaining": 1},
                "chapters": [
                    {
                        "chapter_id": str(uuid.uuid4()),
                        "title": "T",
                        "position": 0,
                        "state": "pending",
                    }
                ],
            }
        )
        assert view.chapters[0].item_count is None


class TestChapterStatusViewInvariants:
    def test_error_field_defaults_to_none(self) -> None:
        view = BulkChapterStatusView.model_validate(_chapter_payload())
        assert view.error is None

    def test_error_field_round_trips_failure_reason(self) -> None:
        view = BulkChapterStatusView.model_validate(
            _chapter_payload(state="failed", error="agent call timed out")
        )
        assert view.error == "agent call timed out"

    def test_item_count_set_on_done(self) -> None:
        view = BulkChapterStatusView.model_validate(_chapter_payload(state="done", item_count=9))
        assert view.item_count == 9

    def test_done_without_item_count_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            BulkChapterStatusView.model_validate(_chapter_payload(state="done"))

    @pytest.mark.parametrize("state", _NOT_DONE_STATES)
    def test_item_count_on_not_done_rejected(self, state: str) -> None:
        with pytest.raises(PydanticValidationError):
            BulkChapterStatusView.model_validate(_chapter_payload(state=state, item_count=3))


class TestResultChapterInvariants:
    def test_output_set_on_done(self) -> None:
        row = BulkExtractionResultChapter.model_validate(
            _chapter_payload(state="done", output=ExtractionOutput())
        )
        assert row.output is not None

    def test_not_done_defaults_to_output_none(self) -> None:
        row = BulkExtractionResultChapter.model_validate(_chapter_payload(state="failed"))
        assert row.output is None

    def test_done_without_output_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            BulkExtractionResultChapter.model_validate(_chapter_payload(state="done"))

    @pytest.mark.parametrize("state", _NOT_DONE_STATES)
    def test_output_on_not_done_rejected(self, state: str) -> None:
        with pytest.raises(PydanticValidationError):
            BulkExtractionResultChapter.model_validate(
                _chapter_payload(state=state, output=ExtractionOutput())
            )
