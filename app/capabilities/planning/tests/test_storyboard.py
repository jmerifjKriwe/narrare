"""The storyboard substrate: structure-aware chapter grouping with sync.

GET assembles stages from the structure registry, chapter positions and the
writer's assignments — suggested stages are computed, never persisted. PUT
moves one chapter to a stage of the current structure. POST remap previews
the mapping onto another structure without writing, or applies exactly that
mapping plus the novel setting in one transaction. A foreign novel reads as
missing (404); an unknown chapter, stage or structure is a 422 that writes
nothing; writes without the setup-created user are 409.
"""

from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.main import app
from app.capabilities.planning.models import ChapterStage, PlanningNovelSettings
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chapter, Novel, User
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = uuid4()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _novel(client: AsyncClient, title: str = "Der Nebel") -> str:
    novel = await client.post("/api/writing/novels", json={"title": title})
    assert novel.status_code == 201
    return novel.json()["id"]


async def _chapter(client: AsyncClient, novel_id: str, title: str, body: str = "") -> str:
    created = await client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": title})
    assert created.status_code == 201
    chapter_id = created.json()["id"]
    if body:
        saved = await client.put(f"/api/writing/chapters/{chapter_id}", json={"body": body})
        assert saved.status_code == 200
    return chapter_id


async def _scenes(client: AsyncClient, novel_id: str, chapter_id: str, *statuses: str) -> None:
    scenes: list[dict[str, object]] = [
        {
            "id": str(uuid4()),
            "title": f"Szene {index}",
            "purpose": "",
            "conflict": "",
            "resolution": "",
            "beats": [],
            "status": status,
        }
        for index, status in enumerate(statuses)
    ]
    saved = await client.put(
        f"/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes", json={"scenes": scenes}
    )
    assert saved.status_code == 200


def _storyboard(novel_id: str) -> str:
    return f"/api/planning/novels/{novel_id}/storyboard"


def _stage(novel_id: str, chapter_id: str) -> str:
    return f"/api/planning/novels/{novel_id}/chapters/{chapter_id}/stage"


def _remap(novel_id: str) -> str:
    return f"/api/planning/novels/{novel_id}/remap"


def _chapters_by_title(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {chapter["title"]: chapter for stage in body["stages"] for chapter in stage["chapters"]}


async def _stored_stage_rows() -> int:
    async with Session() as session:
        stored = await session.scalar(select(func.count()).select_from(ChapterStage))
    return stored or 0


async def _stored_settings_rows() -> int:
    async with Session() as session:
        stored = await session.scalar(select(func.count()).select_from(PlanningNovelSettings))
    return stored or 0


async def test_empty_novel_suggests_without_assigning_and_writes_nothing() -> None:
    async with _client() as client:
        novel_id = await _novel(client)
        await _chapter(client, novel_id, "Ankunft")
        await _chapter(client, novel_id, "Abreise")
        await _chapter(client, novel_id, "Rückkehr")

        response = await client.get(_storyboard(novel_id))

        assert response.status_code == 200
        body = response.json()
        assert body["novel_id"] == novel_id
        assert body["structure_id"] == "three-act"
        assert [stage["key"] for stage in body["stages"]] == [
            "setup",
            "confrontation",
            "resolution",
        ]
        setup, confrontation, resolution = body["stages"]
        assert setup["from"] == 0.0 and setup["to"] == 0.25
        assert confrontation["from"] == 0.25 and confrontation["to"] == 0.75
        assert resolution["from"] == 0.75 and resolution["to"] == 1.0
        chapters = _chapters_by_title(body)
        assert chapters["Ankunft"]["stage_key"] == "setup"
        assert chapters["Ankunft"]["assignment_source"] == "suggested"
        assert chapters["Abreise"]["stage_key"] == "confrontation"
        assert chapters["Rückkehr"]["stage_key"] == "resolution"
        assert chapters["Abreise"]["assignment_source"] == "suggested"
        # The read is pure: suggested stages are computed, never persisted.
        assert await _stored_stage_rows() == 0
        assert await _stored_settings_rows() == 0


async def test_single_chapter_novel_suggests_the_first_stage() -> None:
    async with _client() as client:
        novel_id = await _novel(client)
        await _chapter(client, novel_id, "Anfang")

        body = (await client.get(_storyboard(novel_id))).json()

        assert _chapters_by_title(body)["Anfang"]["stage_key"] == "setup"


async def test_sync_statuses_follow_the_rule_priority() -> None:
    async with _client() as client:
        novel_id = await _novel(client)
        await _chapter(client, novel_id, "Leer")
        planned = await _chapter(client, novel_id, "Geplant")
        finished = await _chapter(client, novel_id, "Fertig")
        drifting = await _chapter(client, novel_id, "Abgewichen")
        await _chapter(client, novel_id, "Im Fluss", body="eins zwei drei")

        await _scenes(client, novel_id, planned, "planned")
        await _scenes(client, novel_id, finished, "complete", "complete")
        await _chapter(client, novel_id, "x")  # placeholder to shift positions
        finished_body = await client.put(
            f"/api/writing/chapters/{finished}", json={"body": "Wort für Wort"}
        )
        assert finished_body.status_code == 200
        await _scenes(client, novel_id, drifting, "complete")
        drifted_body = await client.put(
            f"/api/writing/chapters/{drifting}", json={"body": "noch mehr Worte hier"}
        )
        assert drifted_body.status_code == 200
        moved = await client.put(_stage(novel_id, drifting), json={"stage_key": "resolution"})
        assert moved.status_code == 200
        assert moved.json()["assignment_source"] == "assigned"

        body = (await client.get(_storyboard(novel_id))).json()
        chapters = _chapters_by_title(body)
        assert chapters["Leer"]["sync_status"] == "empty"
        assert chapters["Leer"]["word_count"] == 0
        assert chapters["Geplant"]["sync_status"] == "planned"
        assert chapters["Fertig"]["sync_status"] == "completed"
        assert chapters["Im Fluss"]["sync_status"] == "on_track"
        assert chapters["Im Fluss"]["word_count"] == 3
        assert chapters["Abgewichen"]["sync_status"] == "deviated"
        assert chapters["Abgewichen"]["stage_key"] == "resolution"
        assert chapters["Abgewichen"]["assignment_source"] == "assigned"


async def test_put_stage_persists_and_returns_the_assignment() -> None:
    async with _client() as client:
        novel_id = await _novel(client)
        chapter_id = await _chapter(client, novel_id, "Ankunft")

        response = await client.put(_stage(novel_id, chapter_id), json={"stage_key": "resolution"})

        assert response.status_code == 200
        assert response.json()["chapter_id"] == chapter_id
        assert response.json()["stage_key"] == "resolution"
        assert response.json()["assignment_source"] == "assigned"
        body = (await client.get(_storyboard(novel_id))).json()
        assert _chapters_by_title(body)["Ankunft"]["stage_key"] == "resolution"
        assert _chapters_by_title(body)["Ankunft"]["assignment_source"] == "assigned"
        assert await _stored_stage_rows() == 1


async def test_unknown_chapter_or_stage_is_422_and_writes_nothing() -> None:
    async with _client() as client:
        novel_id = await _novel(client)
        chapter_id = await _chapter(client, novel_id, "Ankunft")
        other_novel = await _novel(client, "Anderer Roman")
        other_chapter = await _chapter(client, other_novel, "Abreise")
        before = (await client.get(_storyboard(novel_id))).json()

        foreign_chapter = await client.put(
            _stage(novel_id, other_chapter), json={"stage_key": "setup"}
        )
        assert foreign_chapter.status_code == 422
        absent_chapter = await client.put(
            _stage(novel_id, str(uuid4())), json={"stage_key": "setup"}
        )
        assert absent_chapter.status_code == 422
        unknown_stage = await client.put(_stage(novel_id, chapter_id), json={"stage_key": "epilog"})
        assert unknown_stage.status_code == 422
        assert "stage" in unknown_stage.json()["detail"]

        # A refused PUT writes nothing: the refetched aggregate is unchanged.
        assert (await client.get(_storyboard(novel_id))).json() == before
        assert await _stored_stage_rows() == 0
        assert await _stored_settings_rows() == 0


async def test_foreign_novel_reads_as_missing() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        novel = Novel(user_id=OTHER_USER, title="Fremder Roman")
        session.add(novel)
        await session.flush()
        session.add(Chapter(user_id=OTHER_USER, novel_id=novel.id, title="Ankunft", position=0))
        await session.commit()
        foreign_novel = str(novel.id)
    async with _client() as client:
        own_novel = await _novel(client)
        own_chapter = await _chapter(client, own_novel, "Ankunft")

        assert (await client.get(_storyboard(foreign_novel))).status_code == 404
        assert (
            await client.put(_stage(foreign_novel, own_chapter), json={"stage_key": "setup"})
        ).status_code == 404
        assert (
            await client.post(_remap(foreign_novel), json={"structure_id": "heros-journey"})
        ).status_code == 404

        assert (await client.get(_storyboard(str(uuid4())))).status_code == 404


async def test_remap_preview_is_pure_and_confirm_writes_exactly_the_preview() -> None:
    async with _client() as client:
        novel_id = await _novel(client)
        await _chapter(client, novel_id, "Eins")
        await _chapter(client, novel_id, "Zwei")
        await _chapter(client, novel_id, "Drei")
        await _chapter(client, novel_id, "Vier")

        preview = await client.post(
            _remap(novel_id), json={"structure_id": "heros-journey", "confirm": False}
        )

        assert preview.status_code == 200
        assert preview.json()["confirmed"] is False
        assert preview.json()["structure_id"] == "heros-journey"
        assert [entry["to_stage"] for entry in preview.json()["mapping"]] == [
            "ordinary-world",
            "mentor",
            "ordeal",
            "return",
        ]
        assert all(entry["from_stage"] for entry in preview.json()["mapping"])
        # The preview writes nothing: no settings, no assignments.
        assert await _stored_stage_rows() == 0
        assert await _stored_settings_rows() == 0

        confirmed = await client.post(
            _remap(novel_id), json={"structure_id": "heros-journey", "confirm": True}
        )

        assert confirmed.status_code == 200
        assert confirmed.json()["confirmed"] is True
        assert confirmed.json()["mapping"] == preview.json()["mapping"]
        body = (await client.get(_storyboard(novel_id))).json()
        assert body["structure_id"] == "heros-journey"
        assert len(body["stages"]) == 12
        chapters = _chapters_by_title(body)
        for entry in confirmed.json()["mapping"]:
            match = next(
                chapter
                for chapter in chapters.values()
                if chapter["chapter_id"] == entry["chapter_id"]
            )
            assert match["stage_key"] == entry["to_stage"]
            assert match["assignment_source"] == "assigned"


async def test_unknown_structure_is_422_and_writes_nothing() -> None:
    async with _client() as client:
        novel_id = await _novel(client)
        await _chapter(client, novel_id, "Ankunft")
        before = (await client.get(_storyboard(novel_id))).json()

        refused = await client.post(
            _remap(novel_id), json={"structure_id": "save-the-cat", "confirm": True}
        )

        assert refused.status_code == 422
        assert "structure" in refused.json()["detail"]
        assert (await client.get(_storyboard(novel_id))).json() == before
        assert await _stored_stage_rows() == 0
        assert await _stored_settings_rows() == 0


async def test_writes_before_setup_are_409_and_reads_are_404() -> None:
    from sqlalchemy import delete

    async with Session() as session:
        await session.execute(delete(User).where(User.id == LOCAL_USER_ID))
        await session.commit()

    async with _client() as client:
        novel_id = str(uuid4())
        chapter_id = str(uuid4())

        assert (await client.get(_storyboard(novel_id))).status_code == 404
        assert (
            await client.put(_stage(novel_id, chapter_id), json={"stage_key": "setup"})
        ).status_code == 409
        assert (
            await client.post(
                _remap(novel_id), json={"structure_id": "heros-journey", "confirm": True}
            )
        ).status_code == 409

    async with Session() as session:
        assert await session.scalar(select(func.count()).select_from(ChapterStage)) == 0
        assert await session.scalar(select(func.count()).select_from(PlanningNovelSettings)) == 0
