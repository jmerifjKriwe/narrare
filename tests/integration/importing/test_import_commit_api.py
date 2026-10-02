"""Integration tests for POST /api/v1/import/commit — ownership + atomic append."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from narrare.novels.models import Novel

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


def _extract_user_id(auth_headers: dict[str, str]) -> uuid.UUID:
    """Derive the ``auth_headers`` user's id from the JWT sub claim.

    Mirrors the ``_extract_user_id`` helper in ``tests/integration/setup/`` —
    the conftest has no dedicated ``user_id`` fixture by design.
    """
    import jwt

    from narrare._app.config import get_settings

    token = auth_headers["Authorization"].removeprefix("Bearer ")
    payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    return uuid.UUID(payload["sub"])


async def _create_second_user(db_session: AsyncSession) -> uuid.UUID:
    """Real second ``User`` row (mirrors ``_second_user_headers`` in notes tests)."""
    from narrare.auth.models import User

    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(),
        email=f"import-b-{uuid.uuid4().hex[:12]}@example.com",
        hashed_password="not-a-real-hash",
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    await db_session.flush()
    return user.id


async def _create_novel(
    db_session: AsyncSession,
    user_id: uuid.UUID,
    title: str = "Import Target",
) -> Novel:
    novel = Novel(user_id=user_id, title=title)
    db_session.add(novel)
    await db_session.flush()
    return novel


def _files() -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        ("files", ("ch-01.md", b"# One\nfirst body", "text/markdown")),
        ("files", ("ch-02.md", b"# Two\nsecond body", "text/markdown")),
    ]


class TestCommitEndpoint:
    async def test_commit_appends_atomically(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel = await _create_novel(db_session, _extract_user_id(auth_headers))
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={
                "novel_id": str(novel.id),
                "adjustments": ('{"excluded_indices": [1], "title_overrides": {"0": "Renamed"}}'),
            },
            files=_files(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["created_count"] == 1
        assert body["chapters"][0]["title"] == "Renamed"

        chapters = await client.get(f"/api/v1/novels/{novel.id}/chapters", headers=auth_headers)
        titles = [c["title"] for c in chapters.json()]
        assert titles == ["Renamed"]

    async def test_commit_unknown_novel_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(uuid.uuid4()), "adjustments": "{}"},
            files=_files(),
        )
        assert response.status_code == 404

    async def test_commit_foreign_novel_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        second_user_id = await _create_second_user(db_session)
        novel = await _create_novel(db_session, second_user_id, title="Foreign")
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": "{}"},
            files=_files(),
        )
        assert response.status_code == 404  # foreign ≡ unknown (IDOR pattern)

    async def test_commit_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/import/commit",
            data={"novel_id": str(uuid.uuid4()), "adjustments": "{}"},
            files=_files(),
        )
        assert response.status_code == 401

    async def test_commit_malformed_adjustments_json_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(uuid.uuid4()), "adjustments": "{not json"},
            files=_files(),
        )
        assert response.status_code == 422  # invalid user input, never a 500
        assert "detail" in response.json()

    async def test_commit_wrong_shape_adjustments_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={
                "novel_id": str(uuid.uuid4()),
                "adjustments": '{"excluded_indices": "nope"}',
            },
            files=_files(),
        )
        assert response.status_code == 422  # valid JSON, invalid shape → still 422
        assert "detail" in response.json()

    async def test_commit_out_of_range_adjustment_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel = await _create_novel(db_session, _extract_user_id(auth_headers))
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={
                "novel_id": str(novel.id),
                "adjustments": '{"excluded_indices": [99]}',
            },
            files=_files(),
        )
        assert response.status_code == 422
        # rollback proof: nothing was written
        chapters = await client.get(f"/api/v1/novels/{novel.id}/chapters", headers=auth_headers)
        assert chapters.json() == []
