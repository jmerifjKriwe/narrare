"""Continuation: the stream is SSE, the chunks add up, and the door stays shut."""

import json
from collections.abc import AsyncIterator  # noqa: TC003
from logging import Formatter
from uuid import UUID, uuid4

import pytest
from anyio import Event
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.api.main import app
from app.capabilities.writing.prompts import continuity_prompt
from app.capabilities.writing.router import (
    _continuation_events,  # pyright: ignore[reportPrivateUsage]  test the stream's finalizer
)
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm import FakeProvider, get_provider
from app.kernel.llm.contract import CompletionEvent, CompletionRequest, Delta
from app.kernel.llm.streaming import FinalizingStreamingResponse
from app.kernel.testing.streams import StreamProbeProvider, interrupt_response

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


@pytest.mark.parametrize("fail", [False, True])
async def test_audit_failure_does_not_truncate_the_response(
    fail: bool, caplog: pytest.LogCaptureFixture
) -> None:
    """A real audit FK rejection preserves response framing and keeps text out of logs."""
    provider = StreamProbeProvider(fail=fail)
    # This user does not exist: the audit's real database commit must fail.
    response = FinalizingStreamingResponse(
        _continuation_events(provider, "audit-private-prompt", uuid4(), uuid4()),
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
        record for record in caplog.records if record.getMessage() == "continuation audit failed"
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
    """A rejected audit preserves cancellation or Starlette's ClientDisconnect."""
    waiting = Event() if interruption == "waiting" else None
    provider = StreamProbeProvider(waiting=waiting)
    response = FinalizingStreamingResponse(
        _continuation_events(provider, "question", uuid4(), uuid4()),
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
        record for record in caplog.records if record.getMessage() == "continuation audit failed"
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
        _continuation_events(provider, "question", novel_id, LOCAL_USER_ID),
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
    """Verify a successful continuation audits its novel, answer, tokens, and unknown cost."""
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
    assert row.cost_usd is None


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


async def test_a_provider_that_dies_mid_stream_errors_and_audits_the_failure() -> None:
    """Verify partial provider output is preserved with an error event and a failed audit."""
    app.dependency_overrides[get_provider] = lambda: _DyingProvider()
    try:
        async with _client() as client:
            chapter_id = await _create_chapter(client)
            response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert _deltas(response.text) == ["Halb"]  # what arrived, arrived
    assert "event: error" in response.text
    assert "event: done" not in response.text

    async with Session() as session:
        row = (await session.execute(text("SELECT status, error, task_key FROM llm_calls"))).one()
    assert row.task_key == "writing.continuation"
    assert row.status == "error"
    assert "the provider died" in row.error


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


def test_the_prompt_carries_the_chapter_tail() -> None:
    """Verify the continuation prompt carries novel and chapter titles and existing prose."""
    prompt = continuity_prompt(
        novel_title="Der Nebel", chapter_title="Ankunft", body="Der Nebel kam von See."
    )
    assert "Der Nebel" in prompt
    assert "Ankunft" in prompt
    assert "Der Nebel kam von See." in prompt
