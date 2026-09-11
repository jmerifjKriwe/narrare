"""RT-S2 — IDOR regression tests: co-author apply/feedback 404 matrix (HTTP).

HTTP-level counterpart to ``test_coauthor_apply_ownership.py`` (RULE-04
file-size split): the real router + the REAL ``CoAuthorApplyService`` over
mock repositories, with auth overridden per caller.  This proves the full
chain — route → service gate → global ``NotFoundError`` handler → 404 —
and that the feedback route threads ``CurrentUserIdDep`` into
``record_feedback`` (without it the endpoint would 500 on the new
signature).

Matrix: owner → 200/204 unchanged; foreign request id → 404 with no side
effect; unknown request id → 404 identical in shape to the foreign case.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from tests.unit.api.writing._test_coauthor_helpers import (
    _apply_service,
    _chapter_repo_mock,
    _feedback_collector_mock,
    _gen_repo,
    _make_chapter,
)

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from narrare.writing.coauthor_apply_service import CoAuthorApplyService

USER_A = uuid4()  # rightful owner of the generation request + chapter
USER_B = uuid4()  # foreign caller


def _serializable_chapter() -> Any:
    """Chapter instance carrying every field ``ChapterResponse`` requires."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return _make_chapter(
        volume_id=None,
        summary="",
        status="draft",
        pov_character_id="",
        timeline_position="",
        created_at=now,
        updated_at=now,
    )


class TestOwnershipHttpLevel:
    """404 matrix through POST .../co-author/apply and .../co-author/feedback."""

    def _client_for(
        self, caller: UUID, service: CoAuthorApplyService
    ) -> tuple[AsyncClient, AbstractContextManager[object]]:
        app = create_app()

        async def _mock_session() -> Any:
            mock = AsyncMock()
            mock.execute = AsyncMock()
            yield mock

        async def _mock_auth() -> str:
            return str(caller)

        app.dependency_overrides[get_async_session] = _mock_session
        app.dependency_overrides[get_current_user_id] = _mock_auth

        async def _factory(session: Any) -> CoAuthorApplyService:
            return service

        client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Origin": "http://localhost:3000"},
        )
        return client, patch("narrare.writing.router_coauthor.get_coauthor_apply_service", _factory)

    async def _post_apply(
        self, client: AsyncClient, chapter_id: UUID, novel_id: UUID, request_id: UUID
    ) -> Any:
        return await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/co-author/apply",
            params={"novel_id": str(novel_id)},
            json={
                "request_id": str(request_id),
                "original": "The original chapter content. It was quite good.",
                "accepted": [
                    {"original_text": "quite good", "revised_text": "excellent"},
                ],
            },
        )

    async def _post_feedback(
        self, client: AsyncClient, chapter_id: UUID, novel_id: UUID, request_id: UUID
    ) -> Any:
        return await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/co-author/feedback",
            params={"novel_id": str(novel_id)},
            json={
                "request_id": str(request_id),
                "feedback": [
                    {
                        "change_id": "change-1",
                        "action": "accept",
                        "focus": "word_choice",
                        "original": "old",
                        "revised": "new",
                    },
                ],
            },
        )

    @pytest.mark.asyncio
    async def test_apply_owner_returns_200(self) -> None:
        chapter = _serializable_chapter()
        repo, gen_req = _gen_repo(owner=USER_A, chapter_id=chapter.id, novel_id=chapter.novel_id)
        chapter_repo = _chapter_repo_mock(chapter)
        service = _apply_service(repo, chapter_repo)

        client, factory_patch = self._client_for(USER_A, service)
        with factory_patch:
            response = await self._post_apply(client, chapter.id, chapter.novel_id, gen_req.id)
        await client.aclose()

        assert response.status_code == status.HTTP_200_OK
        chapter_repo.update_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_foreign_returns_404_and_writes_nothing(self) -> None:
        chapter = _serializable_chapter()
        repo, gen_req = _gen_repo(owner=USER_A, chapter_id=chapter.id, novel_id=chapter.novel_id)
        chapter_repo = _chapter_repo_mock(chapter)
        feedback = _feedback_collector_mock()
        service = _apply_service(repo, chapter_repo, feedback)

        client, factory_patch = self._client_for(USER_B, service)
        with factory_patch:
            response = await self._post_apply(client, chapter.id, chapter.novel_id, gen_req.id)
        await client.aclose()

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["code"] == "NOT_FOUND"
        chapter_repo.update_content.assert_not_called()
        assert feedback.record.await_count == 0

    @pytest.mark.asyncio
    async def test_apply_unknown_404_matches_foreign_shape(self) -> None:
        chapter = _serializable_chapter()
        repo, gen_req = _gen_repo(owner=USER_A, chapter_id=chapter.id, novel_id=chapter.novel_id)
        service = _apply_service(repo, _chapter_repo_mock(chapter))
        unknown_request_id = uuid4()

        client, factory_patch = self._client_for(USER_B, service)
        with factory_patch:
            foreign = await self._post_apply(client, chapter.id, chapter.novel_id, gen_req.id)
            unknown = await self._post_apply(
                client, chapter.id, chapter.novel_id, unknown_request_id
            )
        await client.aclose()

        assert foreign.status_code == unknown.status_code == 404
        foreign_body, unknown_body = foreign.json(), unknown.json()
        assert foreign_body["code"] == unknown_body["code"] == "NOT_FOUND"
        # detail is a pure function of the caller's own input id.
        assert foreign_body["detail"] == f"Generation request ({gen_req.id}) not found"
        assert unknown_body["detail"] == f"Generation request ({unknown_request_id}) not found"

    @pytest.mark.asyncio
    async def test_feedback_owner_returns_204(self) -> None:
        repo, gen_req = _gen_repo(owner=USER_A)
        feedback = _feedback_collector_mock()
        service = _apply_service(repo, feedback=feedback)

        client, factory_patch = self._client_for(USER_A, service)
        with factory_patch:
            response = await self._post_feedback(client, uuid4(), uuid4(), gen_req.id)
        await client.aclose()

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert feedback.record.await_count == 1

    @pytest.mark.asyncio
    async def test_feedback_foreign_returns_404_and_records_nothing(self) -> None:
        repo, gen_req = _gen_repo(owner=USER_A)
        feedback = _feedback_collector_mock()
        service = _apply_service(repo, feedback=feedback)

        client, factory_patch = self._client_for(USER_B, service)
        with factory_patch:
            response = await self._post_feedback(client, uuid4(), uuid4(), gen_req.id)
        await client.aclose()

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["code"] == "NOT_FOUND"
        # Zero FeedbackEvents under the victim's user id.
        assert feedback.record.await_count == 0
