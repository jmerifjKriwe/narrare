"""The consistency check: the second job kind, from enqueue to findings.

Mirrors the extraction suite's shape: the request only enqueues (D14), the
worker's handler reads every chapter plus the accepted canon, prompts the
provider, and files its findings as reviewable rows on one terminal commit.
The review contract mirrors the suggestion queue's end to end — pending is
the queue, acknowledge and dismiss consume exactly once, and a re-run stacks
nothing behind a pending row.
"""

import asyncio
from json import dumps
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import text

from app.api.main import app
from app.kernel.contracts.models import Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm.contract import DONE, CompletionEvent, CompletionRequest, Delta

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.timeout(60)

OTHER_USER = uuid4()

# Chapter titles without numbers, on purpose: the fake's passage assembly
# carries every chapter heading after the first marker inside a passage, and
# a numbered title ("Kapitel 2") would feed the derivation a (word, number)
# pair of its own. The bodies steer the derivation; the titles stay inert.
CHAPTER_TITLES = ("Ankunft", "Später", "Danach", "Ende")

# Two chapters that disagree about Mira's age: the check's bread and butter.
# The texts steer the fake provider's derivation — a capitalized word given
# two different numbers across the chapters is the contradiction.
CONTRADICTING_BODIES = (
    "Mira ist 34 Jahre alt und kennt das Dorf.",
    "Später steht geschrieben: Mira ist 37 und will fort.",
)
# Two names, two contradictions each: enough findings for a review round.
TWO_NAMES_BODIES = (
    "Mira ist 34, und Tom ist 30.",
    "Mira ist 37, und Tom ist 33.",
)
# Chapters that agree: the empty array is the honest answer.
AGREEING_BODIES = (
    "Mira ist 34, wie am Anfang.",
    "Mira ist 34, unverändert.",
)


def _client() -> AsyncClient:
    """Create an HTTP client that drives the real application through ASGI."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _novel_with_chapters(
    client: AsyncClient, bodies: tuple[str, ...], title: str = "Der Nebel"
) -> str:
    """A novel with one written chapter per body, all the caller's own."""
    novel = await client.post("/api/writing/novels", json={"title": title})
    novel_id = novel.json()["id"]
    for position, body in enumerate(bodies):
        chapter = await client.post(
            f"/api/writing/novels/{novel_id}/chapters",
            # The modulo only guards a fifth chapter nobody wrote; duplicates
            # are harmless — titles carry no uniqueness.
            json={"title": CHAPTER_TITLES[position % len(CHAPTER_TITLES)]},
        )
        await client.put(f"/api/writing/chapters/{chapter.json()['id']}", json={"body": body})
    return novel_id


async def _run_lane_once() -> bool:
    """One claim of the lane, the way the api app's task would run it."""
    from app.capabilities.knowledge.jobs import handlers
    from app.kernel.jobs.worker import Worker

    return await Worker(Session, handlers).run_once()


async def _enqueue_check(client: AsyncClient, novel_id: str) -> str:
    """Enqueue one consistency run, asserting the contract's 202.

    Every test expecting the 202 goes through here, so a refusal is caught
    as the wrong status where it happens — not later as a KeyError on a
    body that never carried a job id.
    """
    response = await client.post(f"/api/knowledge/consistency/{novel_id}")
    assert response.status_code == 202
    return response.json()["job_id"]


async def _pending_findings(client: AsyncClient, novel_id: str) -> list[dict[str, object]]:
    """Fetch the novel review queue and require a successful response."""
    listed = await client.get(f"/api/knowledge/novels/{novel_id}/findings")
    assert listed.status_code == 200
    return listed.json()


class _GarbageProvider:
    """A provider whose answer is not JSON: the malformed-answer path.

    It sits exactly where the real one does — behind the provider boundary —
    so everything below the boundary runs the real code."""

    def describe(self) -> str:
        """Identify the provider that emits an invalid consistency answer."""
        return "garbage"

    def configuration_problems(self) -> list[str]:
        """Report that this deterministic provider needs no configuration."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Yield non-JSON prose followed by DONE to exercise answer validation."""
        yield Delta(text="Die Kapitel stimmen überein — aber kein JSON.")
        yield DONE


async def test_the_prompts_declare_their_purpose() -> None:
    """Verify purpose markers, source passages, and accepted canon reach the prompts."""
    from app.capabilities.knowledge.prompts import consistency_prompt, extraction_prompt
    from app.kernel.llm import PURPOSE_PREFIX

    extraction = extraction_prompt(chapter_title="Ankunft", body="Mira kam.")
    assert extraction.startswith(f"{PURPOSE_PREFIX}extract-entities\n")
    assert "SOURCE: Mira kam." in extraction

    check = consistency_prompt(
        entities=[("Mira", "character")],
        chapters=[("Ankunft", "Mira ist 34."), ("Später", "Mira ist 37.")],
    )
    assert check.startswith(f"{PURPOSE_PREFIX}check-consistency\n")
    assert "JSON array" in check  # the answer shape is contracted in prose
    assert "Mira (character)" in check  # the accepted canon grounds the check
    assert "Chapter: Ankunft\nText:\nSOURCE: Mira ist 34." in check
    assert "Chapter: Später\nText:\nSOURCE: Mira ist 37." in check

    empty_grounding = consistency_prompt(entities=[], chapters=[("Ankunft", "Mira ist 34.")])
    assert "None accepted yet." in empty_grounding


def test_the_parse_refuses_answers_that_are_not_the_contracted_shape() -> None:
    """Verify finding parsing accepts valid arrays and rejects malformed or oversized fields."""
    from app.capabilities.knowledge.jobs import MalformedAnswerError, parse_findings

    good = '[{"summary": "Mira: 34 vs. 37", "detail": "Die Kapitel widersprechen sich."}]'
    [finding] = parse_findings(good)
    assert finding.summary == "Mira: 34 vs. 37"
    assert finding.detail == "Die Kapitel widersprechen sich."

    [bare] = parse_findings('[{"summary": "Nur eine Zeile"}]')  # detail is nullable
    assert bare.detail is None

    assert parse_findings("[]") == []  # an empty array is a valid answer

    with pytest.raises(MalformedAnswerError):
        parse_findings("Die Kapitel stimmen überein — aber kein JSON.")
    with pytest.raises(MalformedAnswerError):
        parse_findings('{"summary": "Mira"}')  # an object, not an array
    with pytest.raises(MalformedAnswerError):
        parse_findings('[{"detail": "ohne summary"}]')  # no summary
    with pytest.raises(MalformedAnswerError):
        parse_findings('[{"summary": "   "}]')  # blank is no summary
    with pytest.raises(MalformedAnswerError):
        parse_findings('["Mira"]')  # a string, not an object
    with pytest.raises(MalformedAnswerError):
        parse_findings('[{"summary": "Mira", "detail": 5}]')  # detail must be a string

    # The summary column is String(200): a summary of exactly that width
    # parses, and a longer one is refused on the contract path — not by the
    # database, whose verdict would arrive as a DataError after the fact.
    [widest] = parse_findings(f'[{{"summary": "{"S" * 200}"}}]')
    assert widest.summary == "S" * 200
    with pytest.raises(MalformedAnswerError) as refused:
        parse_findings(f'[{{"summary": "{"S" * 201}"}}]')
    # The refusal carries the summary's true length, the way the entity
    # parse's does: the repr clips the shown item, so the count is what
    # keeps an over-long summary diagnosable.
    assert "an item's summary is 201 characters" in str(refused.value)


async def test_the_check_enqueues_a_job_and_refuses_what_is_not_the_callers() -> None:
    """Verify only an owned novel can enqueue a check or expose its findings."""
    async with _client() as client:
        novel_id = await _novel_with_chapters(client, CONTRADICTING_BODIES)
        job_id = await _enqueue_check(client, novel_id)

        # The request only enqueued: the row sits queued until the lane claims it.
        status = await client.get(f"/api/jobs/{job_id}")
        assert status.status_code == 200
        assert status.json()["status"] == "queued"
        assert status.json()["kind"] == "check-consistency"

        unknown = await client.post(
            "/api/knowledge/consistency/00000000-0000-0000-0000-0000000000ff"
        )
        assert unknown.status_code == 404

    await seed_user(OTHER_USER)
    async with Session() as session:
        foreign = Novel(user_id=OTHER_USER, title="Fremder Roman")
        session.add(foreign)
        await session.commit()

    async with _client() as client:
        foreign_response = await client.post(f"/api/knowledge/consistency/{foreign.id}")
        assert foreign_response.status_code == 404
        foreign_findings = await client.get(f"/api/knowledge/novels/{foreign.id}/findings")
        assert foreign_findings.status_code == 404

    async with Session() as session:
        enqueued = await session.scalar(text("SELECT count(*) FROM jobs"))
    assert enqueued == 1  # the refusals enqueued nothing


async def test_the_worker_files_one_pending_finding_per_contradiction() -> None:
    """Verify a completed check records progress, a pending finding, and its audit together."""
    async with _client() as client:
        novel_id = await _novel_with_chapters(client, CONTRADICTING_BODIES)
        job_id = await _enqueue_check(client, novel_id)

        assert await _run_lane_once() is True

        done = (await client.get(f"/api/jobs/{job_id}")).json()
        assert done["status"] == "done"
        assert done["progress"] == 100
        assert done["result"] == {"findings": 1, "skipped_chapters": []}
        assert done["error"] is None

        findings = await _pending_findings(client, novel_id)
        assert len(findings) == 1
        [finding] = findings
        assert finding["novel_id"] == novel_id
        assert finding["summary"] == "Mira: 34 vs. 37"
        assert finding["detail"] == '"Mira ist 34" vs. "Mira ist 37"'
        assert finding["status"] == "pending"

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
        assert row.task_key == "knowledge.check-consistency"
        assert str(row.novel_id) == novel_id
        assert row.provider_kind == "fake"
        assert row.model == "fake"
        assert row.input_tokens > 0
        assert row.output_tokens > 0
        assert row.status == "ok"
        assert row.cost_usd is None


async def test_an_agreeing_novel_checks_to_an_empty_queue() -> None:
    """Verify consistent chapters complete successfully without pending findings."""
    async with _client() as client:
        novel_id = await _novel_with_chapters(client, AGREEING_BODIES)
        job_id = await _enqueue_check(client, novel_id)

        assert await _run_lane_once() is True

        done = (await client.get(f"/api/jobs/{job_id}")).json()
        assert done["status"] == "done"
        assert done["result"] == {"findings": 0, "skipped_chapters": []}
        assert await _pending_findings(client, novel_id) == []


async def test_a_novel_without_chapters_checks_to_an_empty_queue() -> None:
    """Verify a novel with no chapters completes with zero findings."""
    # No chapters is no contradiction: the check is a done job with an honest
    # zero, not a failure — the empty array is a valid answer.
    async with _client() as client:
        novel = await client.post("/api/writing/novels", json={"title": "Leer"})
        novel_id = novel.json()["id"]
        job_id = await _enqueue_check(client, novel_id)

        assert await _run_lane_once() is True

        done = (await client.get(f"/api/jobs/{job_id}")).json()
        assert done["status"] == "done"
        assert done["result"] == {"findings": 0, "skipped_chapters": []}
        assert await _pending_findings(client, novel_id) == []


async def test_a_malformed_answer_fails_the_job_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify invalid provider output exhausts retries without findings or audit rows."""
    import app.capabilities.knowledge.jobs as jobs

    monkeypatch.setattr(jobs, "get_provider", lambda: _GarbageProvider())

    async with _client() as client:
        novel_id = await _novel_with_chapters(client, CONTRADICTING_BODIES)
        job_id = await _enqueue_check(client, novel_id)

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
        findings = await session.scalar(text("SELECT count(*) FROM consistency_findings"))
        calls = await session.scalar(text("SELECT count(*) FROM llm_calls"))
    assert findings == 0
    assert calls == 0  # a failed job writes no audit row (D3)


async def test_a_rerun_stacks_nothing_and_a_consumed_finding_files_fresh() -> None:
    """The dedupe ruling: only a pending row blocks, and it blocks its own summary.

    A re-run — the outage retry's shape, a second check after the first
    settled — skips a parsed finding whose summary is already pending, so the
    queue answers with one finding. The skip reads only pending rows, which
    is the asymmetry: acknowledge consumes the row, and the same re-run is
    then allowed to file it again — the writer's decision reopens a summary.
    """
    async with _client() as client:
        novel_id = await _novel_with_chapters(client, CONTRADICTING_BODIES)

        await _enqueue_check(client, novel_id)
        assert await _run_lane_once() is True
        # The re-run on the same novel: the same contradiction parsed, its
        # summary already pending — no second row behind the first.
        await _enqueue_check(client, novel_id)
        assert await _run_lane_once() is True

        first = await _pending_findings(client, novel_id)
        assert [finding["summary"] for finding in first] == ["Mira: 34 vs. 37"]

        # The asymmetry's proof: acknowledging consumes the row, so the
        # re-run files the same summary fresh — a new pending row, not the
        # consumed one back.
        acknowledged = await client.post(f"/api/knowledge/findings/{first[0]['id']}/acknowledge")
        assert acknowledged.status_code == 200

        await _enqueue_check(client, novel_id)
        assert await _run_lane_once() is True

        after = await _pending_findings(client, novel_id)
        assert [finding["summary"] for finding in after] == ["Mira: 34 vs. 37"]
        assert first[0]["id"] not in [finding["id"] for finding in after]  # fresh, not resurrected
        consumed = (
            await client.get(f"/api/knowledge/novels/{novel_id}/findings?status=acknowledged")
        ).json()
        assert [row["id"] for row in consumed] == [first[0]["id"]]


async def test_acknowledge_and_dismiss_consume_exactly_once() -> None:
    """Verify either review verdict consumes a finding and repeated verdicts return HTTP 409."""
    async with _client() as client:
        novel_id = await _novel_with_chapters(client, TWO_NAMES_BODIES)
        await _enqueue_check(client, novel_id)
        assert await _run_lane_once() is True

        findings = await _pending_findings(client, novel_id)
        assert [finding["summary"] for finding in findings] == [
            "Mira: 34 vs. 37",
            "Tom: 30 vs. 33",
        ]

        acknowledged = await client.post(f"/api/knowledge/findings/{findings[0]['id']}/acknowledge")
        assert acknowledged.status_code == 200
        assert acknowledged.json()["status"] == "acknowledged"

        dismissed = await client.post(f"/api/knowledge/findings/{findings[1]['id']}/dismiss")
        assert dismissed.status_code == 200
        assert dismissed.json()["status"] == "dismissed"

        # Review is exactly-once: every second verdict on a consumed row is a 409,
        # whichever way the first one went.
        for path in (
            f"/api/knowledge/findings/{findings[0]['id']}/acknowledge",
            f"/api/knowledge/findings/{findings[0]['id']}/dismiss",
            f"/api/knowledge/findings/{findings[1]['id']}/dismiss",
            f"/api/knowledge/findings/{findings[1]['id']}/acknowledge",
        ):
            second = await client.post(path)
            assert second.status_code == 409

        assert await _pending_findings(client, novel_id) == []
        listed_acknowledged = (
            await client.get(f"/api/knowledge/novels/{novel_id}/findings?status=acknowledged")
        ).json()
        listed_dismissed = (
            await client.get(f"/api/knowledge/novels/{novel_id}/findings?status=dismissed")
        ).json()
        assert [row["id"] for row in listed_acknowledged] == [findings[0]["id"]]
        assert [row["id"] for row in listed_dismissed] == [findings[1]["id"]]


async def test_two_concurrent_acknowledges_leave_one_winner() -> None:
    """Verify concurrent acknowledgements yield one success and one conflict."""
    async with _client() as client:
        novel_id = await _novel_with_chapters(client, CONTRADICTING_BODIES)
        await _enqueue_check(client, novel_id)
        assert await _run_lane_once() is True
        [finding] = await _pending_findings(client, novel_id)
        acknowledge_path = f"/api/knowledge/findings/{finding['id']}/acknowledge"

    async def _acknowledge() -> Response:
        """Submit an acknowledgement using an independent client for the concurrency test."""
        async with _client() as own:
            return await own.post(acknowledge_path)

    # Two requests in flight at once: the row-level transition must serialize
    # them — one winner, one 409, one consumed row.
    first, second = await asyncio.gather(_acknowledge(), _acknowledge())
    assert sorted([first.status_code, second.status_code]) == [200, 409]

    async with _client() as client:
        assert await _pending_findings(client, novel_id) == []
        consumed = (
            await client.get(f"/api/knowledge/novels/{novel_id}/findings?status=acknowledged")
        ).json()
    assert len(consumed) == 1


async def test_acknowledge_and_dismiss_race_for_one_finding() -> None:
    """Verify opposing concurrent verdicts consume one finding exactly once."""
    # The stronger race: both verdicts on the same row at once. Whichever
    # wins, the row is consumed exactly once — the loser reads a consumed
    # status under the winner's commit, not a second verdict's ground.
    async with _client() as client:
        novel_id = await _novel_with_chapters(client, CONTRADICTING_BODIES)
        await _enqueue_check(client, novel_id)
        assert await _run_lane_once() is True
        [finding] = await _pending_findings(client, novel_id)
        acknowledge = f"/api/knowledge/findings/{finding['id']}/acknowledge"
        dismiss = f"/api/knowledge/findings/{finding['id']}/dismiss"

    async def _post(path: str) -> Response:
        """Submit one competing review verdict through an independent client."""
        async with _client() as own:
            return await own.post(path)

    winner, loser = await asyncio.gather(_post(acknowledge), _post(dismiss))
    assert sorted([winner.status_code, loser.status_code]) == [200, 409]

    async with _client() as client:
        assert await _pending_findings(client, novel_id) == []
        acknowledged = (
            await client.get(f"/api/knowledge/novels/{novel_id}/findings?status=acknowledged")
        ).json()
        dismissed = (
            await client.get(f"/api/knowledge/novels/{novel_id}/findings?status=dismissed")
        ).json()
    # Exactly one verdict landed; which one is the race's, not the contract's.
    assert len(acknowledged) + len(dismissed) == 1


async def test_another_users_finding_cannot_be_reviewed() -> None:
    """Verify foreign and nonexistent findings return HTTP 404 without changing rows."""
    from app.kernel.contracts.models import ConsistencyFinding

    async with _client() as client:
        novel_id = await _novel_with_chapters(client, CONTRADICTING_BODIES)
        await _enqueue_check(client, novel_id)
        assert await _run_lane_once() is True  # my rows exist: scoping must not blur

    await seed_user(OTHER_USER)
    async with Session() as session:
        novel = Novel(user_id=OTHER_USER, title="Fremder Roman")
        session.add(novel)
        await session.flush()
        theirs = ConsistencyFinding(
            user_id=OTHER_USER,
            novel_id=novel.id,
            summary="Mira: 34 vs. 37",
            status="pending",
        )
        session.add(theirs)
        await session.commit()

    async with _client() as client:
        for path in (
            f"/api/knowledge/findings/{theirs.id}/acknowledge",
            f"/api/knowledge/findings/{theirs.id}/dismiss",
        ):
            response = await client.post(path)
            assert response.status_code == 404

        unknown = await client.post(
            "/api/knowledge/findings/00000000-0000-0000-0000-0000000000ff/acknowledge"
        )
        assert unknown.status_code == 404

    async with Session() as session:
        row = await session.get(ConsistencyFinding, theirs.id)
    assert row is not None
    assert row.status == "pending"  # the refusals consumed nothing


class _ScriptedProvider:
    """A provider that answers each call from a script and records the prompt."""

    def __init__(self, answers: tuple[str, ...]) -> None:
        self.answers = list(answers)
        self.requests: list[CompletionRequest] = []

    def describe(self) -> str:
        """Identify the provider that reads its answers from a script."""
        return "scripted"

    def configuration_problems(self) -> list[str]:
        """Report that this deterministic provider needs no configuration."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Record the request and answer with the next scripted finding array."""
        self.requests.append(request)
        yield Delta(text=self.answers.pop(0))
        yield DONE


def _findings_json(*summaries: str) -> str:
    """A provider answer carrying one finding per summary."""
    return dumps([{"summary": summary, "detail": "34 gegen 37"} for summary in summaries])


async def test_a_novel_beyond_the_bound_is_checked_in_groups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two chapters that cannot share a pass become two calls and one merge."""
    import app.capabilities.knowledge.jobs as jobs

    provider = _ScriptedProvider((_findings_json("Mira altert"), _findings_json("Tom altert")))
    monkeypatch.setattr(jobs, "get_provider", lambda: provider)

    async with _client() as client:
        novel_id = await _novel_with_chapters(client, ("x" * 12_000, "y" * 12_000))
        job_id = await _enqueue_check(client, novel_id)
        assert await _run_lane_once() is True
        done = (await client.get(f"/api/jobs/{job_id}")).json()
        findings = await _pending_findings(client, novel_id)

    assert len(provider.requests) == 2
    assert done["status"] == "done"
    assert done["result"] == {"findings": 2, "skipped_chapters": []}
    assert [finding["summary"] for finding in findings] == ["Mira altert", "Tom altert"]


async def test_the_same_summary_from_two_groups_is_filed_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A contradiction both passes report is one card, not two."""
    import app.capabilities.knowledge.jobs as jobs

    provider = _ScriptedProvider((_findings_json("Mira altert"), _findings_json("Mira altert")))
    monkeypatch.setattr(jobs, "get_provider", lambda: provider)

    async with _client() as client:
        novel_id = await _novel_with_chapters(client, ("x" * 12_000, "y" * 12_000))
        job_id = await _enqueue_check(client, novel_id)
        assert await _run_lane_once() is True
        done = (await client.get(f"/api/jobs/{job_id}")).json()
        findings = await _pending_findings(client, novel_id)

    assert done["result"] == {"findings": 1, "skipped_chapters": []}
    assert len(findings) == 1


async def test_an_oversized_chapter_is_skipped_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The chapter over the bound never reaches the provider and is named."""
    import app.capabilities.knowledge.jobs as jobs

    provider = _ScriptedProvider((_findings_json(),))
    monkeypatch.setattr(jobs, "get_provider", lambda: provider)

    async with _client() as client:
        novel_id = await _novel_with_chapters(client, ("x" * 20_001, "Mira ist 34."))
        job_id = await _enqueue_check(client, novel_id)
        assert await _run_lane_once() is True
        done = (await client.get(f"/api/jobs/{job_id}")).json()

    assert len(provider.requests) == 1
    assert "x" * 20_001 not in provider.requests[0].messages[0].content
    assert done["result"] == {"findings": 0, "skipped_chapters": ["Ankunft"]}


async def test_a_novel_of_only_oversized_chapters_makes_no_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing to check is done, not a failure: no call, every name skipped."""
    import app.capabilities.knowledge.jobs as jobs

    provider = _ScriptedProvider(())
    monkeypatch.setattr(jobs, "get_provider", lambda: provider)

    async with _client() as client:
        novel_id = await _novel_with_chapters(client, ("x" * 20_001, "y" * 20_001))
        job_id = await _enqueue_check(client, novel_id)
        assert await _run_lane_once() is True
        done = (await client.get(f"/api/jobs/{job_id}")).json()

    assert provider.requests == []
    assert done["status"] == "done"
    assert done["result"] == {"findings": 0, "skipped_chapters": ["Ankunft", "Später"]}
