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
from app.kernel.llm.contract import DONE, CompletionEvent, CompletionRequest, Delta

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")

CHAPTER_BODY = (
    "Mira betrat das alte Haus am See. Der Leuchtturm schwieg, und Nebel zog über das Dorf."
)


def _client() -> AsyncClient:
    """Create an HTTP client that drives the real application through ASGI."""
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


async def _enqueue_extraction(client: AsyncClient, novel_id: str, chapter_id: str) -> str:
    """Enqueue one extraction run, asserting the contract's 202.

    Every test expecting the 202 goes through here, so a refusal is caught as
    the wrong status where it happens — not later as a KeyError on a body
    that never carried a job id.
    """
    response = await client.post(
        f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": chapter_id}
    )
    assert response.status_code == 202
    return response.json()["job_id"]


class _GarbageProvider:
    """A provider whose answer is not JSON: the malformed-answer path.

    It sits exactly where the real one does — behind the provider boundary —
    so everything below the boundary runs the real code."""

    def describe(self) -> str:
        """Identify the provider that emits an invalid extraction answer."""
        return "garbage"

    def configuration_problems(self) -> list[str]:
        """Report that this deterministic provider needs no configuration."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Yield non-JSON prose followed by DONE to exercise answer validation."""
        yield Delta(text="Der Nebel hob sich — aber kein JSON.")
        yield DONE


class _NoEntitiesProvider:
    """A provider whose answer is the empty array: a chapter without entities.

    The prompt promises an empty array is a valid answer; this provider sits
    behind the boundary like the real one, so everything below runs the real
    code."""

    def describe(self) -> str:
        """Identify the provider that reports no extracted entities."""
        return "empty"

    def configuration_problems(self) -> list[str]:
        """Report that this deterministic provider needs no configuration."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Yield a valid empty entity array followed by DONE."""
        yield Delta(text='{"items": []}')
        yield DONE


class _RecordingProvider:
    """A provider that answers with a fixed valid array and keeps what it was asked."""

    def __init__(self, answer: str = '{"items": []}') -> None:
        self.answer = answer
        self.requests: list[CompletionRequest] = []

    def describe(self) -> str:
        """Identify the provider that records its prompts."""
        return "recording"

    def configuration_problems(self) -> list[str]:
        """Report that this deterministic provider needs no configuration."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Record the request and answer with the fixed array."""
        self.requests.append(request)
        yield Delta(text=self.answer)
        yield DONE


async def _write_body(client: AsyncClient, chapter_id: str, body: str) -> None:
    """Replace a chapter's body the way the editor does, before enqueueing."""
    response = await client.put(f"/api/writing/chapters/{chapter_id}", json={"body": body})
    assert response.status_code == 200


async def test_a_long_body_is_cut_at_the_limit_and_reported_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A body over the bound reaches the provider cut, and the row says so."""
    import app.capabilities.knowledge.jobs as jobs

    provider = _RecordingProvider()
    monkeypatch.setattr(jobs, "get_provider", lambda: provider)
    async with _client() as client:
        novel_id, chapter_id = await _chapter(client)
        await _write_body(client, chapter_id, "x" * 20_001)
        job_id = await _enqueue_extraction(client, novel_id, chapter_id)
        assert await _run_lane_once() is True
        done = (await client.get(f"/api/jobs/{job_id}")).json()

    assert done["result"] == {"suggestions": 0, "truncated": True}
    sent = provider.requests[0].messages[0].content
    assert "x" * 20_000 in sent
    assert "x" * 20_001 not in sent


async def test_a_body_at_the_limit_is_sent_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bound is inclusive: exactly 20 000 characters are not a truncation."""
    import app.capabilities.knowledge.jobs as jobs

    provider = _RecordingProvider()
    monkeypatch.setattr(jobs, "get_provider", lambda: provider)
    async with _client() as client:
        novel_id, chapter_id = await _chapter(client)
        await _write_body(client, chapter_id, "x" * 20_000)
        job_id = await _enqueue_extraction(client, novel_id, chapter_id)
        assert await _run_lane_once() is True
        done = (await client.get(f"/api/jobs/{job_id}")).json()

    assert done["result"] == {"suggestions": 0, "truncated": False}
    assert "x" * 20_000 in provider.requests[0].messages[0].content


async def test_the_limit_counts_characters_not_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """20 000 two-byte characters are 20 000 characters, not a truncation."""
    import app.capabilities.knowledge.jobs as jobs

    provider = _RecordingProvider()
    monkeypatch.setattr(jobs, "get_provider", lambda: provider)
    async with _client() as client:
        novel_id, chapter_id = await _chapter(client)
        await _write_body(client, chapter_id, "é" * 20_000)
        job_id = await _enqueue_extraction(client, novel_id, chapter_id)
        assert await _run_lane_once() is True
        done = (await client.get(f"/api/jobs/{job_id}")).json()

    assert done["result"] == {"suggestions": 0, "truncated": False}
    assert provider.requests[0].messages[0].content.count("é") == 20_000


async def test_extraction_enqueues_then_the_worker_files_suggestions() -> None:
    """Verify queued extraction commits suggestions, completed progress, and a successful audit."""
    async with _client() as client:
        novel_id, chapter_id = await _chapter(client)
        job_id = await _enqueue_extraction(client, novel_id, chapter_id)

        # The request only enqueued: the row sits queued until the lane claims it.
        status = await client.get(f"/api/jobs/{job_id}")
        assert status.status_code == 200
        assert status.json()["status"] == "queued"
        assert status.json()["kind"] == "extract-entities"

        assert await _run_lane_once() is True

        done = (await client.get(f"/api/jobs/{job_id}")).json()
        assert done["status"] == "done"
        # The cross-layer scale pin: progress is a 0-100 integer because the
        # UI's JobStatus divides it by 100 for its percent — a done job sits
        # at the top of that scale, never outside it.
        assert 0 <= done["progress"] <= 100
        assert done["progress"] == 100
        assert done["result"] == {"suggestions": 3, "truncated": False}
        assert done["error"] is None

        pending = await client.get(f"/api/knowledge/novels/{novel_id}/suggestions")
        assert pending.status_code == 200
        suggestions = pending.json()
        assert [suggestion["name"] for suggestion in suggestions] == ["Mira", "Haus", "See"]
        assert [suggestion["type"] for suggestion in suggestions] == [
            "character",
            "location",
            "faction",
        ]
        assert all(suggestion["status"] == "pending" for suggestion in suggestions)

        # The audit row (plan §3.4): the call itself is recorded on the
        # handler's own commit — task, novel, tokens, status, NULL cost (D5).
        async with Session() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT task_key, novel_id, provider_kind, model, input_tokens,"
                        " output_tokens, status, cost_usd FROM llm_calls"
                    )
                )
            ).one()
        assert row.task_key == "knowledge.extract-entities"
        assert str(row.novel_id) == novel_id
        assert row.provider_kind == "fake"
        assert row.model == "fake"
        assert row.input_tokens > 0
        assert row.output_tokens > 0
        assert row.status == "ok"
        assert row.cost_usd is None


async def test_a_malformed_answer_fails_the_job_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify invalid output exhausts retries without suggestions, entities, or audit rows."""
    import app.capabilities.knowledge.jobs as jobs

    monkeypatch.setattr(jobs, "get_provider", lambda: _GarbageProvider())

    async with _client() as client:
        novel_id, chapter_id = await _chapter(client)
        job_id = await _enqueue_extraction(client, novel_id, chapter_id)

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
        calls = await session.scalar(text("SELECT count(*) FROM llm_calls"))
    assert suggestions == 0
    assert entities == 0
    assert calls == 0  # a failed job writes no audit row (D3)


async def test_an_empty_entity_array_is_a_valid_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an empty provider array completes with zero suggestions."""
    # The prompt promises "an empty array is a valid answer": no entities is
    # a done job with an honest zero, not a failure and not a silent skip.
    import app.capabilities.knowledge.jobs as jobs

    monkeypatch.setattr(jobs, "get_provider", lambda: _NoEntitiesProvider())

    async with _client() as client:
        novel_id, chapter_id = await _chapter(client)
        job_id = await _enqueue_extraction(client, novel_id, chapter_id)

        assert await _run_lane_once() is True

        done = (await client.get(f"/api/jobs/{job_id}")).json()
        assert done["status"] == "done"
        assert done["result"] == {"suggestions": 0, "truncated": False}
        assert done["error"] is None

    async with Session() as session:
        suggestions = await session.scalar(text("SELECT count(*) FROM entity_suggestions"))
    assert suggestions == 0


async def test_extraction_refuses_a_chapter_that_is_not_the_novels() -> None:
    """Verify mismatched and unknown chapter IDs return HTTP 404 without enqueueing jobs."""
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
    """Verify entity parsing rejects invalid shapes, types, and names over the column limit."""
    from app.capabilities.knowledge.jobs import MalformedAnswerError, parse_entities

    good = '{"items": [{"name": "Mira", "type": "character", "description": "Die Erzählerin."}]}'
    [entity] = parse_entities(good)
    assert entity.name == "Mira"
    assert entity.type == "character"
    assert entity.description == "Die Erzählerin."

    with pytest.raises(MalformedAnswerError):
        parse_entities("Der Nebel hob sich — aber kein JSON.")
    with pytest.raises(MalformedAnswerError):
        parse_entities('{"name": "Mira", "type": "character"}')  # no items array
    with pytest.raises(MalformedAnswerError):
        parse_entities('[{"name": "Mira"}]')  # a bare array: not a legal root
    with pytest.raises(MalformedAnswerError):
        parse_entities('{"items": [{"type": "character", "description": "Namenslos."}]}')  # no name
    with pytest.raises(MalformedAnswerError):
        parse_entities(
            '{"items": [{"name": "Mira", "type": "idea", "description": "?"}]}'
        )  # no such type
    with pytest.raises(MalformedAnswerError):
        parse_entities('{"items": ["Mira"]}')  # a string, not an object

    # The name column is String(200): a name of exactly that width parses,
    # and a longer one is refused on the contract path — not by the database,
    # whose verdict would arrive as a DataError after the fact.
    [widest] = parse_entities(f'{{"items": [{{"name": "{"N" * 200}", "type": "character"}}]}}')
    assert widest.name == "N" * 200
    with pytest.raises(MalformedAnswerError) as refused:
        parse_entities(f'{{"items": [{{"name": "{"N" * 201}", "type": "character"}}]}}')
    # The refusal carries the name's true length: the repr clips the shown
    # item at 200 characters, so the count is what keeps an over-long name
    # diagnosable — 201 is a boundary slip, 2000 is a broken prompt.
    assert "an item's name is 201 characters" in str(refused.value)


async def test_a_rerun_stacks_nothing_and_a_consumed_row_files_fresh() -> None:
    """The dedupe ruling: only a pending row blocks, and it blocks its own key.

    A re-run — the outage retry's shape, a second job on the same chapter
    after the first settled — skips a parsed entity whose (chapter, name,
    kind) is already pending, so the queue answers with one card set. The
    skip reads only pending rows, which is the asymmetry: accept consumes
    the row, and the same re-run is then allowed to ask again — the
    consumed key files fresh.
    """
    async with _client() as client:
        novel_id, chapter_id = await _chapter(client)

        await _enqueue_extraction(client, novel_id, chapter_id)
        assert await _run_lane_once() is True
        # The re-run on the same chapter: three parsed entities, all three
        # already pending — none of them files a second row.
        await _enqueue_extraction(client, novel_id, chapter_id)
        assert await _run_lane_once() is True

        first = (await client.get(f"/api/knowledge/novels/{novel_id}/suggestions")).json()
        assert [row["name"] for row in first] == ["Mira", "Haus", "See"]

        # The asymmetry's proof: accept consumes Mira's row, so the re-run
        # files her fresh — a new pending row, not the consumed one back.
        accepted = await client.post(f"/api/knowledge/suggestions/{first[0]['id']}/accept")
        assert accepted.status_code == 200

        await _enqueue_extraction(client, novel_id, chapter_id)
        assert await _run_lane_once() is True

        # The fresh Mira row files after the two that never left, so the
        # queue's created_at order answers Haus, See first — the pin is the
        # set, not the sequence.
        after = (await client.get(f"/api/knowledge/novels/{novel_id}/suggestions")).json()
        assert sorted(row["name"] for row in after) == ["Haus", "Mira", "See"]
        assert first[0]["id"] not in [row["id"] for row in after]  # fresh, not resurrected


async def test_another_users_job_is_not_visible() -> None:
    """Verify the jobs API hides a job belonging to another user."""
    from app.kernel.jobs import enqueue

    await seed_user(OTHER_USER)
    async with Session() as session:
        other_job = await enqueue(session, OTHER_USER, "extract-entities", {"chapter_id": "x"})
        await session.commit()

    async with _client() as client:
        response = await client.get(f"/api/jobs/{other_job.id}")
    assert response.status_code == 404
