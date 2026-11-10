"""Timeline events: per-novel CRUD over the writer's own event rows.

Create carries the temporal position (an order integer plus an optional
free-text date) and an optional chapter link; the list answers in position
order with dateless rows last. A foreign novel reads as missing (404),
never as an oracle; an empty title is refused; the timestamps are the
server's own.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.main import app
from app.capabilities.planning.models import TimelineEvent
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chapter, Novel, User
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = uuid4()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _novel_and_chapter(client: AsyncClient) -> tuple[str, str]:
    novel = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
    assert novel.status_code == 201
    chapter = await client.post(
        f"/api/writing/novels/{novel.json()['id']}/chapters", json={"title": "Ankunft"}
    )
    assert chapter.status_code == 201
    return novel.json()["id"], chapter.json()["id"]


def _event(title: str, **overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "title": title,
        "description": f"worum es bei {title} geht",
        "position": 1,
        "date_label": "im dritten Jahr",
        "character_names": ["Ari", "Bo"],
    }
    event.update(overrides)
    return event


def _path(novel_id: str) -> str:
    return f"/api/planning/novels/{novel_id}/timeline-events"


async def test_crud_round_trip_with_order_and_chapter() -> None:
    async with _client() as client:
        novel_id, chapter_id = await _novel_and_chapter(client)

        created = await client.post(
            _path(novel_id),
            json=_event("Sturm", chapter_id=chapter_id, position=2),
        )
        assert created.status_code == 201
        first = created.json()
        assert first["novel_id"] == novel_id
        assert first["chapter_id"] == chapter_id
        assert first["title"] == "Sturm"
        assert first["position"] == 2
        assert first["date_label"] == "im dritten Jahr"
        assert first["character_names"] == ["Ari", "Bo"]
        assert first["created_at"] and first["updated_at"]

        second = (await client.post(_path(novel_id), json=_event("Ruhe", position=1))).json()
        assert second["chapter_id"] is None

        listed = await client.get(_path(novel_id))
        assert listed.status_code == 200
        assert [(row["title"], row["position"]) for row in listed.json()] == [
            ("Ruhe", 1),
            ("Sturm", 2),
        ]

        fetched = await client.get(f"{_path(novel_id)}/{first['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["title"] == "Sturm"

        updated = await client.put(
            f"{_path(novel_id)}/{first['id']}",
            json={"title": "Sturm!", "position": 0, "character_names": ["Ari"]},
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Sturm!"
        assert updated.json()["position"] == 0
        assert updated.json()["description"] == first["description"]

        reordered = (await client.get(_path(novel_id))).json()
        assert [row["title"] for row in reordered] == ["Sturm!", "Ruhe"]

        deleted = await client.delete(f"{_path(novel_id)}/{first['id']}")
        assert deleted.status_code == 204
        assert (await client.get(f"{_path(novel_id)}/{first['id']}")).status_code == 404
        assert [row["title"] for row in (await client.get(_path(novel_id))).json()] == ["Ruhe"]


async def test_foreign_novel_reads_as_missing() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        novel = Novel(user_id=OTHER_USER, title="Fremder Roman")
        session.add(novel)
        await session.flush()
        chapter = Chapter(user_id=OTHER_USER, novel_id=novel.id, title="Ankunft", position=0)
        session.add(chapter)
        await session.flush()
        event = TimelineEvent(
            user_id=OTHER_USER,
            novel_id=novel.id,
            title="Fremd",
            description="",
            position=1,
        )
        session.add(event)
        await session.commit()
        foreign_novel, foreign_event = str(novel.id), str(event.id)
    async with _client() as client:
        own_novel, _ = await _novel_and_chapter(client)

        assert (await client.get(_path(foreign_novel))).status_code == 404
        assert (
            await client.post(_path(foreign_novel), json=_event("Eingeschmuggelt"))
        ).status_code == 404
        assert (await client.get(f"{_path(own_novel)}/{foreign_event}")).status_code == 404
        assert (
            await client.put(f"{_path(own_novel)}/{foreign_event}", json={"title": "X"})
        ).status_code == 404
        assert (await client.delete(f"{_path(own_novel)}/{foreign_event}")).status_code == 404

        assert (await client.get(_path(str(uuid4())))).status_code == 404
        assert (await client.get(f"{_path(own_novel)}/{uuid4()}")).status_code == 404


async def test_chapter_from_another_novel_is_422() -> None:
    async with _client() as client:
        novel_id, _ = await _novel_and_chapter(client)
        other_novel = (
            await client.post("/api/writing/novels", json={"title": "Anderer Roman"})
        ).json()["id"]
        other_chapter = (
            await client.post(
                f"/api/writing/novels/{other_novel}/chapters", json={"title": "Abreise"}
            )
        ).json()["id"]

        response = await client.post(
            _path(novel_id), json=_event("Falsch", chapter_id=other_chapter)
        )

        assert response.status_code == 422
        assert "chapter" in response.json()["detail"]


async def test_empty_title_is_refused() -> None:
    async with _client() as client:
        novel_id, chapter_id = await _novel_and_chapter(client)

        assert (await client.post(_path(novel_id), json=_event(""))).status_code == 422
        assert (await client.post(_path(novel_id), json=_event("   "))).status_code == 422

        created = (
            await client.post(_path(novel_id), json=_event("Sturm", chapter_id=chapter_id))
        ).json()
        refused = await client.put(f"{_path(novel_id)}/{created['id']}", json={"title": "  "})
        assert refused.status_code == 422
        assert (await client.get(f"{_path(novel_id)}/{created['id']}")).json()["title"] == "Sturm"


async def test_update_explicit_nulls_are_422_and_leave_the_event_untouched() -> None:
    """Non-clearable fields are non-nullable: a carried null is a 422 at the
    boundary — for the schema-shaped fields and for the title alike — and a
    refused PUT writes nothing at all."""
    async with _client() as client:
        novel_id, chapter_id = await _novel_and_chapter(client)
        created = (
            await client.post(_path(novel_id), json=_event("Sturm", chapter_id=chapter_id))
        ).json()
        before = (await client.get(f"{_path(novel_id)}/{created['id']}")).json()

        for body in (
            {"description": None},
            {"date_label": None},
            {"character_names": None},
            {"title": None},
        ):
            refused = await client.put(f"{_path(novel_id)}/{created['id']}", json=body)
            assert refused.status_code == 422

        assert (await client.get(f"{_path(novel_id)}/{created['id']}")).json() == before


async def test_same_position_same_timestamp_lists_in_id_order() -> None:
    """The list order is fully deterministic: position, then creation, then
    id. Two rows sharing both stamps still come out in id order."""
    async with _client() as client:
        novel_id, _ = await _novel_and_chapter(client)
    stamp = datetime.now(UTC)
    async with Session() as session:
        low, high = sorted([uuid4(), uuid4()])
        # Inserted out of id order: without the id tiebreak the rows come
        # back as inserted and this fails.
        for event_id in (high, low):
            session.add(
                TimelineEvent(
                    id=event_id,
                    user_id=LOCAL_USER_ID,
                    novel_id=UUID(novel_id),
                    title=f"Ereignis {event_id}",
                    description="",
                    position=1,
                    date_label="",
                    character_names=[],
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
        await session.commit()
    async with _client() as client:
        listed = (await client.get(_path(novel_id))).json()
    assert [row["id"] for row in listed] == [str(low), str(high)]


async def test_deleting_a_chapter_unlinks_its_events() -> None:
    """The chapter link is SET NULL: deleting the chapter unlinks the event,
    which survives with a null chapter id and stays on the timeline."""
    async with _client() as client:
        novel_id, chapter_id = await _novel_and_chapter(client)
        created = (
            await client.post(_path(novel_id), json=_event("Sturm", chapter_id=chapter_id))
        ).json()

        deleted = await client.delete(f"/api/writing/chapters/{chapter_id}")
        assert deleted.status_code == 204

        fetched = await client.get(f"{_path(novel_id)}/{created['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["chapter_id"] is None
        assert [row["id"] for row in (await client.get(_path(novel_id))).json()] == [created["id"]]


async def test_timestamps_are_server_owned() -> None:
    async with _client() as client:
        novel_id, _ = await _novel_and_chapter(client)

        created = (
            await client.post(
                _path(novel_id),
                json={
                    **_event("Sturm"),
                    "created_at": "2000-01-01T00:00:00+00:00",
                    "updated_at": "2000-01-01T00:00:00+00:00",
                },
            )
        ).json()
        assert "2000" not in created["created_at"]

        forged = await client.put(
            f"{_path(novel_id)}/{created['id']}",
            json={
                "title": "Sturm!",
                "created_at": "2000-01-01T00:00:00+00:00",
                "updated_at": "2000-01-01T00:00:00+00:00",
            },
        )
        assert forged.status_code == 200
        assert forged.json()["created_at"] == created["created_at"]
        assert "2000" not in forged.json()["updated_at"]


async def test_write_before_setup_is_409() -> None:
    """A create writes a row owned by a user; on an instance setup has not
    created, it answers 409 — never a bare 500."""
    from sqlalchemy import delete

    async with Session() as session:
        await session.execute(delete(User).where(User.id == LOCAL_USER_ID))
        await session.commit()

    async with _client() as client:
        response = await client.post(_path(str(uuid4())), json=_event("Sturm"))
        assert response.status_code == 409
        assert response.json() == {"detail": "setup required"}

    async with Session() as session:
        stored = await session.scalar(select(func.count()).select_from(TimelineEvent))
    assert stored == 0
