"""Entity extraction: the first job on the lane, from enqueue to suggestions.

The request only enqueues (D14) — the provider call happens in the worker's
handler, on the handler's own transaction. A malformed model answer fails the
job loudly and writes nothing: no half-written review queue.
"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable  # noqa: TC003
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.api.main import app
from app.capabilities.knowledge.repository import EntityRepository
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chapter, Entity, EntitySuggestion, Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm.contract import DONE, CompletionEvent, CompletionRequest, Delta, TextProvider
from app.kernel.llm.resolution import ResolvedProvider

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")

CHAPTER_BODY = (
    "Mira betrat das alte Haus am See. Der Leuchtturm schwieg, und Nebel zog über das Dorf."
)


def _client() -> AsyncClient:
    """Create an HTTP client that drives the real application through ASGI."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _resolving(
    provider: TextProvider,
) -> Callable[[AsyncSession, UUID, str], Awaitable[ResolvedProvider]]:
    """A resolve_provider stand-in that always serves the scripted provider."""

    async def resolve(session: AsyncSession, user_id: UUID, task_key: str) -> ResolvedProvider:
        return ResolvedProvider(
            provider=provider,
            profile_id=None,
            kind="fake",
            model="fake",
            context_window=None,
            max_output_tokens=None,
            temperature=None,
            request_timeout=None,
            base_url=None,
            api_key=None,
        )

    return resolve


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
    monkeypatch.setattr(jobs, "resolve_provider", _resolving(provider))
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
    monkeypatch.setattr(jobs, "resolve_provider", _resolving(provider))
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
    monkeypatch.setattr(jobs, "resolve_provider", _resolving(provider))
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
        assert done["result"] == {"suggestions": 7, "truncated": False}
        assert done["error"] is None

        pending = await client.get(f"/api/knowledge/novels/{novel_id}/suggestions")
        assert pending.status_code == 200
        suggestions = pending.json()
        # The fake derives every distinct capitalized name the passage
        # offers, to the vocabulary's ceiling of eight — seven here, one
        # per type in the vocabulary's order.
        assert [suggestion["name"] for suggestion in suggestions] == [
            "Mira",
            "Haus",
            "See",
            "Der",
            "Leuchtturm",
            "Nebel",
            "Dorf",
        ]
        assert [suggestion["type"] for suggestion in suggestions] == [
            "character",
            "location",
            "faction",
            "object",
            "system",
            "timeline",
            "event",
        ]
        # the fake's derivation: entity i proposes related_to to entity (i+1),
        # the last wrapping to the first — deterministic off the same names.
        # The read shape names the pair target_name and relation_type.
        assert [suggestion["relations"] for suggestion in suggestions] == [
            [{"target_name": "Haus", "relation_type": "related_to"}],
            [{"target_name": "See", "relation_type": "related_to"}],
            [{"target_name": "Der", "relation_type": "related_to"}],
            [{"target_name": "Leuchtturm", "relation_type": "related_to"}],
            [{"target_name": "Nebel", "relation_type": "related_to"}],
            [{"target_name": "Dorf", "relation_type": "related_to"}],
            [{"target_name": "Mira", "relation_type": "related_to"}],
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
        # The fake kind is free by the truth table (design D4): 0.0, not unknown.
        assert row.cost_usd == 0.0


async def test_a_malformed_answer_fails_the_job_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify invalid output exhausts retries without suggestions, entities, or audit rows."""
    import app.capabilities.knowledge.jobs as jobs

    monkeypatch.setattr(jobs, "resolve_provider", _resolving(_GarbageProvider()))

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

    monkeypatch.setattr(jobs, "resolve_provider", _resolving(_NoEntitiesProvider()))

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

    good = (
        '{"items": [{"name": "Mira", "type": "character",'
        ' "description": "Die Erzählerin.", "relations": []}]}'
    )
    [entity] = parse_entities(good)
    assert entity.name == "Mira"
    assert entity.type == "character"
    assert entity.description == "Die Erzählerin."
    assert entity.relations == []

    with pytest.raises(MalformedAnswerError):
        parse_entities("Der Nebel hob sich — aber kein JSON.")
    with pytest.raises(MalformedAnswerError):
        parse_entities('{"name": "Mira", "type": "character"}')  # no items array
    with pytest.raises(MalformedAnswerError):
        parse_entities('[{"name": "Mira"}]')  # a bare array: not a legal root
    with pytest.raises(MalformedAnswerError):
        parse_entities(
            '{"items": [{"type": "character", "description": "Namenslos.", "relations": []}]}'
        )  # no name
    with pytest.raises(MalformedAnswerError):
        parse_entities(
            '{"items": [{"name": "Mira", "type": "idea", "description": "?", "relations": []}]}'
        )  # no such type
    with pytest.raises(MalformedAnswerError):
        parse_entities('{"items": ["Mira"]}')  # a string, not an object

    # The name column is String(200): a name of exactly that width parses,
    # and a longer one is refused on the contract path — not by the database,
    # whose verdict would arrive as a DataError after the fact.
    [widest] = parse_entities(
        f'{{"items": [{{"name": "{"N" * 200}", "type": "character", "relations": []}}]}}'
    )
    assert widest.name == "N" * 200
    with pytest.raises(MalformedAnswerError) as refused:
        parse_entities(
            f'{{"items": [{{"name": "{"N" * 201}", "type": "character", "relations": []}}]}}'
        )
    # The refusal carries the name's true length: the repr clips the shown
    # item at 200 characters, so the count is what keeps an over-long name
    # diagnosable — 201 is a boundary slip, 2000 is a broken prompt.
    assert "an item's name is 201 characters" in str(refused.value)


async def test_the_parse_reads_relations_and_refuses_their_malformed_forms() -> None:
    """Every item carries its relations: proposals parse into (target, type)
    pairs, and a missing or malformed one is a loud refusal — nothing is
    skipped silently, a bad answer fails the job."""
    from app.capabilities.knowledge.jobs import MalformedAnswerError, parse_entities
    from app.capabilities.knowledge.prompts import ParsedRelation

    good = (
        '{"items": [{"name": "Mira", "type": "character", "description": null,'
        ' "relations": [{"target": "Haus", "type": "bewohnt"}, {"target": "See", "type": "mag"}]}]}'
    )
    [entity] = parse_entities(good)
    assert entity.relations == [ParsedRelation("Haus", "bewohnt"), ParsedRelation("See", "mag")]

    # the boundary is inclusive: the name column's 200 for the target, the
    # relation column's 80 for the type
    [widest] = parse_entities(
        '{"items": [{"name": "Mira", "type": "character", "description": null,'
        f' "relations": [{{"target": "{"T" * 200}", "type": "{"R" * 80}"}}]}}]}}'
    )
    assert widest.relations == [ParsedRelation("T" * 200, "R" * 80)]

    def _item(relations: object) -> str:
        """One well-formed item whose relations array is replaced."""
        return json.dumps(
            {
                "items": [
                    {
                        "name": "Mira",
                        "type": "character",
                        "description": None,
                        "relations": relations,
                    }
                ]
            }
        )

    with pytest.raises(MalformedAnswerError):
        parse_entities(
            '{"items": [{"name": "Mira", "type": "character", "description": null}]}'
        )  # no relations at all
    with pytest.raises(MalformedAnswerError):
        parse_entities(_item("keine"))  # not an array
    with pytest.raises(MalformedAnswerError):
        parse_entities(_item(["Haus"]))  # a proposal is an object, not a string
    with pytest.raises(MalformedAnswerError):
        parse_entities(_item([{"type": "bewohnt"}]))  # no target
    with pytest.raises(MalformedAnswerError):
        parse_entities(_item([{"target": "", "type": "bewohnt"}]))  # a blank target
    with pytest.raises(MalformedAnswerError):
        parse_entities(_item([{"target": "   ", "type": "bewohnt"}]))  # whitespace only
    with pytest.raises(MalformedAnswerError):
        parse_entities(_item([{"target": 5, "type": "bewohnt"}]))  # not a string
    with pytest.raises(MalformedAnswerError):
        parse_entities(_item([{"target": "Haus"}]))  # no type
    with pytest.raises(MalformedAnswerError):
        parse_entities(_item([{"target": "Haus", "type": ""}]))  # a blank type
    with pytest.raises(MalformedAnswerError):
        parse_entities(_item([{"target": "Haus", "type": "   "}]))
    with pytest.raises(MalformedAnswerError):
        parse_entities(_item([{"target": "Haus", "type": 7}]))  # not a string
    with pytest.raises(MalformedAnswerError):
        parse_entities(_item([{"target": "T" * 201, "type": "bewohnt"}]))  # over the target width
    with pytest.raises(MalformedAnswerError):
        parse_entities(_item([{"target": "Haus", "type": "R" * 81}]))  # over the type width


async def test_a_rerun_stacks_nothing_and_a_consumed_row_files_fresh() -> None:
    """The dedupe ruling: only a pending row blocks, and it blocks its own key.

    A re-run — the outage retry's shape, a second job on the same chapter
    after the first settled — skips a parsed entity whose (chapter, name,
    type) is already pending, so the queue answers with one card set. The
    skip reads only pending rows, which is the asymmetry: accept consumes
    the row, and the same re-run is then allowed to ask again — the
    consumed key files fresh.
    """
    async with _client() as client:
        novel_id, chapter_id = await _chapter(client)

        await _enqueue_extraction(client, novel_id, chapter_id)
        assert await _run_lane_once() is True
        # The re-run on the same chapter: seven parsed entities, all seven
        # already pending — none of them files a second row.
        await _enqueue_extraction(client, novel_id, chapter_id)
        assert await _run_lane_once() is True

        first = (await client.get(f"/api/knowledge/novels/{novel_id}/suggestions")).json()
        assert [row["name"] for row in first] == [
            "Mira",
            "Haus",
            "See",
            "Der",
            "Leuchtturm",
            "Nebel",
            "Dorf",
        ]

        # The asymmetry's proof: accept consumes Mira's row, so the re-run
        # files her fresh — a new pending row, not the consumed one back.
        accepted = await client.post(f"/api/knowledge/suggestions/{first[0]['id']}/accept")
        assert accepted.status_code == 200

        await _enqueue_extraction(client, novel_id, chapter_id)
        assert await _run_lane_once() is True

        # The fresh Mira row files after the seven that were pending (the
        # six that never left plus her fresh one), so the queue's created_at
        # order answers the six first — the pin is the set, not the sequence.
        after = (await client.get(f"/api/knowledge/novels/{novel_id}/suggestions")).json()
        assert sorted(row["name"] for row in after) == sorted(
            ["Mira", "Haus", "See", "Der", "Leuchtturm", "Nebel", "Dorf"]
        )
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


# --- Accept's resolution (D8) -----------------------------------------------
#
# The proposals ride the suggestion; accept places every one whose target
# resolves — trimmed, case-insensitive exact match on names and aliases —
# and answers with the ones it could not place, never a silent drop. The
# tests seed the canon and the pending suggestions through the models: the
# parse and the fake's derivation are pinned above, these pin the placing.


async def _seed_canon(*rows: tuple[str, list[str]]) -> tuple[UUID, list[Entity]]:
    """A novel with canon entities of (name, aliases), through the repository.

    The repository is the one writer of search_text, so the seeds carry the
    derived column the same way accepted births do."""
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Die Auflösung")
        session.add(novel)
        await session.flush()
        repository = EntityRepository(session, LOCAL_USER_ID)
        created = [
            await repository.create(novel.id, name, "character", "", aliases, [])
            for name, aliases in rows
        ]
        await session.commit()
        return novel.id, created


async def _pending_proposal(
    novel_id: UUID, name: str, relations: list[dict[str, str]]
) -> EntitySuggestion:
    """A pending suggestion carrying proposals, beside its own chapter."""
    async with Session() as session:
        # One number per chapter is the table's rule now (#521); this fixture
        # gives each proposal its own chapter in the novel, so it appends.
        taken = await session.scalar(
            text("SELECT coalesce(max(position) + 1, 0) FROM chapters WHERE novel_id = :n"),
            {"n": novel_id},
        )
        chapter = Chapter(
            user_id=LOCAL_USER_ID, novel_id=novel_id, title="Ankunft", position=int(taken or 0)
        )
        session.add(chapter)
        await session.flush()
        suggestion = EntitySuggestion(
            user_id=LOCAL_USER_ID,
            novel_id=novel_id,
            chapter_id=chapter.id,
            name=name,
            type="location",
            description=f"{name} appears in the chapter.",
            relations=relations,
            status="pending",
        )
        session.add(suggestion)
        await session.commit()
        return suggestion


async def test_an_accept_resolves_proposals_by_name_and_by_alias() -> None:
    """D8's resolution: trimmed, case-insensitive exact match on names and
    aliases — '  mira  ' finds Mira, an alias in any case finds its row."""
    novel_id, [mira, haus] = await _seed_canon(("Mira", []), ("Haus", ["The House"]))
    suggestion = await _pending_proposal(
        novel_id,
        "Leuchtturm",
        [
            {"target": "  mira  ", "type": "bewohnt"},
            {"target": "the house", "type": "steht_in"},
        ],
    )
    async with _client() as client:
        accepted = await client.post(f"/api/knowledge/suggestions/{suggestion.id}/accept")
        assert accepted.status_code == 200
        body = accepted.json()
        assert body["entity"]["name"] == "Leuchtturm"
        assert body["skipped_relations"] == []  # both proposals placed

        edges = (
            await client.get(f"/api/knowledge/entities/{body['entity']['id']}/relations")
        ).json()
        assert sorted((edge["to_entity_id"], edge["relation_type"]) for edge in edges) == sorted(
            [(str(mira.id), "bewohnt"), (str(haus.id), "steht_in")]
        )


async def test_an_ambiguous_target_is_skipped_with_its_note() -> None:
    """Two entities sharing the target's alias make the proposal ambiguous:
    it skips with its note — no guessed attach — while an unambiguous one
    on the same suggestion still places."""
    novel_id, [mira, _verena] = await _seed_canon(("Mira", ["Käthe"]), ("Verena", ["Käthe"]))
    suggestion = await _pending_proposal(
        novel_id,
        "Leuchtturm",
        [
            {"target": "Käthe", "type": "kennt"},
            {"target": "Mira", "type": "mag"},
        ],
    )
    async with _client() as client:
        accepted = await client.post(f"/api/knowledge/suggestions/{suggestion.id}/accept")
        assert accepted.status_code == 200
        body = accepted.json()
        assert body["skipped_relations"] == [{"target_name": "Käthe", "relation_type": "kennt"}]

        edges = (
            await client.get(f"/api/knowledge/entities/{body['entity']['id']}/relations")
        ).json()
        # zero edges for the skipped pair; the resolvable one placed
        assert [(edge["to_entity_id"], edge["relation_type"]) for edge in edges] == [
            (str(mira.id), "mag")
        ]


async def test_an_absent_target_is_skipped_with_its_note() -> None:
    """A target the novel does not name skips visibly: the note rides the
    response, and no edge is created for it."""
    novel_id, _rows = await _seed_canon(("Mira", []))
    suggestion = await _pending_proposal(
        novel_id, "Leuchtturm", [{"target": "Nebel", "type": "kennt"}]
    )
    async with _client() as client:
        accepted = await client.post(f"/api/knowledge/suggestions/{suggestion.id}/accept")
        assert accepted.status_code == 200
        body = accepted.json()
        assert body["skipped_relations"] == [{"target_name": "Nebel", "relation_type": "kennt"}]
        assert (
            await client.get(f"/api/knowledge/entities/{body['entity']['id']}/relations")
        ).json() == []


async def test_accept_order_decides_a_pending_target() -> None:
    """Resolution sees existing entities only: a target still pending in the
    queue skips, and the same pair places once the target's own accept has
    made it real — the queue's order is the resolution's."""
    novel_id, _rows = await _seed_canon()
    haus = await _pending_proposal(novel_id, "Haus", [{"target": "Mira", "type": "steht_in"}])
    mira = await _pending_proposal(novel_id, "Mira", [{"target": "Haus", "type": "bewohnt"}])
    async with _client() as client:
        first = await client.post(f"/api/knowledge/suggestions/{haus.id}/accept")
        assert first.status_code == 200
        body = first.json()
        assert body["skipped_relations"] == [
            {"target_name": "Mira", "relation_type": "steht_in"}
        ]  # Mira is still pending
        assert (
            await client.get(f"/api/knowledge/entities/{body['entity']['id']}/relations")
        ).json() == []

        second = await client.post(f"/api/knowledge/suggestions/{mira.id}/accept")
        assert second.status_code == 200
        second_body = second.json()
        assert second_body["skipped_relations"] == []  # Haus exists by now
        edges = (
            await client.get(f"/api/knowledge/entities/{second_body['entity']['id']}/relations")
        ).json()
        assert [(edge["to_entity_id"], edge["relation_type"]) for edge in edges] == [
            (str(body["entity"]["id"]), "bewohnt")
        ]


async def test_a_repeated_proposal_files_one_edge() -> None:
    """One answer proposing the same (target, type) twice folds into one
    edge: the look-before-write answers the second proposal, and the
    repository's unique constraint backs the fold — the queue's wording
    never becomes a second relation."""
    novel_id, [mira] = await _seed_canon(("Mira", []))
    suggestion = await _pending_proposal(
        novel_id,
        "Leuchtturm",
        [
            {"target": "Mira", "type": "mag"},
            {"target": "Mira", "type": "mag"},
        ],
    )
    async with _client() as client:
        accepted = await client.post(f"/api/knowledge/suggestions/{suggestion.id}/accept")
        assert accepted.status_code == 200
        body = accepted.json()
        assert body["skipped_relations"] == []  # the fold is not a skip

        edges = (
            await client.get(f"/api/knowledge/entities/{body['entity']['id']}/relations")
        ).json()
        assert [(edge["to_entity_id"], edge["relation_type"]) for edge in edges] == [
            (str(mira.id), "mag")
        ]


async def test_a_target_deleted_in_the_race_skips_with_its_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The edge insert's race backstop: a target deleted between the
    candidate read and the write fails the edge's foreign key — that one
    proposal skips with its note (absence semantics, D8), while the entity
    and the other edges still land. The savepoint keeps the transaction
    alive, so one vanished target costs one skip, not the accept."""
    novel_id, [mira, haus] = await _seed_canon(("Mira", []), ("Haus", []))
    suggestion = await _pending_proposal(
        novel_id,
        "Leuchtturm",
        [
            {"target": "Haus", "type": "bewohnt"},
            {"target": "Mira", "type": "mag"},
        ],
    )

    original_list = EntityRepository.list_for_novel

    async def racing_list(
        self: EntityRepository,
        listed_novel_id: UUID,
        *,
        type: str | None = None,
        tag: str | None = None,
        q: str | None = None,
    ) -> list[Entity]:
        rows = await original_list(self, listed_novel_id, type=type, tag=tag, q=q)
        # The concurrent writer deletes Haus after this request's read —
        # the same window a merge or a delete racing the accept opens.
        async with Session() as other:
            victim = await other.get(Entity, haus.id)
            if victim is not None:
                await other.delete(victim)
                await other.commit()
        return list(rows)

    monkeypatch.setattr(EntityRepository, "list_for_novel", racing_list)
    async with _client() as client:
        accepted = await client.post(f"/api/knowledge/suggestions/{suggestion.id}/accept")
        assert accepted.status_code == 200  # not a 500: the race is an answer
        body = accepted.json()
        assert body["entity"]["name"] == "Leuchtturm"  # the entity still lands
        assert body["skipped_relations"] == [{"target_name": "Haus", "relation_type": "bewohnt"}]

        # The surviving proposal comes after the failed one on purpose: the
        # savepoint's rollback must not end the placing, so a `break` after
        # the vanished target's insert would fail this pin — the next
        # proposal still lands its edge.
        edges = (
            await client.get(f"/api/knowledge/entities/{body['entity']['id']}/relations")
        ).json()
        assert [(edge["to_entity_id"], edge["relation_type"]) for edge in edges] == [
            (str(mira.id), "mag")
        ]
