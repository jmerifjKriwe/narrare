"""Review-round regressions: setup guard, empty chapter titles, stream hygiene."""

from collections.abc import AsyncIterator  # noqa: TC003
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.kernel import llm
from app.kernel.db.session import Session

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _remove_users() -> None:
    async with Session() as session:
        await session.execute(text("DELETE FROM users"))
        await session.commit()


class _FailingProvider:
    """A catalog entry whose stream dies on the first pull."""

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        raise RuntimeError("provider unavailable")
        yield ""  # pragma: no cover — makes this an async generator


async def test_a_novel_cannot_be_created_before_setup() -> None:
    await _remove_users()
    async with _client() as client:
        response = await client.post("/api/writing/novels", json={"title": "Vorzeitig"})
        assert response.status_code == 409
        assert response.json()["detail"] == "setup required"


async def test_a_chapter_can_be_created_without_a_title() -> None:
    async with _client() as client:
        novel = await client.post("/api/writing/novels", json={"title": "Nebel"})
        created = await client.post(f"/api/writing/novels/{novel.json()['id']}/chapters", json={})
        assert created.status_code == 201
        assert created.json()["title"] == ""


async def test_the_continuation_stream_is_not_cached() -> None:
    async with _client() as client:
        novel = await client.post("/api/writing/novels", json={"title": "Nebel"})
        chapter = await client.post(
            f"/api/writing/novels/{novel.json()['id']}/chapters", json={"title": "Kapitel"}
        )
        response = await client.post(f"/api/writing/chapters/{chapter.json()['id']}/continue")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"


async def test_a_failing_provider_ends_the_stream_with_an_error_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(llm.PROVIDERS, "failing", _FailingProvider)
    monkeypatch.setenv("NARRE_LLM_PROVIDER", "failing")
    async with _client() as client:
        novel = await client.post("/api/writing/novels", json={"title": "Nebel"})
        chapter = await client.post(
            f"/api/writing/novels/{novel.json()['id']}/chapters", json={"title": "Kapitel"}
        )
        response = await client.post(f"/api/writing/chapters/{chapter.json()['id']}/continue")
        assert response.status_code == 200
        assert "event: error" in response.text
        assert "event: done" not in response.text
