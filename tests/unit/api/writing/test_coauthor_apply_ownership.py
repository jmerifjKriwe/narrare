"""RT-S2 — IDOR regression tests: ownership gate on co-author apply/feedback.

Before the S2 fix, ``CoAuthorApplyService`` ignored ``user_id`` entirely:
``apply_changes`` loaded the chapter by ``(chapter_id, novel_id)`` — a pairing
that proves chapter∈novel but says nothing about the caller — and wrote the
reconstructed text to it (arbitrary cross-tenant chapter WRITE), while
``record_feedback`` resolved the row with a bare ``get_by_id`` and stamped the
resulting ``FeedbackEvent`` entries with the ROW's ``user_id`` — so a foreign
caller polluted the victim's preference learning (``_helpers.py:44-47``).

The fix is Pattern A (writing-module precedent ``get_validated_request``):
the FIRST statement of both methods resolves the generation request through
the caller-scoped helper (unknown and foreign ids both → ``NotFoundError`` →
404), and ``apply_changes`` additionally verifies that the validated row
references the addressed chapter AND novel before any load or write.

Matrix (plan S2): (1) owner → unchanged behavior, (2) foreign request id →
404 AND no side effect (``update_content`` never called, chapter content
untouched, zero FeedbackEvents under the victim's user id), (3) unknown
request id → 404 identical in shape to (2), (4) owned request row that does
not reference the addressed chapter/novel → 404.

The HTTP-level matrix (real router + real service) lives in
``test_coauthor_apply_ownership_http.py`` (RULE-04 file-size split).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare_core.memory.models import FeedbackEvent
from narrare_core.shared.errors import NotFoundError
from tests.unit.api.writing._test_coauthor_helpers import (
    _apply_request,
    _apply_service,
    _chapter_repo_mock,
    _empty_gen_repo,
    _feedback_collector_mock,
    _feedback_items,
    _gen_repo,
    _make_chapter,
)

USER_A = uuid4()  # rightful owner of the generation request + chapter
USER_B = uuid4()  # foreign caller


# ---------------------------------------------------------------------------
# apply_changes — service level
# ---------------------------------------------------------------------------


class TestApplyChangesOwnership:
    """``apply_changes`` gates on the caller-owned request row (Pattern A)."""

    @pytest.mark.asyncio
    async def test_foreign_request_raises_not_found_and_never_touches_chapter(self) -> None:
        """USER_B applying with USER_A's request id → 404 BEFORE any chapter
        load or write; chapter content untouched; zero FeedbackEvents."""
        chapter = _make_chapter()
        original_content = chapter.content
        repo, gen_req = _gen_repo(owner=USER_A, chapter_id=chapter.id, novel_id=chapter.novel_id)
        chapter_repo = _chapter_repo_mock(chapter)
        feedback = _feedback_collector_mock()
        service = _apply_service(repo, chapter_repo, feedback)

        with pytest.raises(NotFoundError, match="Generation request"):
            await service.apply_changes(
                chapter_id=chapter.id,
                novel_id=chapter.novel_id,
                user_id=str(USER_B),
                request=_apply_request(request_id=gen_req.id, with_rejected=True),
            )

        # No side effect on the victim's chapter — nothing was even loaded.
        chapter_repo.get_by_id.assert_not_called()
        chapter_repo.update_content.assert_not_called()
        assert chapter.content == original_content
        # No preference-learning pollution under the victim's user id.
        assert feedback.record.await_count == 0

    @pytest.mark.asyncio
    async def test_unknown_request_raises_not_found(self) -> None:
        chapter = _make_chapter()
        chapter_repo = _chapter_repo_mock(chapter)
        service = _apply_service(_empty_gen_repo(), chapter_repo, _feedback_collector_mock())

        with pytest.raises(NotFoundError, match="Generation request"):
            await service.apply_changes(
                chapter_id=chapter.id,
                novel_id=chapter.novel_id,
                user_id=str(USER_B),
                request=_apply_request(),
            )

        chapter_repo.get_by_id.assert_not_called()
        chapter_repo.update_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_foreign_and_unknown_request_are_indistinguishable(self) -> None:
        """Anti-enumeration: the 404 is a pure function of the caller's input."""
        chapter = _make_chapter()
        repo, gen_req = _gen_repo(owner=USER_A, chapter_id=chapter.id, novel_id=chapter.novel_id)
        unknown_request_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await _apply_service(repo, _chapter_repo_mock(chapter)).apply_changes(
                chapter.id, chapter.novel_id, str(USER_B), _apply_request(request_id=gen_req.id)
            )
        with pytest.raises(NotFoundError) as unknown_exc:
            await _apply_service(_empty_gen_repo(), _chapter_repo_mock(chapter)).apply_changes(
                chapter.id,
                chapter.novel_id,
                str(USER_B),
                _apply_request(request_id=unknown_request_id),
            )

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Generation request ({gen_req.id}) not found"
        assert str(unknown_exc.value) == f"Generation request ({unknown_request_id}) not found"

    @pytest.mark.asyncio
    async def test_owned_request_referencing_other_chapter_raises_not_found(self) -> None:
        """The write must target the chapter the request row was created for —
        a caller-owned request id cannot unlock a different chapter."""
        victim_chapter = _make_chapter()  # addressed in the URL
        repo, gen_req = _gen_repo(owner=USER_B, novel_id=victim_chapter.novel_id)  # other chapter
        chapter_repo = _chapter_repo_mock(victim_chapter)
        service = _apply_service(repo, chapter_repo, _feedback_collector_mock())

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.apply_changes(
                chapter_id=victim_chapter.id,
                novel_id=victim_chapter.novel_id,
                user_id=str(USER_B),
                request=_apply_request(request_id=gen_req.id),
            )

        chapter_repo.get_by_id.assert_not_called()
        chapter_repo.update_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_owned_request_referencing_other_novel_raises_not_found(self) -> None:
        chapter = _make_chapter()
        repo, gen_req = _gen_repo(owner=USER_B, chapter_id=chapter.id)  # other novel
        chapter_repo = _chapter_repo_mock(chapter)
        service = _apply_service(repo, chapter_repo, _feedback_collector_mock())

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.apply_changes(
                chapter_id=chapter.id,
                novel_id=chapter.novel_id,
                user_id=str(USER_B),
                request=_apply_request(request_id=gen_req.id),
            )

        chapter_repo.get_by_id.assert_not_called()
        chapter_repo.update_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_owner_applies_changes_unchanged(self) -> None:
        """Owner flow is unchanged: validated row → load → reconstruct → write;
        rejected-change feedback is recorded under the OWNER's user id."""
        chapter = _make_chapter()
        repo, gen_req = _gen_repo(owner=USER_A, chapter_id=chapter.id, novel_id=chapter.novel_id)
        chapter_repo = _chapter_repo_mock(chapter)
        feedback = _feedback_collector_mock()
        service = _apply_service(repo, chapter_repo, feedback)

        result = await service.apply_changes(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            user_id=str(USER_A),
            request=_apply_request(request_id=gen_req.id, with_rejected=True),
        )

        assert result is chapter
        chapter_repo.update_content.assert_called_once()
        assert "excellent" in result.content
        # Rejected-change feedback: recorded, and stamped with the owner's id.
        assert feedback.record.await_count == 1
        event = feedback.record.call_args[0][0]
        assert isinstance(event, FeedbackEvent)
        assert event.user_id == USER_A


# ---------------------------------------------------------------------------
# record_feedback — service level
# ---------------------------------------------------------------------------


class TestRecordFeedbackOwnership:
    """``record_feedback`` resolves the row caller-scoped (no pollution)."""

    @pytest.mark.asyncio
    async def test_foreign_request_raises_not_found_and_records_nothing(self) -> None:
        repo, gen_req = _gen_repo(owner=USER_A)
        feedback = _feedback_collector_mock()
        service = _apply_service(repo, feedback=feedback)

        with pytest.raises(NotFoundError, match="Generation request"):
            await service.record_feedback(gen_req.id, _feedback_items(), user_id=str(USER_B))

        assert feedback.record.await_count == 0

    @pytest.mark.asyncio
    async def test_unknown_request_raises_not_found(self) -> None:
        feedback = _feedback_collector_mock()
        service = _apply_service(_empty_gen_repo(), feedback=feedback)

        with pytest.raises(NotFoundError, match="Generation request"):
            await service.record_feedback(uuid4(), _feedback_items(), user_id=str(USER_B))

        assert feedback.record.await_count == 0

    @pytest.mark.asyncio
    async def test_foreign_and_unknown_request_are_indistinguishable(self) -> None:
        repo, gen_req = _gen_repo(owner=USER_A)
        unknown_request_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await _apply_service(repo).record_feedback(gen_req.id, [], user_id=str(USER_B))
        with pytest.raises(NotFoundError) as unknown_exc:
            await _apply_service(_empty_gen_repo()).record_feedback(
                unknown_request_id, [], user_id=str(USER_B)
            )

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Generation request ({gen_req.id}) not found"
        assert str(unknown_exc.value) == f"Generation request ({unknown_request_id}) not found"

    @pytest.mark.asyncio
    async def test_owner_records_feedback_under_own_user_id(self) -> None:
        repo, gen_req = _gen_repo(owner=USER_A)
        feedback = _feedback_collector_mock()
        service = _apply_service(repo, feedback=feedback)

        await service.record_feedback(gen_req.id, _feedback_items(), user_id=str(USER_A))

        assert feedback.record.await_count == 1
        event = feedback.record.call_args[0][0]
        assert isinstance(event, FeedbackEvent)
        assert event.user_id == USER_A
