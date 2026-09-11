"""Unit tests for CoAuthorApplyService.record_feedback — mocked dependencies.

Tests the ``record_feedback`` method of
:class:`CoAuthorApplyService` without touching the database.
All dependencies are mocked (DI pattern, RULE-07).

Since the IDOR remediation (plan S2), ``record_feedback`` resolves the
generation request caller-scoped (Pattern A) — these tests seed an OWNED
row and pass its user as the caller; the foreign and unknown matrices
live in ``test_coauthor_apply_ownership.py``.

See ADR-023 and ADR-023-Restimplementierung Phase 1 for context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.writing.coauthor_apply_service import CoAuthorApplyService
from narrare.writing.schemas_coauthor import ChangeFeedback
from narrare_core.shared.errors import NotFoundError
from tests.unit.api.writing._test_coauthor_helpers import (
    _make_generation_request,
)

if TYPE_CHECKING:
    from narrare.chapters.repository import ChapterRepository
    from narrare.writing.repository import GenerationRepository
    from narrare_core.memory.protocols import FeedbackCollector

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
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            feedback_service=cast("FeedbackCollector", feedback_service),
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
            user_id=str(gen_req.user_id),
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
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            feedback_service=cast("FeedbackCollector", feedback_service),
        )

        with pytest.raises(NotFoundError, match="Generation request"):
            await service.record_feedback(
                request_id=uuid4(),
                feedback=[],
                user_id=str(uuid4()),
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
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
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
            user_id=str(gen_req.user_id),
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
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            feedback_service=cast("FeedbackCollector", feedback_service),
        )

        await service.record_feedback(
            request_id=gen_req.id,
            feedback=[],
            user_id=str(gen_req.user_id),
        )

        # No feedback events should be recorded for an empty list
        feedback_service.record.assert_not_called()
