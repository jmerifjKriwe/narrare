"""Integration tests for ADR-052 WebSocket stop and recovery semantics."""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from narrare._app.main import create_app
from narrare.auth import ws_tickets
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.composer import ComposedPrompt

from ._ws_db_isolation import ws_db_test_client
from .test_session_lifecycle import _create_novel_and_chapter, _register_user

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from narrare_core.llm import LLMIntent, ResolvedModelConfig


class _CancellableModelRegistry:
    """Fake streaming registry whose first stream blocks until cancelled."""

    def __init__(self) -> None:
        self.cancelled = False
        self.stream_call_count = 0

    async def stream(
        self,
        *,
        intent: LLMIntent,
        system_prompt: str,
        user_prompt: str,
        config: ResolvedModelConfig | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Yield one partial chunk, then block on the first stream only."""
        del intent, system_prompt, user_prompt, config, api_key, base_url, kwargs
        self.stream_call_count += 1
        if self.stream_call_count == 1:
            yield StreamChunk(text="Partial preserved prose")
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                self.cancelled = True
                raise
            return

        yield StreamChunk(text="Second direction works")
        yield StreamChunk(
            text="",
            is_final=True,
            usage=TokenUsage(prompt_tokens=1, completion_tokens=3, total_tokens=4),
        )


@pytest.fixture()
def ws_recovery_env() -> Iterator[tuple[TestClient, FastAPI, _CancellableModelRegistry]]:
    """TestClient + app + cancellable fake registry for ADR-052 flows."""
    fake_registry = _CancellableModelRegistry()
    mock_composer = AsyncMock()
    mock_composer.build.return_value = ComposedPrompt(
        system="You are a creative writing assistant.",
        user="Continue the story based on the user's direction.",
    )
    app = create_app(test_mode=True)

    with (
        patch(
            "narrare.writing.router_sessions.get_model_registry",
            return_value=fake_registry,
        ),
        patch(
            "narrare.writing.router_sessions.get_composer",
            return_value=mock_composer,
        ),
        ws_db_test_client(app) as client,
    ):
        yield client, app, fake_registry


def _session_url(
    chapter_id: str,
    user_id: str,
    project_id: str,
    *,
    session_id: str | None = None,
) -> str:
    """Build the WRITE-005 WebSocket URL with a FRESH single-use ticket.

    Identity is derived from the consumed ticket (ADR-084); every
    connect/reconnect presents a new ticket (single-use — a replayed
    one is rejected with 4401). Minted via the registry directly,
    no REST hop needed in test setup.
    """
    token = ws_tickets.issue(UUID(user_id))
    url = f"/api/v1/writing/sessions/{chapter_id}?token={token}&project_id={project_id}"
    if session_id is not None:
        url += f"&session_id={session_id}"
    return url


def _receive_until(
    ws: Any,
    expected_type: str,
    *,
    attempts: int = 20,
) -> dict[str, Any]:
    """Receive WebSocket JSON messages until ``expected_type`` appears."""
    for _ in range(attempts):
        message = ws.receive_json()
        if message.get("type") == expected_type:
            return dict(message)
    raise AssertionError(f"Did not receive {expected_type!r} within {attempts} messages")


def _wait_for(predicate: Any, *, timeout: float = 1.0) -> None:
    """Wait briefly for the TestClient event-loop thread to observe a condition."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for asynchronous condition")


def _active_invocation_id(app: FastAPI, session_id: str) -> str:
    """Return the active invocation id from the shared registry."""
    turn = app.state.active_turn_registry.get(session_id)
    assert turn is not None, "Expected an active streaming turn"
    return turn.invocation_id


def _load_session_state(app: FastAPI, session_id: str) -> Any:
    """Load a session state from the shared session manager."""
    return asyncio.run(app.state.session_manager._load(UUID(session_id)))  # pyright: ignore[reportPrivateUsage]


def _persist_session_state(app: FastAPI, state: Any) -> None:
    """Persist a mutated session state through the shared session manager."""
    asyncio.run(app.state.session_manager._persist(state))  # pyright: ignore[reportPrivateUsage]


def test_stop_generation_mid_stream_preserves_partial_and_allows_next_direction(
    ws_recovery_env: tuple[TestClient, FastAPI, _CancellableModelRegistry],
) -> None:
    """stop_generation cancels server work, preserves partials, and keeps session active."""
    client, app, fake_registry = ws_recovery_env
    user_id, auth_headers = _register_user(client)
    novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

    with client.websocket_connect(_session_url(chapter_id, user_id, novel_id)) as ws:
        session_id = ws.receive_json()["session_id"]
        ws.send_json({"type": "user_direction", "content": "Write until I stop you"})
        _receive_until(ws, "text_chunk")

        invocation_id = _active_invocation_id(app, session_id)
        ws.send_json({"type": "stop_generation", "invocation_id": invocation_id})
        stopped = _receive_until(ws, "generation_stopped")

        assert stopped["reason"] == "user_stop"
        assert stopped["partial_prose"] == "Partial preserved prose"
        assert stopped["invocation_id"] == invocation_id
        assert _load_session_state(app, session_id) is not None
        _wait_for(lambda: fake_registry.cancelled)

        ws.send_json({"type": "user_direction", "content": "Continue after stop"})
        done = _receive_until(ws, "text_done")
        assert done["text"] == "Second direction works"


def test_disconnect_then_reconnect_recovers_partial_and_transcript_tail(
    ws_recovery_env: tuple[TestClient, FastAPI, _CancellableModelRegistry],
) -> None:
    """A reconnect with session_id reattaches to the same shared session state."""
    client, app, _ = ws_recovery_env
    user_id, auth_headers = _register_user(client)
    novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

    with client.websocket_connect(_session_url(chapter_id, user_id, novel_id)) as ws:
        session_id = ws.receive_json()["session_id"]
        ws.send_json({"type": "user_direction", "content": "Keep this session alive"})
        _receive_until(ws, "text_chunk")
        invocation_id = _active_invocation_id(app, session_id)

    with client.websocket_connect(
        _session_url(chapter_id, user_id, novel_id, session_id=session_id),
    ) as ws:
        recovered = ws.receive_json()
        assert recovered["type"] == "session_recovered"
        assert recovered["session_id"] == session_id
        assert recovered["partial_prose"] == "Partial preserved prose"
        assert recovered["transcript_tail"][-1]["content"] == "Keep this session alive"

        ws.send_json({"type": "stop_generation", "invocation_id": invocation_id})
        assert _receive_until(ws, "generation_stopped")["reason"] == "user_stop"


def test_reconnect_to_expired_session_returns_recovery_failed(
    ws_recovery_env: tuple[TestClient, FastAPI, _CancellableModelRegistry],
) -> None:
    """Inactive cached sessions fail recovery with the typed expired reason."""
    client, app, _ = ws_recovery_env
    user_id, auth_headers = _register_user(client)
    novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

    with client.websocket_connect(_session_url(chapter_id, user_id, novel_id)) as ws:
        session_id = ws.receive_json()["session_id"]

    state = _load_session_state(app, session_id)
    assert state is not None
    state.is_active = False
    _persist_session_state(app, state)

    with client.websocket_connect(
        _session_url(chapter_id, user_id, novel_id, session_id=session_id),
    ) as ws:
        failed = ws.receive_json()
        assert failed == {"type": "recovery_failed", "reason": "session_expired"}


def test_reconnect_to_nonexistent_session_returns_recovery_failed(
    ws_recovery_env: tuple[TestClient, FastAPI, _CancellableModelRegistry],
) -> None:
    """Unknown session ids fail recovery with the typed not_found reason."""
    client, _, _ = ws_recovery_env
    user_id, auth_headers = _register_user(client)
    novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)
    missing_session_id = str(uuid4())

    with client.websocket_connect(
        _session_url(chapter_id, user_id, novel_id, session_id=missing_session_id),
    ) as ws:
        failed = ws.receive_json()
        assert failed == {"type": "recovery_failed", "reason": "session_not_found"}


def test_reconnect_with_project_mismatch_returns_ownership_mismatch(
    ws_recovery_env: tuple[TestClient, FastAPI, _CancellableModelRegistry],
) -> None:
    """A session cannot be recovered through a different project owner tuple."""
    client, _, _ = ws_recovery_env
    user_id, auth_headers = _register_user(client)
    novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)
    other_novel_id, _ = _create_novel_and_chapter(client, auth_headers)

    with client.websocket_connect(_session_url(chapter_id, user_id, novel_id)) as ws:
        session_id = ws.receive_json()["session_id"]

    with client.websocket_connect(
        _session_url(chapter_id, user_id, other_novel_id, session_id=session_id),
    ) as ws:
        failed = ws.receive_json()
        assert failed == {"type": "recovery_failed", "reason": "ownership_mismatch"}


def test_idle_timeout_emits_connection_lost_and_keeps_session_recoverable(
    ws_recovery_env: tuple[TestClient, FastAPI, _CancellableModelRegistry],
) -> None:
    """Idle timeout reports connection loss without deleting cached session state."""
    client, app, _ = ws_recovery_env
    user_id, auth_headers = _register_user(client)
    novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

    async def _raise_timeout(coro: object, *_: object, **__: object) -> object:
        if inspect.iscoroutine(coro):
            coro.close()
        raise TimeoutError

    with (
        patch("narrare.writing.ws_handler.asyncio.wait_for", new=_raise_timeout),
        client.websocket_connect(_session_url(chapter_id, user_id, novel_id)) as ws,
    ):
        session_id = ws.receive_json()["session_id"]
        lost = ws.receive_json()
        assert lost["type"] == "connection_lost"

    assert _load_session_state(app, session_id) is not None


def test_shared_cache_allows_later_connection_to_recover_original_session(
    ws_recovery_env: tuple[TestClient, FastAPI, _CancellableModelRegistry],
) -> None:
    """Fresh connections create distinct sessions; session_id reattaches to the first."""
    client, _, _ = ws_recovery_env
    user_id, auth_headers = _register_user(client)
    novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

    with client.websocket_connect(_session_url(chapter_id, user_id, novel_id)) as ws:
        first_session_id = ws.receive_json()["session_id"]

    with client.websocket_connect(_session_url(chapter_id, user_id, novel_id)) as ws:
        second_session_id = ws.receive_json()["session_id"]

    assert first_session_id != second_session_id

    with client.websocket_connect(
        _session_url(chapter_id, user_id, novel_id, session_id=first_session_id),
    ) as ws:
        recovered = ws.receive_json()
        assert recovered["type"] == "session_recovered"
        assert recovered["session_id"] == first_session_id
