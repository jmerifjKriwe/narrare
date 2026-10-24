"""Entity extraction: the first job on the lane, from enqueue to suggestions.

The request only enqueues (D14) — the provider call happens in the worker's
handler, on the handler's own transaction. A malformed model answer fails the
job loudly and writes nothing: no half-written review queue.
"""

from collections.abc import AsyncIterator  # noqa: TC003
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")

CHAPTER_BODY = (
    "Mira betrat das alte Haus am See. Der Leuchtturm schwieg, und Nebel zog über das Dorf."
)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _chapter(client: AsyncClient, title: str = "Der Nebel") -> tuple[str, str]:
    """A novel with one written chapter, both the caller's own."""
    novel = await client.post("/api/writing/novels", json={"title": title})
    chapter = await client.post(
        f"/api/writing/novels/{novel.json()['id']}/chapters", json={"title": "Ankunft"}
    )
    chapter_id = chapter.json()["id"]
    await client.put(f"/api/writing/chapters/{chapter_id}", json={"body": CHAPTER_BODY})
    return novel.json()["id"], chapter_id


async def _run_lane_once() -> bool:
    """One claim of the lane, the way the api app's task would run it."""
    from app.capabilities.knowledge.jobs import handlers
    from app.kernel.jobs.worker import Worker

    return await Worker(Session, handlers).run_once()


class _GarbageProvider:
    """A provider whose answer is not JSON: the malformed-answer path.

    It sits exactly where the real one does — behind the provider boundary —
    so everything below the boundary runs the real code."""

    def describe(self) -> str:
        return "garbage"

    def configuration_problems(self) -> list[str]:
        return []

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        yield "Der Nebel hob sich — aber kein JSON."


async def test_extraction_enqueues_then_the_worker_files_suggestions() -> None:
    async with _client() as client:
        novel_id, chapter_id = await _chapter(client)
        response = await client.post(
            f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": chapter_id}
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # The request only enqueued: the row sits queued until the lane claims it.
        status = await client.get(f"/api/jobs/{job_id}")
        assert status.status_code == 200
        assert status.json()["status"] == "queued"
        assert status.json()["kind"] == "extract-entities"

        assert await _run_lane_once() is True

        done = (await client.get(f"/api/jobs/{job_id}")).json()
        assert done["status"] == "done"
        assert done["progress"] == 100  # 0-100, the handler's report
        assert done["result"] == {"suggestions": 3}
        assert done["error"] is None

        pending = await client.get(f"/api/knowledge/novels/{novel_id}/suggestions")
        assert pending.status_code == 200
        suggestions = pending.json()
        assert [suggestion["name"] for suggestion in suggestions] == ["Mira", "Haus", "See"]
        assert [suggestion["kind"] for suggestion in suggestions] == [
            "character",
            "place",
            "thing",
        ]
        assert all(suggestion["status"] == "pending" for suggestion in suggestions)


async def test_a_malformed_answer_fails_the_job_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.capabilities.knowledge.jobs as jobs

    monkeypatch.setattr(jobs, "get_provider", lambda: _GarbageProvider())

    async with _client() as client:
        novel_id, chapter_id = await _chapter(client)
        accepted = await client.post(
            f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": chapter_id}
        )
        job_id = accepted.json()["job_id"]

        # The failure earns exactly one re-run (MAX_ATTEMPTS = 2), then fails.
        assert await _run_lane_once() is True
        assert await _run_lane_once() is True
        assert await _run_lane_once() is False  # nothing queued anymore

        job = (await client.get(f"/api/jobs/{job_id}")).json()
        assert job["status"] == "failed"
        assert job["error"] is not None
        assert "JSON" in job["error"] or "json" in job["error"]
        assert job["result"] is None

    async with Session() as session:
        suggestions = await session.scalar(text("SELECT count(*) FROM entity_suggestions"))
        entities = await session.scalar(text("SELECT count(*) FROM entities"))
    assert suggestions == 0
    assert entities == 0


async def test_extraction_refuses_a_chapter_that_is_not_the_novels() -> None:
    async with _client() as client:
        novel_id, _ = await _chapter(client, title="Erster Roman")
        _, other_chapter_id = await _chapter(client, title="Zweiter Roman")

        wrong_novel = await client.post(
            f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": other_chapter_id}
        )
        assert wrong_novel.status_code == 404

        unknown = await client.post(
            f"/api/knowledge/extraction/{novel_id}",
            json={"chapter_id": "00000000-0000-0000-0000-0000000000ff"},
        )
        assert unknown.status_code == 404

    async with Session() as session:
        jobs_count = await session.scalar(text("SELECT count(*) FROM jobs"))
    assert jobs_count == 0  # a refusal enqueues nothing


async def test_the_parse_refuses_answers_that_are_not_the_contracted_shape() -> None:
    from app.capabilities.knowledge.jobs import MalformedAnswerError, parse_entities

    good = '[{"name": "Mira", "kind": "character", "description": "Die Erzählerin."}]'
    [entity] = parse_entities(good)
    assert entity.name == "Mira"
    assert entity.kind == "character"
    assert entity.description == "Die Erzählerin."

    with pytest.raises(MalformedAnswerError):
        parse_entities("Der Nebel hob sich — aber kein JSON.")
    with pytest.raises(MalformedAnswerError):
        parse_entities('{"name": "Mira", "kind": "character"}')  # an object, not an array
    with pytest.raises(MalformedAnswerError):
        parse_entities('[{"kind": "character", "description": "Namenslos."}]')  # no name
    with pytest.raises(MalformedAnswerError):
        parse_entities('[{"name": "Mira", "kind": "idea", "description": "?"}]')  # no such kind
    with pytest.raises(MalformedAnswerError):
        parse_entities('["Mira"]')  # a string, not an object


async def test_another_users_job_is_not_visible() -> None:
    from app.kernel.jobs import enqueue

    await seed_user(OTHER_USER)
    async with Session() as session:
        other_job = await enqueue(session, OTHER_USER, "extract-entities", {"chapter_id": "x"})
        await session.commit()

    async with _client() as client:
        response = await client.get(f"/api/jobs/{other_job.id}")
    assert response.status_code == 404
