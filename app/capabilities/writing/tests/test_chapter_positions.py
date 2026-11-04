"""Chapter positions: creations that overlap must not share a number.

A second click on "Neues Kapitel" before the first one lands is a legal
gesture, and the rail orders by ``position`` alone — with no tie-break, two
rows at one position are both a duplicated number in the list and an order the
planner picks. #521.
"""

import asyncio
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chapter
from app.kernel.db.session import Session

pytestmark = pytest.mark.timeout(60)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _novel(client: AsyncClient, title: str = "Der Nebel") -> str:
    response = await client.post("/api/writing/novels", json={"title": title})
    return response.json()["id"]


async def _create_chapter(novel_id: str) -> int:
    """One request of its own, the way two clicks arrive: separate connections."""
    async with _client() as client:
        response = await client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": ""})
        return response.status_code


async def test_chapters_created_at_once_get_distinct_positions() -> None:
    async with _client() as client:
        novel_id = await _novel(client)

    codes = await asyncio.gather(*(_create_chapter(novel_id) for _ in range(8)))
    assert codes == [201] * 8

    async with _client() as client:
        listed = (await client.get(f"/api/writing/novels/{novel_id}/chapters")).json()

    assert [chapter["position"] for chapter in listed] == list(range(8))


async def test_the_schema_refuses_two_chapters_at_one_position() -> None:
    """The allocation is guarded in code; the table refuses the collision too."""
    async with _client() as client:
        novel_id = await _novel(client)

    async with Session() as session:
        session.add(
            Chapter(user_id=LOCAL_USER_ID, novel_id=UUID(novel_id), title="", position=0, body="")
        )
        await session.commit()

        session.add(
            Chapter(user_id=LOCAL_USER_ID, novel_id=UUID(novel_id), title="", position=0, body="")
        )
        with pytest.raises(IntegrityError):
            await session.commit()
