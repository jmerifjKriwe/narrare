"""Wire-model invariants for the bulk extraction job (F2, ADR-092)."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError as PydanticValidationError

from narrare.kb.bulk_extraction.contracts import BULK_EXTRACT_MAX_CHAPTERS, BULK_JOB_TTL
from narrare.kb.bulk_extraction.schemas import (
    BulkChapterState,
    BulkExtractionStartRequest,
    BulkExtractionStatusView,
    BulkJobStatus,
)


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
