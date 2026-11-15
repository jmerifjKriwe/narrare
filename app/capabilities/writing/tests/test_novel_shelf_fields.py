"""The shelf's tracking fields: status, series and archive, all real.

Status answers to the vocabulary at the service boundary, the series
title joins on read, and the archive keeps its books out of the main
grid until asked. Every figure traces to a row.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.capabilities.writing.repository import NovelRepository, SeriesRepository
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_novel(client: AsyncClient, title: str) -> str:
    response = await client.post("/api/writing/novels", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


async def _create_series(title: str, user_id: UUID = LOCAL_USER_ID) -> str:
    async with Session() as session:
        series = await SeriesRepository(session, user_id).create(title)
        await session.commit()
        return str(series.id)


async def test_a_new_novel_is_on_the_shelf_with_no_answers() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        body = fetched.json()
        assert body["status"] is None
        assert body["series_title"] is None
        assert body["series_volume"] is None
        assert body["archived_at"] is None


async def test_status_round_trips_through_patch_and_read() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        patched = await client.patch(f"/api/writing/novels/{novel_id}", json={"status": "revision"})
        assert patched.status_code == 200
        assert patched.json()["status"] == "revision"

        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["status"] == "revision"
        listed = await client.get("/api/writing/novels")
        assert listed.json()[0]["status"] == "revision"


@pytest.mark.parametrize("value", ["published", "Draft", "fertig"])
async def test_a_status_outside_the_vocabulary_is_refused(value: str) -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        refused = await client.patch(f"/api/writing/novels/{novel_id}", json={"status": value})
        assert refused.status_code == 422
        assert refused.json()["detail"] == "invalid status"
        # Nothing was written: the book still has no status.
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["status"] is None


async def test_a_carried_null_clears_the_status() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        await client.patch(f"/api/writing/novels/{novel_id}", json={"status": "draft"})
        cleared = await client.patch(f"/api/writing/novels/{novel_id}", json={"status": None})
        assert cleared.status_code == 200
        assert cleared.json()["status"] is None


async def test_the_series_title_joins_on_read() -> None:
    series_id = await _create_series("Die Nebel-Chroniken")
    async with _client() as client:
        novel_id = await _create_novel(client, "Band Eins")
        alone_id = await _create_novel(client, "Solo")
        patched = await client.patch(
            f"/api/writing/novels/{novel_id}",
            json={"series_id": series_id, "series_volume": 2},
        )
        assert patched.status_code == 200
        assert patched.json()["series_title"] == "Die Nebel-Chroniken"
        assert patched.json()["series_volume"] == 2

        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["series_title"] == "Die Nebel-Chroniken"
        listed = {novel["id"]: novel for novel in (await client.get("/api/writing/novels")).json()}
        assert listed[novel_id]["series_title"] == "Die Nebel-Chroniken"
        assert listed[novel_id]["series_volume"] == 2
        # A book without a series carries no title, not an empty one.
        assert listed[alone_id]["series_title"] is None
        assert listed[alone_id]["series_volume"] is None


async def test_a_foreign_or_unknown_series_is_refused_by_name() -> None:
    await seed_user(OTHER_USER)
    foreign_id = await _create_series("Fremde Reihe", user_id=OTHER_USER)
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        for series_id in (foreign_id, str(uuid4())):
            refused = await client.patch(
                f"/api/writing/novels/{novel_id}", json={"series_id": series_id}
            )
            assert refused.status_code == 422
            assert refused.json()["detail"] == "invalid series_id"


async def test_a_volume_without_a_series_is_refused() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        refused = await client.patch(f"/api/writing/novels/{novel_id}", json={"series_volume": 1})
        assert refused.status_code == 422
        assert refused.json()["detail"] == "invalid series_volume"


@pytest.mark.parametrize("value", [0, -1])
async def test_a_volume_below_one_is_refused(value: int) -> None:
    series_id = await _create_series("Die Nebel-Chroniken")
    async with _client() as client:
        novel_id = await _create_novel(client, "Band Eins")
        refused = await client.patch(
            f"/api/writing/novels/{novel_id}",
            json={"series_id": series_id, "series_volume": value},
        )
        assert refused.status_code == 422
        assert refused.json()["detail"] == "invalid series_volume"


async def test_clearing_the_series_takes_the_volume_with_it() -> None:
    series_id = await _create_series("Die Nebel-Chroniken")
    async with _client() as client:
        novel_id = await _create_novel(client, "Band Eins")
        await client.patch(
            f"/api/writing/novels/{novel_id}",
            json={"series_id": series_id, "series_volume": 2},
        )
        cleared = await client.patch(f"/api/writing/novels/{novel_id}", json={"series_id": None})
        assert cleared.status_code == 200
        assert cleared.json()["series_title"] is None
        assert cleared.json()["series_volume"] is None


async def test_a_volume_cannot_ride_a_cleared_series() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Band Eins")
        refused = await client.patch(
            f"/api/writing/novels/{novel_id}", json={"series_id": None, "series_volume": 3}
        )
        assert refused.status_code == 422
        assert refused.json()["detail"] == "invalid series_volume"


async def test_archived_books_leave_the_main_grid() -> None:
    async with _client() as client:
        kept_id = await _create_novel(client, "Bleibt")
        archived_id = await _create_novel(client, "Geht")
        # A chapter: the archived book keeps its real count on read.
        created = await client.post(
            f"/api/writing/novels/{archived_id}/chapters", json={"title": "Kapitel"}
        )
        assert created.status_code == 201
        stamp = datetime.now(UTC)
        patched = await client.patch(
            f"/api/writing/novels/{archived_id}", json={"archived_at": stamp.isoformat()}
        )
        assert patched.status_code == 200
        assert datetime.fromisoformat(patched.json()["archived_at"]) == stamp

        listed = await client.get("/api/writing/novels")
        assert [novel["id"] for novel in listed.json()] == [kept_id]

        with_archive = await client.get("/api/writing/novels", params={"include_archived": "true"})
        rows = {novel["id"]: novel for novel in with_archive.json()}
        assert set(rows) == {kept_id, archived_id}
        assert rows[archived_id]["chapter_count"] == 1
        assert datetime.fromisoformat(rows[archived_id]["archived_at"]) == stamp

        # The editor still reaches an archived book by id.
        fetched = await client.get(f"/api/writing/novels/{archived_id}")
        assert fetched.status_code == 200
        assert fetched.json()["chapter_count"] == 1


async def test_a_carried_null_returns_the_book_to_the_shelf() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        await client.patch(
            f"/api/writing/novels/{novel_id}",
            json={"archived_at": datetime.now(UTC).isoformat()},
        )
        assert (await client.get("/api/writing/novels")).json() == []

        restored = await client.patch(f"/api/writing/novels/{novel_id}", json={"archived_at": None})
        assert restored.status_code == 200
        assert restored.json()["archived_at"] is None
        listed = await client.get("/api/writing/novels")
        assert [novel["id"] for novel in listed.json()] == [novel_id]


async def test_the_target_words_ride_the_read() -> None:
    """The shelf's word pair reads the novel's own target: the column the
    setup wizard binds rides both read paths, and a book without a target
    answers None — the shelf's honest neutral, never a guessed goal."""
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["target_words"] is None
        listed = await client.get("/api/writing/novels")
        assert listed.json()[0]["target_words"] is None

        # The target the wizard binds is the row's own — the read carries it.
        async with Session() as session:
            novels = NovelRepository(session, LOCAL_USER_ID)
            novel = await novels.get(UUID(novel_id))
            assert novel is not None
            await novels.save(novel, {"target_words": 65000})
            await session.commit()

        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["target_words"] == 65000
        listed = await client.get("/api/writing/novels")
        assert listed.json()[0]["target_words"] == 65000
