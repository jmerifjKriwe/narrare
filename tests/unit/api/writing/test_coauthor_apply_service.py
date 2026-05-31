"""Unit tests for CoAuthorApplyService.apply_changes — mocked dependencies.

Tests the ``apply_changes`` method of
:class:`CoAuthorApplyService` without touching the database.
All dependencies are mocked (DI pattern, RULE-07).

See ADR-023 and ADR-023-Restimplementierung Phase 1 for context.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.writing.coauthor_apply_service import CoAuthorApplyService
from narrare.writing.schemas_coauthor import (
    ApplyChangesRequest,
    TextChange,
)
from narrare_core.memory.models import FeedbackAction, FeedbackEvent
from narrare_core.shared.errors import NotFoundError
from tests.unit.api.writing._test_coauthor_helpers import (
    _apply_request,
    _make_chapter,
    _make_generation_request,
)

# ---------------------------------------------------------------------------
# apply_changes
# ---------------------------------------------------------------------------


class TestApplyChanges:
    """Tests for CoAuthorApplyService.apply_changes()."""

    @pytest.mark.asyncio
    async def test_apply_changes_happy_path(self) -> None:
        """Accepted changes are applied and chapter content is updated."""
        chapter = _make_chapter(content="The original chapter content. It was quite good.")
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)

        async def _update_content(c: Any, content: str, wc: int) -> Any:
            c.content = content
            c.word_count = wc
            return c

        chapter_repo.update_content = AsyncMock(side_effect=_update_content)
        repo = MagicMock(spec=["get_by_id"])
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
        )

        result = await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(uuid4()),
            request=_apply_request(),
        )

        assert result is not None
        assert result.content is not None
        assert "excellent" in result.content
        assert "quite good" not in result.content
        chapter_repo.get_by_id.assert_called_once_with(chapter.id, chapter.novel_id)
        chapter_repo.update_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_changes_passes_reconstructed_content_to_repo(self) -> None:
        """Verify the reconstructed text is passed to update_content."""
        chapter = _make_chapter(content="The cat sat on the mat.")
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)
        repo = MagicMock(spec=["get_by_id"])
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
        )

        await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(uuid4()),
            request=ApplyChangesRequest(
                request_id=uuid4(),
                original="The cat sat on the mat.",
                accepted=[
                    TextChange(original_text="cat", revised_text="dog"),
                    TextChange(original_text="mat", revised_text="rug"),
                ],
                rejected=[],
            ),
        )

        call_args = chapter_repo.update_content.call_args
        assert call_args is not None
        content_arg = call_args[0][1]
        assert content_arg == "The dog sat on the rug."

    @pytest.mark.asyncio
    async def test_apply_changes_word_count_computed(self) -> None:
        """Word count is computed from the reconstructed text."""
        chapter = _make_chapter(content="A B C.")
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)
        repo = MagicMock(spec=["get_by_id"])
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
        )

        await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(uuid4()),
            request=ApplyChangesRequest(
                request_id=uuid4(),
                original="A B C.",
                accepted=[
                    TextChange(original_text="A B C", revised_text="D E F G"),
                ],
                rejected=[],
            ),
        )

        call_args = chapter_repo.update_content.call_args
        assert call_args is not None
        word_count_arg = call_args[0][2]
        assert word_count_arg == 4

    @pytest.mark.asyncio
    async def test_apply_changes_chapter_not_found_raises_not_found(self) -> None:
        """When chapter does not exist, NotFoundError is raised."""
        chapter_repo = MagicMock(spec=["get_by_id"])
        chapter_repo.get_by_id = AsyncMock(return_value=None)
        repo = MagicMock(spec=["get_by_id"])
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
        )

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.apply_changes(
                chapter_id=uuid4(),
                novel_id=uuid4(),
                user_id=str(uuid4()),
                request=_apply_request(),
            )

    @pytest.mark.asyncio
    async def test_apply_changes_with_rejected_records_feedback(self) -> None:
        """Rejected changes should trigger feedback recording."""
        chapter = _make_chapter()
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)

        gen_req = _make_generation_request()
        repo = MagicMock(spec=["get_by_id"])
        repo.get_by_id = AsyncMock(return_value=gen_req)

        feedback_service = MagicMock(spec=["record"])
        feedback_service.record = AsyncMock()

        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
            feedback_service=feedback_service,  # type: ignore[arg-type]
        )

        await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(uuid4()),
            request=_apply_request(with_rejected=True),
        )

        assert feedback_service.record.call_count == 1
        call_args = feedback_service.record.call_args
        assert call_args is not None
        event = call_args[0][0]
        assert isinstance(event, FeedbackEvent)
        assert event.action == FeedbackAction.REJECT

    @pytest.mark.asyncio
    async def test_apply_changes_with_rejected_but_no_feedback_service(self) -> None:
        """Rejected changes should no-op when no FeedbackCollector."""
        chapter = _make_chapter()
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)
        repo = MagicMock(spec=["get_by_id"])
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
            feedback_service=None,
        )

        result = await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(uuid4()),
            request=_apply_request(with_rejected=True),
        )

        assert result is not None
        chapter_repo.update_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_changes_with_missing_gen_request_skips_feedback(self) -> None:
        """When generation request not found, rejected feedback is skipped."""
        chapter = _make_chapter()
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)

        repo = MagicMock(spec=["get_by_id"])
        repo.get_by_id = AsyncMock(return_value=None)

        feedback_service = MagicMock(spec=["record"])
        feedback_service.record = AsyncMock()

        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
            feedback_service=feedback_service,  # type: ignore[arg-type]
        )

        result = await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(uuid4()),
            request=_apply_request(with_rejected=True),
        )

        assert result is not None
        feedback_service.record.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_changes_no_rejected_changes_no_feedback(self) -> None:
        """When no rejected changes, no feedback is recorded."""
        chapter = _make_chapter()
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)
        repo = MagicMock(spec=["get_by_id"])
        feedback_service = MagicMock(spec=["record"])
        feedback_service.record = AsyncMock()
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
            feedback_service=feedback_service,  # type: ignore[arg-type]
        )

        await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(uuid4()),
            request=_apply_request(with_rejected=False),
        )

        feedback_service.record.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_changes_returns_updated_chapter(self) -> None:
        """The return value is the chapter returned by update_content."""
        expected_chapter = _make_chapter()
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=_make_chapter())
        chapter_repo.update_content = AsyncMock(return_value=expected_chapter)
        repo = MagicMock(spec=["get_by_id"])
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
        )

        result = await service.apply_changes(
            chapter_id=expected_chapter.id,
            novel_id=expected_chapter.novel_id,
            user_id=str(uuid4()),
            request=_apply_request(),
        )

        assert result is expected_chapter
