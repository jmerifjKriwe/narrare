"""Unit tests for CoAuthorApplyService.apply_changes — mocked dependencies.

Tests the ``apply_changes`` method of
:class:`CoAuthorApplyService` without touching the database.
All dependencies are mocked (DI pattern, RULE-07).

Since the IDOR remediation (plan S2), ``apply_changes`` first validates the
generation request against the caller (Pattern A) and requires the row to
reference the addressed chapter and novel.  These tests therefore always
seed an OWNED request row matching (chapter_id, novel_id); the foreign and
unknown matrices live in ``test_coauthor_apply_ownership.py``.

See ADR-023 and ADR-023-Restimplementierung Phase 1 for context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

if TYPE_CHECKING:
    from narrare.chapters.models import Chapter
    from narrare.chapters.repository import ChapterRepository
    from narrare.writing.models import GenerationRequest
    from narrare.writing.repository import GenerationRepository
    from narrare_core.memory.protocols import FeedbackCollector

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
# Helpers
# ---------------------------------------------------------------------------


def _owned_request(chapter: Any, user_id: Any) -> tuple[MagicMock, Any]:
    """Repo mock resolving to a request row owned by ``user_id`` for
    ``chapter`` — the pre-gate state every happy-path test needs."""
    gen_req = _make_generation_request(
        chapter_id=chapter.id,
        novel_id=chapter.novel_id,
        user_id=user_id,
    )
    repo = MagicMock(spec=["get_by_id"])
    repo.get_by_id = AsyncMock(return_value=gen_req)
    return repo, gen_req


# ---------------------------------------------------------------------------
# apply_changes
# ---------------------------------------------------------------------------


class TestApplyChanges:
    """Tests for CoAuthorApplyService.apply_changes()."""

    @pytest.mark.asyncio
    async def test_apply_changes_happy_path(self) -> None:
        """Accepted changes are applied and chapter content is updated."""
        user = uuid4()
        chapter = _make_chapter(content="The original chapter content. It was quite good.")
        repo, gen_req = _owned_request(chapter, user)
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)

        async def _update_content(c: Any, content: str, wc: int) -> Any:
            c.content = content
            c.word_count = wc
            return c

        chapter_repo.update_content = AsyncMock(side_effect=_update_content)
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
        )

        result = await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(user),
            request=_apply_request(request_id=gen_req.id),
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
        user = uuid4()
        chapter = _make_chapter(content="The cat sat on the mat.")
        repo, gen_req = _owned_request(chapter, user)
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
        )

        await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(user),
            request=ApplyChangesRequest(
                request_id=gen_req.id,
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
        user = uuid4()
        chapter = _make_chapter(content="A B C.")
        repo, gen_req = _owned_request(chapter, user)
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
        )

        await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(user),
            request=ApplyChangesRequest(
                request_id=gen_req.id,
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
        user = uuid4()
        chapter_id, novel_id = uuid4(), uuid4()
        gen_req = _make_generation_request(chapter_id=chapter_id, novel_id=novel_id, user_id=user)
        repo = MagicMock(spec=["get_by_id"])
        repo.get_by_id = AsyncMock(return_value=gen_req)
        chapter_repo = MagicMock(spec=["get_by_id"])
        chapter_repo.get_by_id = AsyncMock(return_value=None)
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
        )

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.apply_changes(
                chapter_id=chapter_id,
                novel_id=novel_id,
                user_id=str(user),
                request=_apply_request(request_id=gen_req.id),
            )

    @pytest.mark.asyncio
    async def test_apply_changes_with_rejected_records_feedback(self) -> None:
        """Rejected changes should trigger feedback recording."""
        user = uuid4()
        chapter = _make_chapter()
        repo, gen_req = _owned_request(chapter, user)
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)

        feedback_service = MagicMock(spec=["record"])
        feedback_service.record = AsyncMock()

        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            feedback_service=cast("FeedbackCollector", feedback_service),
        )

        await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(user),
            request=_apply_request(request_id=gen_req.id, with_rejected=True),
        )

        assert feedback_service.record.call_count == 1
        call_args = feedback_service.record.call_args
        assert call_args is not None
        event = call_args[0][0]
        assert isinstance(event, FeedbackEvent)
        assert event.action == FeedbackAction.REJECT
        # Feedback is stamped with the caller's (owner's) user id.
        assert event.user_id == user

    @pytest.mark.asyncio
    async def test_apply_changes_with_rejected_but_no_feedback_service(self) -> None:
        """Rejected changes should no-op when no FeedbackCollector."""
        user = uuid4()
        chapter = _make_chapter()
        repo, gen_req = _owned_request(chapter, user)
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            feedback_service=None,
        )

        result = await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(user),
            request=_apply_request(request_id=gen_req.id, with_rejected=True),
        )

        assert result is not None
        chapter_repo.update_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_changes_with_unknown_request_raises_before_write(self) -> None:
        """Unknown request id → NotFoundError BEFORE any chapter write.

        Before the S2 fix, a missing request row merely skipped the
        rejected-feedback while still applying the write — the write must
        be bound to a caller-owned request row (regression guard).
        """
        chapter = _make_chapter()
        repo = MagicMock(spec=["get_by_id"])
        repo.get_by_id = AsyncMock(return_value=None)

        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)

        feedback_service = MagicMock(spec=["record"])
        feedback_service.record = AsyncMock()

        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            feedback_service=cast("FeedbackCollector", feedback_service),
        )

        with pytest.raises(NotFoundError, match="Generation request"):
            await service.apply_changes(
                chapter_id=chapter.id,
                novel_id=chapter.novel_id,
                user_id=str(uuid4()),
                request=_apply_request(with_rejected=True),
            )

        chapter_repo.get_by_id.assert_not_called()
        chapter_repo.update_content.assert_not_called()
        feedback_service.record.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_changes_no_rejected_changes_no_feedback(self) -> None:
        """When no rejected changes, no feedback is recorded."""
        user = uuid4()
        chapter = _make_chapter()
        repo, gen_req = _owned_request(chapter, user)
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)
        feedback_service = MagicMock(spec=["record"])
        feedback_service.record = AsyncMock()
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            feedback_service=cast("FeedbackCollector", feedback_service),
        )

        await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(user),
            request=_apply_request(request_id=gen_req.id, with_rejected=False),
        )

        feedback_service.record.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_changes_returns_updated_chapter(self) -> None:
        """The return value is the chapter returned by update_content."""
        user = uuid4()
        expected_chapter: Chapter = _make_chapter()
        repo, gen_req = _owned_request(expected_chapter, user)
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=_make_chapter())
        chapter_repo.update_content = AsyncMock(return_value=expected_chapter)
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
        )

        result: Chapter | None = await service.apply_changes(
            chapter_id=expected_chapter.id,
            novel_id=expected_chapter.novel_id,
            user_id=str(user),
            request=_apply_request(request_id=gen_req.id),
        )

        assert result is expected_chapter

    @pytest.mark.asyncio
    async def test_apply_changes_reuses_validated_row_for_feedback(self) -> None:
        """The gate's validated row is reused — no second repo lookup."""
        user = uuid4()
        chapter = _make_chapter()
        repo, gen_req = _owned_request(chapter, user)
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
        )

        await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(user),
            request=_apply_request(request_id=gen_req.id, with_rejected=True),
        )

        repo.get_by_id.assert_called_once_with(gen_req.id)

    @pytest.mark.asyncio
    async def test_apply_changes_owned_request_wrong_chapter_raises(self) -> None:
        """An owned request row pointing at another chapter must not unlock
        the addressed chapter (cross-chapter write guard)."""
        user = uuid4()
        chapter = _make_chapter()
        gen_req: GenerationRequest = _make_generation_request(
            chapter_id=uuid4(),  # different chapter than addressed below
            novel_id=chapter.novel_id,
            user_id=user,
        )
        repo = MagicMock(spec=["get_by_id"])
        repo.get_by_id = AsyncMock(return_value=gen_req)
        chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
        chapter_repo.get_by_id = AsyncMock(return_value=chapter)
        chapter_repo.update_content = AsyncMock(return_value=chapter)
        service: CoAuthorApplyService = CoAuthorApplyService(
            repo=cast("GenerationRepository", repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
        )

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.apply_changes(
                chapter_id=chapter.id,
                novel_id=chapter.novel_id,
                user_id=str(user),
                request=_apply_request(request_id=gen_req.id),
            )

        chapter_repo.get_by_id.assert_not_called()
        chapter_repo.update_content.assert_not_called()
