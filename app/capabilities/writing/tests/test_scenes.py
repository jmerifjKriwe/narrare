"""Scenes: the prose unit under a chapter — CRUD, the whole-set order, and
the derived reads (W4 design §5, D1/D2/D16).

A chapter is a grouping shell; its scenes carry the prose. The contract is
the chapters' own, one level down: positions are unique per chapter and
deferrable (#521), allocated under the book's row lock; an order PUT is the
whole set or a 409 naming the stored ids; a delete closes the gap and moves
a number, never a "last written" (D8). An empty chapter is a real state
(D16) — the last scene may go, and the chapter reads honestly at zero.

The word figures derive from scenes through the shelf's one whitespace
rule: SceneRead.word_count per scene, ChapterRead.word_count + scene_count
per chapter, NovelRead.word_count the book's sum. The empty title is the
localized placeholder's state, stored as "" — a rendering, not a value.
"""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_novel(client: AsyncClient, title: str = "Der Nebel") -> str:
    response = await client.post("/api/writing/novels", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


async def _create_chapter(client: AsyncClient, novel_id: str, title: str = "Ankunft") -> str:
    created = await client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": title})
    assert created.status_code == 201
    return created.json()["id"]


async def _create_scene(client: AsyncClient, chapter_id: str, **fields: object) -> dict[str, Any]:
    created = await client.post(f"/api/writing/chapters/{chapter_id}/scenes", json=fields)
    assert created.status_code == 201
    return created.json()


async def _three_scenes(client: AsyncClient, chapter_id: str) -> list[dict[str, Any]]:
    return [
        await _create_scene(client, chapter_id, title=title)
        for title in ("Ankunft", "Nacht", "Abfahrt")
    ]


async def _seed_foreign_chapter() -> tuple[UUID, UUID]:
    """A chapter (and its novel) another user owns — the boundary's other side."""
    await seed_user(OTHER_USER)
    novel_id, chapter_id = uuid4(), uuid4()
    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, now(), now())"
            ),
            {"id": novel_id, "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.execute(
            text(
                "INSERT INTO chapters "
                "(id, user_id, novel_id, title, position, body, created_at, updated_at) "
                "VALUES (:id, :user_id, :novel_id, :title, 0, '', now(), now())"
            ),
            {"id": chapter_id, "user_id": OTHER_USER, "novel_id": novel_id, "title": "Fremd"},
        )
        await session.commit()
    return novel_id, chapter_id


async def _seed_foreign_scene() -> UUID:
    """A scene another user owns, hanging off a foreign chapter."""
    _, chapter_id = await _seed_foreign_chapter()
    scene_id = uuid4()
    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO scenes "
                "(id, user_id, chapter_id, position, title, body, created_at, updated_at) "
                "VALUES (:id, :user_id, :chapter_id, 1, '', '', now(), now())"
            ),
            {"id": scene_id, "user_id": OTHER_USER, "chapter_id": chapter_id},
        )
        await session.commit()
    return scene_id


# --- CRUD and the honest defaults -----------------------------------------


async def test_a_scene_is_born_empty_with_unset_labels() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(client, chapter_id)

    assert scene["chapter_id"] == chapter_id
    assert scene["title"] == ""
    assert scene["body"] == ""
    assert scene["setting"] is None
    assert scene["story_time"] is None
    assert scene["word_count"] == 0
    assert scene["position"] == 1
    assert scene["id"]
    assert scene["created_at"]
    assert scene["updated_at"]


async def test_the_first_scene_starts_at_position_one() -> None:
    """Scenes are 1-based — the migration wraps each chapter's prose at
    position 1, and a new chapter's first scene joins it there, not at 0."""
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        first = await _create_scene(client, chapter_id)
        second = await _create_scene(client, chapter_id)
    assert first["position"] == 1
    assert second["position"] == 2


async def test_scenes_are_listed_in_position_order() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        await _three_scenes(client, chapter_id)
        listed = await client.get(f"/api/writing/chapters/{chapter_id}/scenes")
    assert listed.status_code == 200
    assert [scene["title"] for scene in listed.json()] == ["Ankunft", "Nacht", "Abfahrt"]
    assert [scene["position"] for scene in listed.json()] == [1, 2, 3]


async def test_a_scene_carries_its_prose_and_labels() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(
            client,
            chapter_id,
            title="Am Hafen",
            body="Der Nebel kam von See.",
            setting="Hafen bei Nacht",
            story_time="Dritte Stunde nach Mitternacht",
        )
        reloaded = await client.get(f"/api/writing/scenes/{scene['id']}")
    assert reloaded.status_code == 200
    body = reloaded.json()
    assert body["title"] == "Am Hafen"
    assert body["body"] == "Der Nebel kam von See."
    assert body["setting"] == "Hafen bei Nacht"
    assert body["story_time"] == "Dritte Stunde nach Mitternacht"
    assert body["word_count"] == 5


async def test_a_created_scene_title_is_trimmed() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(client, chapter_id, title="  Wald  ")
    assert scene["title"] == "Wald"


async def test_a_whitespace_scene_title_is_the_placeholder_state() -> None:
    """The empty title is stored as "" — the localized placeholder is a
    rendering of it, never a label the column tells."""
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(client, chapter_id, title="   ")
        reloaded = await client.get(f"/api/writing/scenes/{scene['id']}")
    assert scene["title"] == ""
    assert reloaded.json()["title"] == ""


async def test_a_scene_can_return_to_untitled() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(client, chapter_id, title="Am Hafen")
        cleared = await client.put(f"/api/writing/scenes/{scene['id']}", json={"title": ""})
        reloaded = await client.get(f"/api/writing/scenes/{scene['id']}")
    assert cleared.status_code == 200
    assert reloaded.json()["title"] == ""


async def test_an_over_long_scene_title_is_refused() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        refused = await client.post(
            f"/api/writing/chapters/{chapter_id}/scenes", json={"title": "x" * 201}
        )
    assert refused.status_code == 422


# --- Update: present-only, the nullable labels clearable ------------------


async def test_update_changes_only_the_carried_fields() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(
            client, chapter_id, title="Alt", body="Prosa.", setting="Ort", story_time="Zeit"
        )
        renamed = await client.put(f"/api/writing/scenes/{scene['id']}", json={"title": "Neu"})
        reloaded = await client.get(f"/api/writing/scenes/{scene['id']}")
    assert renamed.status_code == 200
    body = reloaded.json()
    assert body["title"] == "Neu"
    assert body["body"] == "Prosa."
    assert body["setting"] == "Ort"
    assert body["story_time"] == "Zeit"


async def test_a_carried_null_clears_a_label() -> None:
    """setting/story_time are present-and-nullable: a carried null is the
    honest unset, an absent field is no change (the NovelUpdate rule)."""
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(client, chapter_id, setting="Ort", story_time="Zeit")
        cleared = await client.put(
            f"/api/writing/scenes/{scene['id']}", json={"setting": None, "story_time": None}
        )
        reloaded = await client.get(f"/api/writing/scenes/{scene['id']}")
    assert cleared.status_code == 200
    assert reloaded.json()["setting"] is None
    assert reloaded.json()["story_time"] is None


async def test_an_absent_label_is_unchanged() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(client, chapter_id, setting="Ort")
        await client.put(f"/api/writing/scenes/{scene['id']}", json={"body": "Neue Prosa."})
        reloaded = await client.get(f"/api/writing/scenes/{scene['id']}")
    assert reloaded.json()["setting"] == "Ort"
    assert reloaded.json()["body"] == "Neue Prosa."


async def test_a_blank_label_folds_to_unset() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(client, chapter_id, setting="  ", story_time=" Ort ")
        reloaded = await client.get(f"/api/writing/scenes/{scene['id']}")
    assert reloaded.json()["setting"] is None
    assert reloaded.json()["story_time"] == "Ort"


async def test_a_scene_body_update_persists_and_recounts() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(client, chapter_id, body="eins zwei")
        saved = await client.put(
            f"/api/writing/scenes/{scene['id']}", json={"body": "eins zwei drei"}
        )
    assert saved.status_code == 200
    assert saved.json()["body"] == "eins zwei drei"
    assert saved.json()["word_count"] == 3


async def test_an_over_long_setting_is_refused() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(client, chapter_id)
        refused = await client.put(
            f"/api/writing/scenes/{scene['id']}", json={"setting": "x" * 201}
        )
    assert refused.status_code == 422


# --- Delete: always allowed, the gap closes (D16, D8) ---------------------


async def test_delete_removes_the_scene_and_renumbers_survivors() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scenes = await _three_scenes(client, chapter_id)
        deleted = await client.delete(f"/api/writing/scenes/{scenes[1]['id']}")
        listed = await client.get(f"/api/writing/chapters/{chapter_id}/scenes")
    assert deleted.status_code == 204
    assert [scene["title"] for scene in listed.json()] == ["Ankunft", "Abfahrt"]
    assert [scene["position"] for scene in listed.json()] == [1, 2]


async def test_delete_keeps_the_survivors_updated_at() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scenes = await _three_scenes(client, chapter_id)
        await client.delete(f"/api/writing/scenes/{scenes[1]['id']}")
        for scene in (scenes[0], scenes[2]):
            reloaded = await client.get(f"/api/writing/scenes/{scene['id']}")
            # the number moved; the "last written" did not (D8)
            assert reloaded.json()["updated_at"] == scene["updated_at"]


async def test_delete_advances_the_novel_timestamp() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        chapter_id = await _create_chapter(client, novel_id)
        scenes = await _three_scenes(client, chapter_id)
        before = datetime.fromisoformat(
            (await client.get(f"/api/writing/novels/{novel_id}")).json()["updated_at"]
        )
        await client.delete(f"/api/writing/scenes/{scenes[1]['id']}")
        after = datetime.fromisoformat(
            (await client.get(f"/api/writing/novels/{novel_id}")).json()["updated_at"]
        )
    assert after > before


async def test_the_last_scene_can_be_deleted_an_empty_chapter_is_real() -> None:
    """D16: an empty chapter is a real state — the last scene may go, and
    the chapter reads honestly at zero, never a refused delete."""
    async with _client() as client:
        novel_id = await _create_novel(client)
        chapter_id = await _create_chapter(client, novel_id)
        scene = await _create_scene(client, chapter_id, body="eins zwei drei")
        deleted = await client.delete(f"/api/writing/scenes/{scene['id']}")
        listed = await client.get(f"/api/writing/chapters/{chapter_id}/scenes")
        chapter = await client.get(f"/api/writing/chapters/{chapter_id}")
    assert deleted.status_code == 204
    assert listed.json() == []
    assert chapter.json()["scene_count"] == 0
    assert chapter.json()["word_count"] == 0


async def test_delete_answers_404_for_a_foreign_scene() -> None:
    scene_id = await _seed_foreign_scene()
    async with _client() as client:
        deleted = await client.delete(f"/api/writing/scenes/{scene_id}")
    assert deleted.status_code == 404
    assert deleted.json()["detail"] == "scene not found"
    async with Session() as session:
        kept = await session.scalar(
            text("SELECT count(*) FROM scenes WHERE id = :id"), {"id": scene_id}
        )
    assert kept == 1


async def test_delete_answers_404_for_a_never_known_scene() -> None:
    async with _client() as client:
        deleted = await client.delete(f"/api/writing/scenes/{uuid4()}")
    assert deleted.status_code == 404


# --- Scoping: the user boundary, one answer for absent and foreign --------


async def test_a_scene_cannot_be_added_to_another_users_chapter() -> None:
    _, chapter_id = await _seed_foreign_chapter()
    async with _client() as client:
        created = await client.post(
            f"/api/writing/chapters/{chapter_id}/scenes", json={"title": "Eindringen"}
        )
    assert created.status_code == 404
    assert created.json()["detail"] == "chapter not found"


async def test_list_scenes_answers_404_for_a_foreign_chapter() -> None:
    _, chapter_id = await _seed_foreign_chapter()
    async with _client() as client:
        listed = await client.get(f"/api/writing/chapters/{chapter_id}/scenes")
    assert listed.status_code == 404


async def test_another_users_scene_cannot_be_read() -> None:
    scene_id = await _seed_foreign_scene()
    async with _client() as client:
        read = await client.get(f"/api/writing/scenes/{scene_id}")
    assert read.status_code == 404


async def test_another_users_scene_cannot_be_saved() -> None:
    scene_id = await _seed_foreign_scene()
    async with _client() as client:
        saved = await client.put(f"/api/writing/scenes/{scene_id}", json={"body": "Überschrieben"})
    assert saved.status_code == 404
    async with Session() as session:
        body = await session.scalar(
            text("SELECT body FROM scenes WHERE id = :id"), {"id": scene_id}
        )
    assert body == ""


async def test_get_scene_answers_404_for_a_never_known_id() -> None:
    async with _client() as client:
        read = await client.get(f"/api/writing/scenes/{uuid4()}")
    assert read.status_code == 404


async def test_without_the_setup_user_scene_create_is_409() -> None:
    from sqlalchemy import delete

    from app.kernel.contracts.models import User

    async with Session() as session:
        await session.execute(delete(User).where(User.id == LOCAL_USER_ID))
        await session.commit()
    async with _client() as client:
        refused = await client.post(f"/api/writing/chapters/{uuid4()}/scenes", json={})
    assert refused.status_code == 409
    assert refused.json() == {"detail": "setup required"}


# --- Order: the whole set or a 409 naming the stored ids ------------------


async def test_reorder_rewrites_contiguously() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scenes = await _three_scenes(client, chapter_id)
        reordered = await client.put(
            f"/api/writing/chapters/{chapter_id}/scene-order",
            json={"ids": [scenes[2]["id"], scenes[0]["id"], scenes[1]["id"]]},
        )
        listed = await client.get(f"/api/writing/chapters/{chapter_id}/scenes")
    assert reordered.status_code == 204
    assert [scene["title"] for scene in listed.json()] == ["Abfahrt", "Ankunft", "Nacht"]
    assert [scene["position"] for scene in listed.json()] == [1, 2, 3]


async def test_reorder_keeps_each_rows_updated_at() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scenes = await _three_scenes(client, chapter_id)
        await client.put(
            f"/api/writing/chapters/{chapter_id}/scene-order",
            json={"ids": [scene["id"] for scene in reversed(scenes)]},
        )
        for scene in scenes:
            reloaded = await client.get(f"/api/writing/scenes/{scene['id']}")
            # an arrangement is not a write (D8)
            assert reloaded.json()["updated_at"] == scene["updated_at"]


async def test_reorder_advances_the_novel_timestamp() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        chapter_id = await _create_chapter(client, novel_id)
        scenes = await _three_scenes(client, chapter_id)
        before = datetime.fromisoformat(
            (await client.get(f"/api/writing/novels/{novel_id}")).json()["updated_at"]
        )
        await client.put(
            f"/api/writing/chapters/{chapter_id}/scene-order",
            json={"ids": [scene["id"] for scene in reversed(scenes)]},
        )
        after = datetime.fromisoformat(
            (await client.get(f"/api/writing/novels/{novel_id}")).json()["updated_at"]
        )
    assert after > before


async def test_reorder_refuses_a_missing_id_naming_the_stored_order() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scenes = await _three_scenes(client, chapter_id)
        # reorder once so the stored order differs from creation order
        stored = [scenes[2]["id"], scenes[0]["id"], scenes[1]["id"]]
        moved = await client.put(
            f"/api/writing/chapters/{chapter_id}/scene-order", json={"ids": stored}
        )
        assert moved.status_code == 204
        refused = await client.put(
            f"/api/writing/chapters/{chapter_id}/scene-order",
            json={"ids": [scenes[0]["id"], scenes[2]["id"]]},
        )
    assert refused.status_code == 409
    assert refused.json() == {"detail": {"code": "order_mismatch", "scene_ids": stored}}


async def test_reorder_refuses_an_extra_id() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scenes = await _three_scenes(client, chapter_id)
        refused = await client.put(
            f"/api/writing/chapters/{chapter_id}/scene-order",
            json={"ids": [scenes[0]["id"], scenes[1]["id"], scenes[2]["id"], str(uuid4())]},
        )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "order_mismatch"


async def test_reorder_refuses_a_foreign_id() -> None:
    foreign_scene = await _seed_foreign_scene()
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scenes = await _three_scenes(client, chapter_id)
        refused = await client.put(
            f"/api/writing/chapters/{chapter_id}/scene-order",
            json={"ids": [scenes[0]["id"], scenes[1]["id"], str(foreign_scene)]},
        )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "order_mismatch"
    # the refusal reached nothing beyond this chapter: the foreign row kept its place
    async with Session() as session:
        position = await session.scalar(
            text("SELECT position FROM scenes WHERE id = :id"), {"id": foreign_scene}
        )
    assert position == 1


async def test_reorder_refuses_a_duplicate_id() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scenes = await _three_scenes(client, chapter_id)
        refused = await client.put(
            f"/api/writing/chapters/{chapter_id}/scene-order",
            json={"ids": [scenes[0]["id"], scenes[1]["id"], scenes[2]["id"], scenes[1]["id"]]},
        )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "order_mismatch"


async def test_reorder_leaves_the_order_untouched_on_refusal() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        chapter_id = await _create_chapter(client, novel_id)
        scenes = await _three_scenes(client, chapter_id)
        novel_before = (await client.get(f"/api/writing/novels/{novel_id}")).json()
        refused = await client.put(
            f"/api/writing/chapters/{chapter_id}/scene-order",
            json={"ids": [scene["id"] for scene in reversed(scenes)] + [str(uuid4())]},
        )
        assert refused.status_code == 409
        for scene in scenes:
            reloaded = await client.get(f"/api/writing/scenes/{scene['id']}")
            assert reloaded.json()["position"] == scene["position"]
            assert reloaded.json()["updated_at"] == scene["updated_at"]
        novel_after = (await client.get(f"/api/writing/novels/{novel_id}")).json()
    assert novel_after["updated_at"] == novel_before["updated_at"]


async def test_reorder_an_empty_chapter_accepts_the_empty_whole() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        reordered = await client.put(
            f"/api/writing/chapters/{chapter_id}/scene-order", json={"ids": []}
        )
    assert reordered.status_code == 204


async def test_reorder_answers_404_for_a_never_known_chapter() -> None:
    async with _client() as client:
        refused = await client.put(f"/api/writing/chapters/{uuid4()}/scene-order", json={"ids": []})
    assert refused.status_code == 404
    assert refused.json()["detail"] == "chapter not found"


async def test_reorder_answers_404_for_a_foreign_chapter() -> None:
    _, chapter_id = await _seed_foreign_chapter()
    async with _client() as client:
        refused = await client.put(
            f"/api/writing/chapters/{chapter_id}/scene-order", json={"ids": []}
        )
    assert refused.status_code == 404


# --- Positions: the allocator under the book's lock (#521) ----------------


async def test_scenes_created_at_once_get_distinct_positions() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))

    async def create_one() -> int:
        async with _client() as client:
            response = await client.post(f"/api/writing/chapters/{chapter_id}/scenes", json={})
            return response.status_code

    codes = await asyncio.gather(*(create_one() for _ in range(8)))
    assert codes == [201] * 8
    async with _client() as client:
        listed = await client.get(f"/api/writing/chapters/{chapter_id}/scenes")
    assert [scene["position"] for scene in listed.json()] == list(range(1, 9))


# --- Derived reads: the one whitespace rule, scenes the source ------------


async def test_scene_word_count_follows_the_shelves_whitespace_rule() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        near = chr(0x00A0) + "zwei" + chr(0x2007) + "drei" + chr(0x202F) + "vier"
        scene = await _create_scene(client, chapter_id, body="  eins" + near + "  ")
        empty = await _create_scene(client, chapter_id, body=chr(0x3000) + " \t")
    assert scene["word_count"] == 4
    assert empty["word_count"] == 0


async def test_chapter_read_carries_scene_count_and_word_count() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        chapter_id = await _create_chapter(client, novel_id)
        await _create_scene(client, chapter_id, body="eins zwei drei")
        await _create_scene(client, chapter_id, body="vier")
        chapter = await client.get(f"/api/writing/chapters/{chapter_id}")
        listed = await client.get(f"/api/writing/novels/{novel_id}/chapters")
    assert chapter.json()["scene_count"] == 2
    assert chapter.json()["word_count"] == 4
    assert listed.json()[0]["scene_count"] == 2
    assert listed.json()[0]["word_count"] == 4


async def test_an_empty_chapter_reads_honestly() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        chapter_id = await _create_chapter(client, novel_id)
        chapter = await client.get(f"/api/writing/chapters/{chapter_id}")
        listed = await client.get(f"/api/writing/novels/{novel_id}/chapters")
    assert chapter.json()["scene_count"] == 0
    assert chapter.json()["word_count"] == 0
    assert listed.json()[0]["scene_count"] == 0
    assert listed.json()[0]["word_count"] == 0


async def test_chapter_word_count_tracks_a_scene_write() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        chapter_id = await _create_chapter(client, novel_id)
        scene = await _create_scene(client, chapter_id, body="eins zwei")
        await client.put(f"/api/writing/scenes/{scene['id']}", json={"body": "eins zwei drei"})
        chapter = await client.get(f"/api/writing/chapters/{chapter_id}")
    assert chapter.json()["word_count"] == 3


async def test_novel_word_count_sums_the_scenes_across_chapters() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        first = await _create_chapter(client, novel_id, "Ankunft")
        second = await _create_chapter(client, novel_id, "Die Stadt")
        await _create_scene(client, first, body="eins zwei drei")
        await _create_scene(client, second, body="vier fünf")
        await _create_scene(client, second, body="sechs")
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        listed = await client.get("/api/writing/novels")
    assert fetched.json()["word_count"] == 6
    assert fetched.json()["chapter_count"] == 2
    row = next(novel for novel in listed.json() if novel["id"] == novel_id)
    assert row["word_count"] == 6


async def test_a_chapter_with_no_scenes_contributes_no_words() -> None:
    """The interim chapters.body is no longer the source: a chapter whose
    prose lives only in the old column reads zero until scenes carry it."""
    async with _client() as client:
        novel_id = await _create_novel(client)
        chapter_id = await _create_chapter(client, novel_id)
    async with Session() as session:
        await session.execute(
            text("UPDATE chapters SET body = 'alte Prosa hier' WHERE id = :id"),
            {"id": UUID(chapter_id)},
        )
        await session.commit()
    async with _client() as client:
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        chapter = await client.get(f"/api/writing/chapters/{chapter_id}")
    assert fetched.json()["word_count"] == 0
    assert chapter.json()["word_count"] == 0


# --- Activity: the ledger follows the prose onto scenes -------------------


async def _today_words(client: AsyncClient) -> int:
    response = await client.get("/api/writing/activity")
    assert response.status_code == 200
    return response.json()["today_words"]


async def test_scene_create_with_prose_feeds_the_activity() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        assert await _today_words(client) == 0
        await _create_scene(client, chapter_id, body="eins zwei drei")
        assert await _today_words(client) == 3


async def test_an_empty_scene_create_records_no_activity() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        await _create_scene(client, chapter_id)
        assert await _today_words(client) == 0


async def test_scene_update_counts_the_diff_not_the_total() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(client, chapter_id, body="eins zwei drei")
        await client.put(
            f"/api/writing/scenes/{scene['id']}", json={"body": "eins zwei drei vier fünf"}
        )
        assert await _today_words(client) == 5
        await client.put(f"/api/writing/scenes/{scene['id']}", json={"body": "eins"})
        assert await _today_words(client) == 1


async def test_a_title_only_scene_edit_records_no_activity() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(client, chapter_id, body="eins zwei")
        await client.put(f"/api/writing/scenes/{scene['id']}", json={"title": "Neu"})
        assert await _today_words(client) == 2


async def test_scene_delete_counts_negative() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client, await _create_novel(client))
        scene = await _create_scene(client, chapter_id, body="eins zwei drei")
        await client.delete(f"/api/writing/scenes/{scene['id']}")
        assert await _today_words(client) == 0


async def test_chapter_delete_accounts_its_scenes_words() -> None:
    """The cascade takes the scenes; the day loses the words they held —
    the sum across the chapter's scenes, not the interim chapter body."""
    async with _client() as client:
        novel_id = await _create_novel(client)
        chapter_id = await _create_chapter(client, novel_id)
        await _create_scene(client, chapter_id, body="eins zwei")
        await _create_scene(client, chapter_id, body="drei vier fünf")
        assert await _today_words(client) == 5
        deleted = await client.delete(f"/api/writing/chapters/{chapter_id}")
        assert deleted.status_code == 204
        assert await _today_words(client) == 0
