"""Unit tests for CoAuthorApplyService.record_feedback — mocked dependencies.

Tests the ``record_feedback`` method of
:class:`CoAuthorApplyService` without touching the database.
All dependencies are mocked (DI pattern, RULE-07).

See ADR-023 and ADR-023-Restimplementierung Phase 1 for context.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.writing.coauthor_apply_service import CoAuthorApplyService
from narrare.writing.schemas_coauthor import ChangeFeedback
from narrare_core.shared.errors import NotFoundError
from tests.unit.api.writing._test_coauthor_helpers import (
    _make_generation_request,
)

# ---------------------------------------------------------------------------
# record_feedback
# ---------------------------------------------------------------------------


class TestRecordFeedback:
    """Tests for CoAuthorApplyService.record_feedback()."""

    @pytest.mark.asyncio
    async def test_record_feedback_happy_path(self) -> None:
        """Feedback is recorded successfully for each feedback item."""
        gen_req = _make_generation_request()
        repo = MagicMock(spec=["get_by_id"])
        repo.get_by_id = AsyncMock(return_value=gen_req)

        chapter_repo = MagicMock(spec=["get_by_id"])
        feedback_service = MagicMock(spec=["record"])
        feedback_service.record = AsyncMock()

        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
            feedback_service=feedback_service,  # type: ignore[arg-type]
        )

        feedback_items = [
            ChangeFeedback(
                change_id="ch_1",
                action="accept",
                original="old text",
                revised="new text",
            ),
            ChangeFeedback(
                change_id="ch_2",
                action="reject",
                original="bad text",
                revised="",
            ),
        ]

        await service.record_feedback(
            request_id=gen_req.id,
            feedback=feedback_items,
        )

        # Two feedback events should be recorded
        assert feedback_service.record.call_count == 2

    @pytest.mark.asyncio
    async def test_record_feedback_request_not_found(self) -> None:
        """When generation request is not found, NotFoundError is raised."""
        repo = MagicMock(spec=["get_by_id"])
        repo.get_by_id = AsyncMock(return_value=None)

        chapter_repo = MagicMock(spec=["get_by_id"])
        feedback_service = MagicMock(spec=["record"])
        feedback_service.record = AsyncMock()

        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
            feedback_service=feedback_service,  # type: ignore[arg-type]
        )

        with pytest.raises(NotFoundError, match="GenerationRequest"):
            await service.record_feedback(
                request_id=uuid4(),
                feedback=[],
            )

        feedback_service.record.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_feedback_no_feedback_service_noop(self) -> None:
        """When no FeedbackCollector configured, method silently no-ops."""
        gen_req = _make_generation_request()
        repo = MagicMock(spec=["get_by_id"])
        repo.get_by_id = AsyncMock(return_value=gen_req)

        chapter_repo = MagicMock(spec=["get_by_id"])

        # No feedback service
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
            feedback_service=None,
        )

        # Should not raise and should call record_batch_feedback
        # which will no-op due to None feedback service
        await service.record_feedback(
            request_id=gen_req.id,
            feedback=[
                ChangeFeedback(
                    change_id="ch_1",
                    action="accepted",
                    original="old",
                    revised="new",
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_record_feedback_empty_list(self) -> None:
        """Empty feedback list is handled gracefully."""
        gen_req = _make_generation_request()
        repo = MagicMock(spec=["get_by_id"])
        repo.get_by_id = AsyncMock(return_value=gen_req)

        chapter_repo = MagicMock(spec=["get_by_id"])
        feedback_service = MagicMock(spec=["record"])
        feedback_service.record = AsyncMock()

        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
            feedback_service=feedback_service,  # type: ignore[arg-type]
        )

        await service.record_feedback(
            request_id=gen_req.id,
            feedback=[],
        )

        # No feedback events should be recorded for an empty list
        feedback_service.record.assert_not_called()
