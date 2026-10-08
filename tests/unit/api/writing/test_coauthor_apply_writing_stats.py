"""Unit tests — CoAuthorApplyService x WritingStatsRecorder (STATS-001 E3b).

Mirrors ``tests/unit/api/chapters/test_chapter_writing_stats*.py`` (E3a):
``apply_changes`` emits exactly ONE signed word-count delta per successful
apply, with full attribution (user/novel/chapter). The recorded user id is
the gate-validated generation-request owner — the UUID on the row the
Pattern-A gate proved belongs to the caller, never a re-parse of the raw
caller string. Pinned here: negative (shrink), positive (growth), zero
(identical word count — the CALL is pinned, not the skip; skipping is the
recorder's internal job), cross-caller attribution isolation, and the
never-raises posture via the REAL ``SqlWritingStatsRecorder`` behind an
exploding session factory (a raising fake would contradict the contract —
call sites must not add try/except).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.analytics.writing_stats_recorder import SqlWritingStatsRecorder
from narrare.writing.coauthor_apply_service import CoAuthorApplyService
from narrare.writing.schemas_coauthor import ApplyChangesRequest, TextChange
from tests.fakes import FakeWritingStatsRecorder
from tests.unit.api.writing._test_coauthor_helpers import (
    _apply_request,
    _make_chapter,
    _make_generation_request,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from narrare.chapters.repository import ChapterRepository
    from narrare.writing.repository import GenerationRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_service(
    chapter: Any,
    user_id: Any,
    recorder: Any,
) -> tuple[CoAuthorApplyService, Any, MagicMock]:
    """Service + gate mocks wired for one owned apply against ``chapter``.

    Returns ``(service, generation_request, chapter_repo)``. The chapter
    repo's ``update_content`` mirrors the real repository: it mutates the
    chapter row IN PLACE (the old word count is unrecoverable afterwards —
    the very hazard that makes the pre-write capture mandatory).
    """
    gen_req = _make_generation_request(
        chapter_id=chapter.id, novel_id=chapter.novel_id, user_id=user_id
    )
    repo = MagicMock(spec=["get_by_id"])
    repo.get_by_id = AsyncMock(return_value=gen_req)
    chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
    chapter_repo.get_by_id = AsyncMock(return_value=chapter)

    async def _update_content(c: Any, content: str, wc: int) -> Any:
        c.content = content
        c.word_count = wc
        return c

    chapter_repo.update_content = AsyncMock(side_effect=_update_content)
    service = CoAuthorApplyService(
        repo=cast("GenerationRepository", repo),
        chapter_repo=cast("ChapterRepository", chapter_repo),
        writing_stats_recorder=recorder,
    )
    return service, gen_req, chapter_repo


# ---------------------------------------------------------------------------
# Signed delta + attribution
# ---------------------------------------------------------------------------


class TestApplyRecordsSignedDelta:
    """One record_delta call per apply — signed, fully attributed."""

    @pytest.mark.asyncio
    async def test_apply_records_negative_delta_with_full_attribution(self) -> None:
        """Default chapter (wc 9) + default request (7-word reconstruction)
        yields exactly one call with delta -2 and the gate-validated identity."""
        user = uuid4()
        chapter = _make_chapter()  # word_count 9
        recorder = FakeWritingStatsRecorder()
        service, gen_req, chapter_repo = _apply_service(chapter, user, recorder)

        await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(user),
            request=_apply_request(request_id=gen_req.id),
        )

        assert recorder.calls == [
            {
                "user_id": user,  # UUID from the validated row, not the str
                "novel_id": chapter.novel_id,
                "chapter_id": chapter.id,
                "delta_words": -2,
            }
        ]
        chapter_repo.update_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_records_positive_delta_when_text_grows(self) -> None:
        """Accepted change grows the text: POSITIVE delta (5 - 3 = +2)."""
        user = uuid4()
        chapter = _make_chapter(content="A B C.", word_count=3)
        recorder = FakeWritingStatsRecorder()
        service, gen_req, _chapter_repo = _apply_service(chapter, user, recorder)

        await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(user),
            request=ApplyChangesRequest(
                request_id=gen_req.id,
                original="A B C.",
                accepted=[
                    TextChange(original_text="A B C", revised_text="D E F G H"),
                ],
                rejected=[],
            ),
        )

        assert len(recorder.calls) == 1
        assert recorder.calls[0]["delta_words"] == 2
        assert recorder.calls[0]["chapter_id"] == chapter.id
        assert recorder.calls[0]["novel_id"] == chapter.novel_id

    @pytest.mark.asyncio
    async def test_apply_identical_word_count_still_records_zero_delta(self) -> None:
        """Reconstruction keeps the chapter's word count ⇒ the call is
        pinned WITH delta 0 (no ``if delta:`` pre-check at call sites —
        skipping is the recorder's internal job, E3a contract)."""
        user = uuid4()
        chapter = _make_chapter(word_count=7)  # reconstruction also counts 7
        recorder = FakeWritingStatsRecorder()
        service, gen_req, _chapter_repo = _apply_service(chapter, user, recorder)

        await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(user),
            request=_apply_request(request_id=gen_req.id),
        )

        assert recorder.deltas == [0]
        assert len(recorder.calls) == 1


class TestApplyAttributionIsolation:
    @pytest.mark.asyncio
    async def test_attribution_does_not_leak_between_callers(self) -> None:
        """Two applies by different users/novels/chapters through ONE shared
        recorder ⇒ every call carries exactly its own identity, in order."""
        user_a, user_b = uuid4(), uuid4()
        chapter_a = _make_chapter()  # wc 9, delta -2
        chapter_b = _make_chapter(content="A B C.", word_count=3)  # growth, delta +2
        recorder = FakeWritingStatsRecorder()
        service_a, gen_req_a, _repo_a = _apply_service(chapter_a, user_a, recorder)
        service_b, gen_req_b, _repo_b = _apply_service(chapter_b, user_b, recorder)

        await service_a.apply_changes(
            chapter_a.id,
            chapter_a.novel_id,
            str(user_a),
            _apply_request(request_id=gen_req_a.id),
        )
        await service_b.apply_changes(
            chapter_b.id,
            chapter_b.novel_id,
            str(user_b),
            ApplyChangesRequest(
                request_id=gen_req_b.id,
                original="A B C.",
                accepted=[
                    TextChange(original_text="A B C", revised_text="D E F G H"),
                ],
                rejected=[],
            ),
        )

        assert [call["user_id"] for call in recorder.calls] == [user_a, user_b]
        assert [call["novel_id"] for call in recorder.calls] == [
            chapter_a.novel_id,
            chapter_b.novel_id,
        ]
        assert [call["chapter_id"] for call in recorder.calls] == [
            chapter_a.id,
            chapter_b.id,
        ]
        assert [call["delta_words"] for call in recorder.calls] == [-2, 2]


# ---------------------------------------------------------------------------
# Never-raises posture (real recorder behind a failing session factory)
# ---------------------------------------------------------------------------


class _ExplodingSessionFactory:
    """Stands in for ``async_sessionmaker`` — every session open fails."""

    def __call__(self, *args: Any) -> _ExplodingSessionCtx:
        return _ExplodingSessionCtx()


class _ExplodingSessionCtx:
    def __enter__(self) -> _ExplodingSessionCtx:
        raise RuntimeError("db down")

    def __aenter__(self) -> _ExplodingSessionCtx:
        raise RuntimeError("db down")

    def __aexit__(self, *args: Any) -> None:
        del args


class TestRecorderFailureDoesNotBreakApply:
    @pytest.mark.asyncio
    async def test_apply_succeeds_when_recorder_persistence_fails(self) -> None:
        """Real SqlWritingStatsRecorder swallows the DB failure; the apply
        write wins (ADR-095 — stats capture never breaks a user write)."""
        user = uuid4()
        chapter = _make_chapter()
        service, gen_req, chapter_repo = _apply_service(
            chapter,
            user,
            SqlWritingStatsRecorder(
                # cast: the sanctioned seam for a fake where async_sessionmaker is declared.
                cast("async_sessionmaker[AsyncSession]", _ExplodingSessionFactory()),
            ),
        )

        result = await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(user),
            request=_apply_request(request_id=gen_req.id),
        )

        assert result.content is not None
        assert "excellent" in result.content  # apply applied despite recorder failure
        chapter_repo.update_content.assert_called_once()
