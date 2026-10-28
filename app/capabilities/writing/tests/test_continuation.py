"""Continuation: the stream is SSE, the chunks add up, and the door stays shut."""

import json
from collections.abc import AsyncIterator  # noqa: TC003
from logging import Formatter
from uuid import UUID, uuid4

import pytest
from anyio import Event
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.api.main import app
from app.capabilities.writing import router as writing_router
from app.capabilities.writing import service as writing_service
from app.capabilities.writing.prompts import continuation_prompt
from app.capabilities.writing.repository import EntityRepository
from app.capabilities.writing.router import (
    _continuation_events,  # pyright: ignore[reportPrivateUsage]  test the stream's finalizer
    continue_chapter,
)
from app.capabilities.writing.service import WritingService
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.context import BudgetImpossibleError, ContextBudgets
from app.kernel.contracts.models import Chapter, Entity, Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm.contract import (
    DONE,
    CompletionEvent,
    CompletionRequest,
    Delta,
    TextProvider,
)
from app.kernel.llm.fake import FakeProvider
from app.kernel.llm.profiles import ProfileRepository
from app.kernel.llm.resolution import ResolvedProvider
from app.kernel.llm.streaming import FinalizingStreamingResponse
from app.kernel.testing.streams import StreamProbeProvider, interrupt_response

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _resolved(provider: TextProvider) -> ResolvedProvider:
    """A fake-tier resolved carrier for a stand-in provider the tests inject."""
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


@pytest.mark.parametrize("fail", [False, True])
async def test_audit_failure_does_not_truncate_the_response(
    fail: bool, caplog: pytest.LogCaptureFixture
) -> None:
    """A real audit FK rejection preserves response framing and keeps text out of logs."""
    provider = StreamProbeProvider(fail=fail)
    # This user does not exist: the audit's real database commit must fail.
    response = FinalizingStreamingResponse(
        _continuation_events(_resolved(provider), "audit-private-prompt", uuid4(), uuid4()),
        media_type="text/event-stream",
        headers={},
    )
    async with AsyncClient(transport=ASGITransport(app=response), base_url="http://test") as client:
        result = await client.get("/")
    # ASGITransport asserts that more_body=False was received before returning.
    assert result.status_code == 200
    assert '"delta": "partial"' in result.text
    assert ("event: error" in result.text) is fail
    assert ("event: done" in result.text) is not fail
    failures = [
        record
        for record in caplog.records
        if record.getMessage() == "writing.continuation audit failed"
    ]
    assert len(failures) == 1
    assert failures[0].exc_info is not None
    assert isinstance(failures[0].exc_info[1], IntegrityError)
    logged = Formatter().format(failures[0])
    assert "audit-private-prompt" not in logged
    assert "partial" not in logged
    assert "IntegrityError" in logged
    assert "INSERT INTO llm_calls" in logged


@pytest.mark.parametrize("interruption", ["waiting", "send"])
async def test_audit_failure_does_not_replace_a_disconnect(
    interruption: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A rejected audit breaks neither disconnect path: send raises ClientDisconnect,
    receive returns normally once Starlette's task group closes."""
    waiting = Event() if interruption == "waiting" else None
    provider = StreamProbeProvider(waiting=waiting)
    response = FinalizingStreamingResponse(
        _continuation_events(_resolved(provider), "question", uuid4(), uuid4()),
        media_type="text/event-stream",
        headers={},
    )
    # The probe asserts ClientDisconnect on send failure; receive cancellation
    # must return normally after Starlette's task group closes.
    await interrupt_response(
        response,
        spec_version="2.0" if waiting else "2.4",
        frame="" if waiting else "event: done",
        disconnected=waiting,
    )
    failures = [
        record
        for record in caplog.records
        if record.getMessage() == "writing.continuation audit failed"
    ]
    assert len(failures) == 1
    assert failures[0].exc_info is not None
    assert isinstance(failures[0].exc_info[1], IntegrityError)


@pytest.mark.parametrize(
    ("spec_version", "frame"),
    [
        (spec, frame)
        for spec in ("2.0", "2.4")
        for frame in ("delta", "event: done", "event: error", "waiting")
        if (spec, frame) != ("2.4", "waiting")
    ],
)
async def test_disconnected_stream_is_audited_once(spec_version: str, frame: str) -> None:
    """Disconnects preserve partial text, usage, and the provider's outcome."""
    waiting = Event() if frame == "waiting" else None
    provider = StreamProbeProvider(fail=frame == "event: error", waiting=waiting)
    novel_id = uuid4()
    response = FinalizingStreamingResponse(
        _continuation_events(_resolved(provider), "question", novel_id, LOCAL_USER_ID),
        media_type="text/event-stream",
        headers={},
    )
    await interrupt_response(
        response, spec_version=spec_version, frame="" if waiting else frame, disconnected=waiting
    )
    async with Session() as session:
        row = (
            await session.execute(
                text(
                    "SELECT status, error, response_text, input_tokens, output_tokens,"
                    " novel_id FROM llm_calls"
                )
            )
        ).one()
    assert row.novel_id == novel_id
    assert row.response_text == "partial"
    assert row.status == ("ok" if frame == "event: done" else "error")
    assert row.error == (
        None
        if frame == "event: done"
        else "provider failed"
        if frame == "event: error"
        else "stream interrupted"
    )
    expected_usage = (None, None) if frame == "delta" else (3, 2)
    assert (row.input_tokens, row.output_tokens) == expected_usage


def _client() -> AsyncClient:
    """Create an HTTP client that drives the real application through ASGI."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _deltas(body: str) -> list[str]:
    """Collect text deltas from SSE data lines while ignoring other event payloads."""
    deltas: list[str] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            payload: dict[str, str] = json.loads(line[len("data: ") :])
            if "delta" in payload:
                deltas.append(payload["delta"])
    return deltas


async def _create_chapter(client: AsyncClient, body: str = "") -> str:
    """Create a novel and chapter through the API, optionally saving an initial body."""
    novel = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
    chapter = await client.post(
        f"/api/writing/novels/{novel.json()['id']}/chapters", json={"title": "Ankunft"}
    )
    chapter_id = chapter.json()["id"]
    if body:
        await client.put(f"/api/writing/chapters/{chapter_id}", json={"body": body})
    return chapter_id


async def test_the_continuation_streams_the_provider_chunks() -> None:
    """Verify continuation emits multiple SSE deltas and finishes with a done event."""
    async with _client() as client:
        chapter_id = await _create_chapter(client)
        response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    deltas = _deltas(response.text)
    # More than one event: the endpoint streams, it does not buffer one blob.
    assert len(deltas) > 1
    assert "".join(deltas) == "".join(FakeProvider.CHUNKS)
    assert "event: done" in response.text


async def test_the_continuation_records_its_audit_row() -> None:
    """Verify a successful continuation audits its novel, answer, tokens, and free fake."""
    async with _client() as client:
        chapter_id = await _create_chapter(client)
        response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")
        assert response.status_code == 200

    async with Session() as session:
        novel_id = await session.scalar(
            text("SELECT novel_id FROM chapters WHERE id = :id"), {"id": UUID(chapter_id)}
        )
        row = (
            await session.execute(
                text(
                    "SELECT task_key, novel_id, status, input_tokens, output_tokens,"
                    " response_text, cost_usd FROM llm_calls"
                )
            )
        ).one()
    assert row.task_key == "writing.continuation"
    assert str(row.novel_id) == str(novel_id)
    assert row.status == "ok"
    assert row.input_tokens > 0
    assert row.output_tokens > 0
    assert row.response_text == "".join(FakeProvider.CHUNKS)
    # The fake kind is free by the truth table (design D4): 0.0, not unknown.
    assert row.cost_usd == 0.0


class _DyingProvider:
    """Streams half an answer, then dies: the mid-stream failure path.

    It sits exactly where the real one does — behind the provider boundary —
    so everything below the boundary runs the real code."""

    def describe(self) -> str:
        """Identify the provider that fails after emitting partial text."""
        return "dying"

    def configuration_problems(self) -> list[str]:
        """Report that this deterministic provider needs no configuration."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Yield one partial text delta, then raise a provider failure."""
        yield Delta(text="Halb")
        raise RuntimeError("the provider died")


async def test_a_provider_that_dies_mid_stream_errors_and_audits_the_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify partial provider output is preserved with an error event and a failed audit."""

    async def _dying(session: AsyncSession, user_id: UUID, task_key: str) -> ResolvedProvider:
        return _resolved(_DyingProvider())

    monkeypatch.setattr(writing_router, "resolve_provider", _dying)
    async with _client() as client:
        chapter_id = await _create_chapter(client)
        response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")

    assert response.status_code == 200
    assert _deltas(response.text) == ["Halb"]  # what arrived, arrived
    assert "event: error" in response.text
    assert "event: done" not in response.text

    async with Session() as session:
        row = (await session.execute(text("SELECT status, error, task_key FROM llm_calls"))).one()
    assert row.task_key == "writing.continuation"
    assert row.status == "error"
    assert "the provider died" in row.error


async def test_a_profile_whose_key_is_lost_ends_the_stream_with_the_one_error_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stored key no tier can produce is the error frame, never a 500.

    The profile is the user's only one, so the cascade resolves it and its
    broken key refuses before any provider call: the response is exactly the
    one error frame, and no audit row claims a call that never ran.
    """
    monkeypatch.setenv("NARRE_KEYRING", "off")
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())
    async with Session() as session:
        await ProfileRepository(session, LOCAL_USER_ID).create(
            name="Broken",
            kind="openai-chat",
            base_url="https://api.vendor.example/v1",
            model="acme/turbo-3",
            # Ciphertext another NARRE_SECRET_KEY made: undecryptable on purpose.
            api_key="gAAAAABlindtext-not-what-this-key-encrypted",
            api_key_hint="roken",
        )
        await session.commit()

    async with _client() as client:
        chapter_id = await _create_chapter(client)
        response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")

    assert response.status_code == 200
    assert response.text == "event: error\ndata: {}\n\n"
    async with Session() as session:
        assert await session.scalar(text("SELECT count(*) FROM llm_calls")) == 0


async def test_an_impossible_budget_pair_ends_the_stream_with_the_one_error_frame(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The allocator refusing an impossible pair is the one error frame, no audit row.

    Resolution has already succeeded — the refusal comes from the builder the
    route calls second — so the stream ends the way a lost key ends it: one
    error frame, no provider call, no llm_calls row claiming either.
    """

    def _impossible(**_: object) -> ContextBudgets:
        raise BudgetImpossibleError(
            "no input room: max_output_tokens 5000 fills or exceeds context_window 4096"
        )

    monkeypatch.setattr(writing_service, "allocate", _impossible)
    async with _client() as client:
        chapter_id = await _create_chapter(client)
        response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")

    assert response.status_code == 200
    assert response.text == "event: error\ndata: {}\n\n"
    async with Session() as session:
        assert await session.scalar(text("SELECT count(*) FROM llm_calls")) == 0
    refusals = [
        record for record in caplog.records if record.getMessage() == "continuation budget refused"
    ]
    assert len(refusals) == 1
    assert refusals[0].exc_info is not None


class _RequestProbe:
    """A provider boundary that keeps the request the route built.

    It sits exactly where the real one does — behind the boundary the route
    resolves — so the assertion is on the CompletionRequest the wire would
    carry, not on a re-derived copy of it.
    """

    def __init__(self) -> None:
        self.request: CompletionRequest | None = None

    def describe(self) -> str:
        """Identify the probe for startup logging symmetry."""
        return "probe"

    def configuration_problems(self) -> list[str]:
        """Report that this deterministic provider needs no configuration."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Keep the request, then answer a fixed prose piece with the done event."""
        self.request = request
        yield Delta(text="Antwort.")
        yield DONE


@pytest.mark.parametrize(
    ("window", "output", "temperature", "expected_max_tokens"),
    [
        # The fake/env tier's facts are unset: the default reservation rides.
        (None, None, None, 1024),
        # A profile's facts: its own value, its temperature.
        (8192, 777, 0.3, 777),
    ],
)
async def test_the_continuation_request_carries_the_reservation_and_set_facts_only(
    monkeypatch: pytest.MonkeyPatch,
    window: int | None,
    output: int | None,
    temperature: float | None,
    expected_max_tokens: int,
) -> None:
    """max_tokens is always on the wire: the profile's value, else the default;
    temperature rides only when the resolved facts set it."""
    probe = _RequestProbe()
    resolved = ResolvedProvider(
        provider=probe,
        profile_id=None,
        kind="fake",
        model="fake",
        context_window=window,
        max_output_tokens=output,
        temperature=temperature,
        request_timeout=None,
        base_url=None,
        api_key=None,
    )

    async def _resolved_probe(
        session: AsyncSession, user_id: UUID, task_key: str
    ) -> ResolvedProvider:
        return resolved

    monkeypatch.setattr(writing_router, "resolve_provider", _resolved_probe)
    async with _client() as client:
        chapter_id = await _create_chapter(client)
        response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")

    assert response.status_code == 200
    assert "event: done" in response.text
    assert probe.request is not None
    assert probe.request.messages[0].role == "user"
    assert probe.request.max_tokens == expected_max_tokens
    assert probe.request.temperature == temperature


async def test_the_route_hands_back_the_finalizing_response() -> None:
    """The endpoint itself — not a hand-built wrapper — is what carries the audit.

    Every disconnect test above builds the response by hand; this one binds the
    route to the subclass, so reverting the endpoint to a plain StreamingResponse
    fails here instead of silently losing the audit guarantee.
    """
    async with _client() as client:
        chapter_id = await _create_chapter(client)
    async with Session() as session:
        service = WritingService(session, LOCAL_USER_ID)
        response = await continue_chapter(UUID(chapter_id), service, LOCAL_USER_ID)
    assert isinstance(response, FinalizingStreamingResponse)


async def test_another_users_chapter_cannot_be_continued() -> None:
    """Verify continuation hides another user's chapter with HTTP 404."""
    await seed_user(OTHER_USER)
    async with Session() as session:
        novel_id, chapter_id = uuid4(), uuid4()
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
            {
                "id": chapter_id,
                "user_id": OTHER_USER,
                "novel_id": novel_id,
                "title": "Fremd",
            },
        )
        await session.commit()

    async with _client() as client:
        response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")
        assert response.status_code == 404


async def test_a_missing_chapter_is_still_a_404_on_the_plain_tier() -> None:
    """Resolution first moved the builder behind it; the normal paths keep 404.

    No profile anywhere and the environment tier resolving to the fake: the
    missing chapter is refused with HTTP 404 exactly as before the reorder.
    """
    async with _client() as client:
        response = await client.post(f"/api/writing/chapters/{uuid4()}/continue")
    assert response.status_code == 404


_INSTRUCTION_END = (
    "Continue the chapter in the same voice. Keep the language of the existing "
    "text. Return only the new text, without a heading or commentary."
)


def test_each_section_renders_under_its_heading_and_the_instruction_stays_last() -> None:
    """Verify the prompt's four sections, their headings and the verbatim closing."""
    budgets = ContextBudgets(
        immediate_text=2000, referenced_entities=500, recent_chapters=400, style_hints=200
    )
    prompt = continuation_prompt(
        budgets=budgets,
        novel_title="Der Nebel",
        chapter_title="Ankunft",
        body="Der Nebel kam von See.",
        entities=[Entity(name="Mira", type="character", content="Die Wanderin.", aliases=[])],
        predecessors=[Chapter(title="Ursprung", position=0, body="Mira kam.")],
        genre="Mystery",
        blurb="Ein Nebeljahr.",
    )
    assert prompt.startswith(
        "Novel: Der Nebel\nChapter: Ankunft\n\nText so far:\nDer Nebel kam von See.\n\n"
    )
    assert "Referenced entities:\n### Mira (character)\nDie Wanderin." in prompt
    assert "Previous chapters:\n### Ursprung\nMira kam." in prompt
    assert "Style notes:\nGenre: Mystery\nBlurb: Ein Nebeljahr." in prompt
    assert prompt.endswith(_INSTRUCTION_END)
    assert "PURPOSE:" not in prompt
    assert "SOURCE:" not in prompt


def test_the_immediate_section_truncates_hard_at_its_budget_scaffolding_included() -> None:
    """Header, Text-so-far scaffolding and instruction count against the slice:
    the tail shrinks so the whole section is exactly the immediate budget."""
    budgets = ContextBudgets(
        immediate_text=250, referenced_entities=0, recent_chapters=0, style_hints=0
    )
    body = "Nebel uber der Kuste, und der Wind nahm zu, bis die Laternen flackerten. " * 6
    prompt = continuation_prompt(
        budgets=budgets, novel_title="Der Nebel", chapter_title="Ankunft", body=body
    )
    assert len(prompt) == 250
    assert body[:40] not in prompt  # the front fell away, the tail is the body's end
    assert body[-30:] in prompt


def test_a_zero_floor_slice_omits_its_section_entirely() -> None:
    """A zero-budget slice is absent, not an empty heading."""
    budgets = ContextBudgets(
        immediate_text=2000, referenced_entities=0, recent_chapters=0, style_hints=0
    )
    prompt = continuation_prompt(
        budgets=budgets,
        novel_title="Der Nebel",
        chapter_title="Ankunft",
        body="Der Nebel kam von See.",
        entities=[Entity(name="Mira", type="character", content="Die Wanderin.", aliases=[])],
        predecessors=[Chapter(title="Ursprung", position=0, body="Mira kam.")],
        genre="Mystery",
        blurb="Ein Nebeljahr.",
    )
    assert "Referenced entities:" not in prompt
    assert "Previous chapters:" not in prompt
    assert "Style notes:" not in prompt
    assert "Mira" not in prompt


def test_an_entity_whose_body_exceeds_the_slice_degrades_to_name_and_type() -> None:
    """A body that no longer fits degrades to the name (type) line, never overflow."""
    budgets = ContextBudgets(
        immediate_text=2000, referenced_entities=100, recent_chapters=0, style_hints=0
    )
    prompt = continuation_prompt(
        budgets=budgets,
        novel_title="Der Nebel",
        chapter_title="Ankunft",
        body="Der Nebel kam von See.",
        entities=[Entity(name="Mira Lange", type="character", content="X" * 300, aliases=[])],
    )
    assert "Mira Lange (character)" in prompt
    assert "### Mira Lange" not in prompt
    assert "X" * 20 not in prompt
    section = prompt[prompt.index("Referenced entities:") : prompt.index("Continue the chapter")]
    assert len(section) <= 100


def test_an_entity_whose_line_does_not_fit_is_skipped_silently() -> None:
    """Below the line floor the entity is skipped; a smaller later one still fits."""
    budgets = ContextBudgets(
        immediate_text=2000, referenced_entities=40, recent_chapters=0, style_hints=0
    )
    prompt = continuation_prompt(
        budgets=budgets,
        novel_title="Der Nebel",
        chapter_title="Ankunft",
        body="Der Nebel kam von See.",
        entities=[
            Entity(name="Mira Lange", type="character", content="Kurz.", aliases=[]),
            Entity(name="Fuchs", type="object", content="Rot.", aliases=[]),
        ],
    )
    # 40 minus heading and separator leaves 17: the first line (22) does not fit
    # and the skip is silent; the next entity's line (14) degrades in.
    assert "Mira" not in prompt
    assert "Fuchs (object)" in prompt
    assert "### Fuchs" not in prompt


def test_a_slice_that_cannot_hold_its_heading_is_omitted_whole() -> None:
    """Below heading + newline + separator the section is absent; at the threshold
    the heading renders whole and the slice never overflows."""
    prompt = continuation_prompt(
        budgets=ContextBudgets(
            immediate_text=2000, referenced_entities=22, recent_chapters=20, style_hints=0
        ),
        novel_title="Der Nebel",
        chapter_title="Ankunft",
        body="Der Nebel kam von See.",
        entities=[Entity(name="Mira", type="character", content="Die Wanderin.", aliases=[])],
        predecessors=[Chapter(title="Ursprung", position=0, body="Mira kam.")],
    )
    assert "Referenced entities:" not in prompt  # 22 < 20 + 3
    assert "Previous chapters:" not in prompt  # 20 < 18 + 3

    whole = continuation_prompt(
        budgets=ContextBudgets(
            immediate_text=2000, referenced_entities=23, recent_chapters=21, style_hints=0
        ),
        novel_title="Der Nebel",
        chapter_title="Ankunft",
        body="Der Nebel kam von See.",
        entities=[Entity(name="Mira", type="character", content="Die Wanderin.", aliases=[])],
        predecessors=[Chapter(title="Ursprung", position=0, body="Mira kam.")],
    )
    entities_section = whole[
        whole.index("Referenced entities:") : whole.index("Previous chapters:")
    ]
    assert len(entities_section) <= 23
    assert "Mira" not in whole  # no entry fits beside the heading: skipped silently
    chapters_section = whole[
        whole.index("Previous chapters:") : whole.index("Continue the chapter")
    ]
    assert len(chapters_section) <= 21
    assert "Ursprung" not in whole  # the tail does not fit beside the heading: dropped


def test_predecessors_render_nearest_first_with_hard_cut_tails() -> None:
    """Nearest predecessor first; the slice is filled greedily and never overflows."""
    budgets = ContextBudgets(
        immediate_text=2000, referenced_entities=0, recent_chapters=200, style_hints=0
    )
    near_body = "Nahe beim Ufer. " * 4
    old_body = "Der Ursprung lag weiter draussen. " * 8
    prompt = continuation_prompt(
        budgets=budgets,
        novel_title="Der Nebel",
        chapter_title="Ankunft",
        body="Der Nebel kam von See.",
        predecessors=[
            Chapter(title="Naehe", position=1, body=near_body),
            Chapter(title="Ursprung", position=0, body=old_body),
        ],
    )
    assert prompt.index("### Naehe") < prompt.index("### Ursprung")
    section = prompt[prompt.index("Previous chapters:") : prompt.index("Continue the chapter")]
    assert len(section) <= 200
    assert near_body in prompt  # first claim: the whole short body fits
    assert old_body not in prompt  # the remainder was hard-cut
    assert old_body[-60:] in prompt


def test_style_notes_truncate_to_the_style_budget() -> None:
    """Genre and blurb render under their heading, hard-cut to the slice."""
    budgets = ContextBudgets(
        immediate_text=2000, referenced_entities=0, recent_chapters=0, style_hints=60
    )
    prompt = continuation_prompt(
        budgets=budgets,
        novel_title="Der Nebel",
        chapter_title="Ankunft",
        body="Der Nebel kam von See.",
        genre="Mystery",
        blurb="A" * 100,
    )
    section = prompt[prompt.index("Style notes:") : prompt.index("Continue the chapter")]
    assert section == "Style notes:\nGenre: Mystery\nBlurb: " + "A" * 25


def test_style_notes_are_omitted_when_the_novel_carries_neither_genre_nor_blurb() -> None:
    budgets = ContextBudgets(
        immediate_text=2000, referenced_entities=500, recent_chapters=0, style_hints=200
    )
    prompt = continuation_prompt(
        budgets=budgets,
        novel_title="Der Nebel",
        chapter_title="Ankunft",
        body="Der Nebel kam von See.",
    )
    assert "Style notes:" not in prompt


async def _fixture_novel(session: AsyncSession) -> Novel:
    """A novel with style facts, two predecessor chapters and three entities."""
    service = WritingService(session, LOCAL_USER_ID)
    novel = await service.create_novel("Der Nebel", genre="Mystery", blurb="Ein Nebeljahr.")
    first = await service.create_chapter(novel.id, "Ankunft")
    first.body = "Der Ursprung: Mira kam von See."
    second = await service.create_chapter(novel.id, "Naehe")
    second.body = "Die Naehe wuchs. Brander schwieg."
    session.add_all(
        [
            Entity(
                user_id=LOCAL_USER_ID,
                novel_id=novel.id,
                name="Mira",
                type="character",
                content="Die Wanderin von der See.",
                aliases=["die Wanderin"],
            ),
            Entity(
                user_id=LOCAL_USER_ID,
                novel_id=novel.id,
                name="Brander",
                type="character",
                content="Der Schweiger.",
                aliases=[],
            ),
            Entity(
                user_id=LOCAL_USER_ID,
                novel_id=novel.id,
                name="Nebelgeist",
                type="generic",
                content="Wird im Text nie genannt.",
                aliases=[],
            ),
        ]
    )
    await session.commit()
    return novel


async def test_an_entity_found_by_alias_in_different_case_is_ordered_by_first_occurrence() -> None:
    """The scan folds both sides: an uppercase alias match orders before a later name."""
    async with Session() as session:
        novel = await _fixture_novel(session)
        service = WritingService(session, LOCAL_USER_ID)
        current = await service.create_chapter(novel.id, "Schweigen")
        current.body = "DIE WANDERIN ging voran. Spater schwieg Brander."
        await session.commit()

        prompt = await service.continuation_prompt(
            current.id, context_window=8192, max_output_tokens=1024, model="fake"
        )
    assert prompt.index("### Mira (character)") < prompt.index("### Brander (character)")
    assert "Die Wanderin von der See." in prompt
    assert "Der Schweiger." in prompt
    assert "Nebelgeist" not in prompt  # never named in the tail: excluded


async def test_predecessors_arrive_nearest_first() -> None:
    """The gathering hands the builder position 1 before position 0."""
    async with Session() as session:
        novel = await _fixture_novel(session)
        service = WritingService(session, LOCAL_USER_ID)
        current = await service.create_chapter(novel.id, "Drittes")
        current.body = "Das Kapitel endet hier."
        await session.commit()

        prompt = await service.continuation_prompt(current.id)
    assert prompt.index("### Naehe") < prompt.index("### Ankunft")
    assert "Die Naehe wuchs. Brander schwieg." in prompt
    assert "Der Ursprung: Mira kam von See." in prompt
    assert "Das Kapitel endet hier." in prompt  # the current chapter is the tail itself
    assert "### Drittes" not in prompt


async def test_a_small_window_omits_sections_whose_heading_does_not_fit() -> None:
    """Rooms of 10-35 put the small slices below their own headings (the real
    allocator's floors): the sections are omitted whole — no truncated heading
    rides into the prompt, and no section exceeds its slice."""
    async with Session() as session:
        novel = await _fixture_novel(session)
        service = WritingService(session, LOCAL_USER_ID)
        current = await service.create_chapter(novel.id, "Klein")
        current.body = "Rest."
        await session.commit()

        # allocate(1000, 997): room 10 — entities 2, chapters 1, style 0.
        prompt = await service.continuation_prompt(
            current.id, context_window=1000, max_output_tokens=997, model="fake"
        )
        # allocate(1000, 990): room 35 — entities 8, chapters 3, style 1 with a
        # genre set: still below the heading, so nothing partial may render.
        wider = await service.continuation_prompt(
            current.id, context_window=1000, max_output_tokens=990, model="fake"
        )
    scaffold = "Novel: Der Nebel\nChapter: Klein\n\nText so far:\n\n\n" + _INSTRUCTION_END
    assert prompt == scaffold
    assert wider == scaffold


async def test_an_impossible_pair_is_refused_before_any_gathering() -> None:
    """allocate runs first: the refusal names the pair and beats NotFoundError."""
    async with Session() as session:
        novel = await _fixture_novel(session)
        service = WritingService(session, LOCAL_USER_ID)
        current = await service.create_chapter(novel.id, "Weiter")
        await session.commit()

        with pytest.raises(BudgetImpossibleError) as raised:
            await service.continuation_prompt(
                current.id, context_window=4096, max_output_tokens=5000, model="vendor/small"
            )
        message = str(raised.value)
        assert "4096" in message
        assert "5000" in message
        assert "vendor/small" in message
        # A missing chapter stays inside the refusal: gathering never ran.
        with pytest.raises(BudgetImpossibleError):
            await service.continuation_prompt(
                uuid4(), context_window=4096, max_output_tokens=5000, model="vendor/small"
            )


async def test_a_tiny_window_omits_the_three_small_sections() -> None:
    """room 3 = floor((1000 - 999) * 3.5): the 25/10/5 % floors stay zero, omitted."""
    async with Session() as session:
        novel = await _fixture_novel(session)
        service = WritingService(session, LOCAL_USER_ID)
        current = await service.create_chapter(novel.id, "Ende")
        current.body = "Sie schwiegen."
        await session.commit()

        prompt = await service.continuation_prompt(
            current.id, context_window=1000, max_output_tokens=999, model="fake"
        )
    assert "Referenced entities:" not in prompt
    assert "Previous chapters:" not in prompt
    assert "Style notes:" not in prompt
    assert "Mystery" not in prompt
    assert "Mira" not in prompt
    # The 3-character room is smaller than the uncuttable scaffolding, so the
    # tail renders empty; the sections are absent, not empty headings.
    assert "Text so far:\n\n" in prompt


async def test_the_entity_repository_lists_only_its_novels_entities() -> None:
    """The scan's source is scoped: another novel's entities never enter the list."""
    async with Session() as session:
        service = WritingService(session, LOCAL_USER_ID)
        novel = await service.create_novel("Erster")
        other = await service.create_novel("Zweiter")
        session.add(Entity(user_id=LOCAL_USER_ID, novel_id=novel.id, name="Mira", type="character"))
        session.add(Entity(user_id=LOCAL_USER_ID, novel_id=other.id, name="Fremd", type="generic"))
        await session.commit()

        mine = await EntityRepository(session, LOCAL_USER_ID).list_for_novel(novel.id)
        assert [entity.name for entity in mine] == ["Mira"]
