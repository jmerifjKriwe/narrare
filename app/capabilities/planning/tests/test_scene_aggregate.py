"""The scene-plan aggregate: one read, one whole-aggregate write, server-side diff-sync.

PUT takes the chapter's whole scene list and diffs by stable scene id: a known
id updates, an id from another chapter is a 422 that writes nothing, a doubled
id is a 422 before any write, an absent id deletes, and positions renumber
1..N by payload order. A foreign novel reads as missing (404), never as an
oracle, and the timestamps are the server's own.
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.api.main import app
from app.capabilities.planning.models import ScenePlan
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


def _scene(scene_id: UUID, title: str, **overrides: object) -> dict[str, object]:
    scene: dict[str, object] = {
        "id": str(scene_id),
        "title": title,
        "purpose": f"wozu {title}",
        "conflict": f"was {title}",
        "resolution": f"wie {title}",
        "beats": [f"{title} eins", f"{title} zwei"],
        "status": "planned",
    }
    scene.update(overrides)
    return scene


def _path(novel_id: str, chapter_id: str) -> str:
    return f"/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes"


async def test_get_returns_the_empty_aggregate_without_creating_rows() -> None:
    async with _client() as client:
        novel_id, chapter_id = await _novel_and_chapter(client)

        response = await client.get(_path(novel_id, chapter_id))

        assert response.status_code == 200
        body = response.json()
        assert body["chapter_id"] == chapter_id
        assert body["scenes"] == []
        assert body["version_updated_at"]
        # No auto-create means no rows: the empty answer is an answer, not a write.
        async with Session() as session:
            stored = await session.scalar(select(func.count()).select_from(ScenePlan))
        assert stored == 0


async def test_put_reorders_edits_deletes_and_adds() -> None:
    async with _client() as client:
        novel_id, chapter_id = await _novel_and_chapter(client)
        first, second, third, added = uuid4(), uuid4(), uuid4(), uuid4()

        seeded = await client.put(
            _path(novel_id, chapter_id),
            json={
                "scenes": [
                    _scene(first, "Anfang"),
                    _scene(second, "Mitte"),
                    _scene(third, "Ende"),
                ]
            },
        )
        assert seeded.status_code == 200
        assert [scene["position"] for scene in seeded.json()["scenes"]] == [1, 2, 3]

        saved = await client.put(
            _path(novel_id, chapter_id),
            json={
                "scenes": [
                    _scene(third, "Ende?", status="in_progress"),
                    _scene(first, "Anfang"),
                    _scene(added, "Neu"),
                ]
            },
        )
        assert saved.status_code == 200
        scenes = saved.json()["scenes"]
        assert [(scene["title"], scene["position"]) for scene in scenes] == [
            ("Ende?", 1),
            ("Anfang", 2),
            ("Neu", 3),
        ]
        assert [scene["id"] for scene in scenes] == [str(third), str(first), str(added)]
        assert scenes[0]["status"] == "in_progress"
        assert scenes[0]["beats"] == ["Ende? eins", "Ende? zwei"]

        reloaded = (await client.get(_path(novel_id, chapter_id))).json()["scenes"]
        assert [(scene["title"], scene["position"]) for scene in reloaded] == [
            ("Ende?", 1),
            ("Anfang", 2),
            ("Neu", 3),
        ]


async def test_put_unknown_scene_id_is_422_and_leaves_the_aggregate_untouched() -> None:
    async with _client() as client:
        novel_id, chapter_id = await _novel_and_chapter(client)
        other_chapter = (
            await client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": "Abreise"})
        ).json()["id"]
        kept = uuid4()
        await client.put(_path(novel_id, chapter_id), json={"scenes": [_scene(kept, "Anfang")]})
        foreign_scene = uuid4()
        await client.put(
            _path(novel_id, other_chapter), json={"scenes": [_scene(foreign_scene, "Fremd")]}
        )
        before = (await client.get(_path(novel_id, chapter_id))).json()

        refused = await client.put(
            _path(novel_id, chapter_id),
            json={
                "scenes": [
                    _scene(
                        kept,
                        "Anfang!",
                    ),
                    _scene(foreign_scene, "Eingeschmuggelt"),
                ]
            },
        )

        assert refused.status_code == 422
        assert "unknown scene id" in refused.json()["detail"]
        assert (await client.get(_path(novel_id, chapter_id))).json() == before


async def test_put_duplicate_scene_id_is_422_before_any_write() -> None:
    async with _client() as client:
        novel_id, chapter_id = await _novel_and_chapter(client)
        first, second = uuid4(), uuid4()
        await client.put(
            _path(novel_id, chapter_id),
            json={"scenes": [_scene(first, "Anfang"), _scene(second, "Mitte")]},
        )
        before = (await client.get(_path(novel_id, chapter_id))).json()

        refused = await client.put(
            _path(novel_id, chapter_id),
            json={
                "scenes": [
                    _scene(first, "Anfang!"),
                    _scene(second, "Mitte"),
                    _scene(first, "Anfang zweimal"),
                ]
            },
        )

        assert refused.status_code == 422
        assert "duplicate scene id" in refused.json()["detail"]
        assert (await client.get(_path(novel_id, chapter_id))).json() == before


async def test_put_unknown_status_is_422_and_leaves_the_aggregate_untouched() -> None:
    async with _client() as client:
        novel_id, chapter_id = await _novel_and_chapter(client)
        kept = uuid4()
        await client.put(_path(novel_id, chapter_id), json={"scenes": [_scene(kept, "Anfang")]})
        before = (await client.get(_path(novel_id, chapter_id))).json()

        refused = await client.put(
            _path(novel_id, chapter_id),
            json={"scenes": [_scene(kept, "Anfang", status="archived")]},
        )

        assert refused.status_code == 422
        assert (await client.get(_path(novel_id, chapter_id))).json() == before


async def test_foreign_and_missing_chapters_read_as_missing() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        novel = Novel(user_id=OTHER_USER, title="Fremder Roman")
        session.add(novel)
        await session.flush()
        chapter = Chapter(user_id=OTHER_USER, novel_id=novel.id, title="Ankunft", position=0)
        session.add(chapter)
        await session.commit()
        foreign_novel, foreign_chapter = str(novel.id), str(chapter.id)
    async with _client() as client:
        own_novel, own_chapter = await _novel_and_chapter(client)

        assert (await client.get(_path(foreign_novel, foreign_chapter))).status_code == 404
        assert (
            await client.put(_path(foreign_novel, foreign_chapter), json={"scenes": []})
        ).status_code == 404

        assert (await client.get(_path(str(uuid4()), str(uuid4())))).status_code == 404
        assert (
            await client.put(_path(str(uuid4()), str(uuid4())), json={"scenes": []})
        ).status_code == 404

        assert (await client.get(_path(own_novel, foreign_chapter))).status_code == 404
        assert (await client.get(_path(foreign_novel, own_chapter))).status_code == 404


async def test_timestamps_are_server_owned() -> None:
    async with _client() as client:
        novel_id, chapter_id = await _novel_and_chapter(client)
        scene_id = uuid4()

        created = (
            await client.put(
                _path(novel_id, chapter_id), json={"scenes": [_scene(scene_id, "Anfang")]}
            )
        ).json()["scenes"][0]
        first_version = (await client.get(_path(novel_id, chapter_id))).json()["version_updated_at"]

        forged = await client.put(
            _path(novel_id, chapter_id),
            json={
                "scenes": [
                    _scene(
                        scene_id,
                        "Anfang!",
                        created_at="2000-01-01T00:00:00+00:00",
                        updated_at="2000-01-01T00:00:00+00:00",
                    )
                ]
            },
        )

        assert forged.status_code == 200
        row = forged.json()["scenes"][0]
        assert row["created_at"] == created["created_at"]
        assert "2000" not in row["updated_at"]
        assert datetime.fromisoformat(row["updated_at"]) > datetime.fromisoformat(
            created["updated_at"]
        )
        second_version = forged.json()["version_updated_at"]
        assert datetime.fromisoformat(second_version) > datetime.fromisoformat(first_version)


async def test_put_before_setup_is_409_and_writes_nothing() -> None:
    """A PUT writes rows owned by a user; on an instance setup has not
    created, it answers 409 and writes nothing — never a bare 500."""
    async with Session() as session:
        await session.execute(delete(User).where(User.id == LOCAL_USER_ID))
        await session.commit()

    async with _client() as client:
        response = await client.put(
            _path(str(uuid4()), str(uuid4())),
            json={"scenes": [_scene(uuid4(), "Anfang")]},
        )
        assert response.status_code == 409
        assert response.json() == {"detail": "setup required"}

    async with Session() as session:
        stored = await session.scalar(select(func.count()).select_from(ScenePlan))
    assert stored == 0


async def test_get_before_setup_is_404() -> None:
    """Reads need no owner: on an unset-up instance a GET is missing, not a
    refusal — only the write maps the missing user to 409."""
    async with Session() as session:
        await session.execute(delete(User).where(User.id == LOCAL_USER_ID))
        await session.commit()

    async with _client() as client:
        response = await client.get(_path(str(uuid4()), str(uuid4())))

        assert response.status_code == 404


async def test_put_empty_clears_the_chapter() -> None:
    async with _client() as client:
        novel_id, chapter_id = await _novel_and_chapter(client)
        await client.put(_path(novel_id, chapter_id), json={"scenes": [_scene(uuid4(), "Anfang")]})

        cleared = await client.put(_path(novel_id, chapter_id), json={"scenes": []})

        assert cleared.status_code == 200
        assert cleared.json()["scenes"] == []
        assert (await client.get(_path(novel_id, chapter_id))).json()["scenes"] == []
