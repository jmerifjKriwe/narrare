"""Tests for WritingSessionMessageRouter recover_session routing (ADR-052)."""

from __future__ import annotations

from uuid import uuid4

from narrare.writing._ws_cache import InMemorySessionCache
from narrare.writing.ws_message_router import WritingSessionMessageRouter
from narrare.writing.ws_session_context import WritingSessionContext
from narrare_core.writing.session_manager import SessionManager


class _RecordingSocket:
    """Minimal WebSocket-like object that records sent messages."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_json(self, data: dict[str, object]) -> None:
        self.sent.append(data)


class _StubControl:
    """Stub WritingSessionControlProtocol for recover routing."""

    def __init__(self) -> None:
        self.received_session_id: str | None = None
        self.received_sink: object | None = None
        self.outcome: dict[str, object] = {
            "kind": "recovered",
            "session_id": "",
            "stream_status": "streaming",
            "last_sequence": 2,
            "active_partial_prose": "partial",
            "active_invocation_id": str(uuid4()),
            "transcript_tail": [{"role": "assistant", "content": "partial"}],
        }

    async def stop_generation(
        self,
        session_id: object,
        invocation_id: object,
    ) -> dict[str, object]:
        return {
            "status": "no_active_turn",
            "partial_prose": "",
            "invocation_id": str(invocation_id),
        }

    async def reattach_session(
        self,
        session_id: object,
        user_id: object,
        project_id: object,
        *,
        new_sink: object,
    ) -> dict[str, object]:
        self.received_session_id = str(session_id)
        self.received_sink = new_sink
        result = dict(self.outcome)
        result["session_id"] = str(session_id)
        return result


class _DummyDispatcher:
    async def dispatch(self, *args: object, **kwargs: object) -> None:
        """No-op dispatcher for router construction."""


def _make_router(control: _StubControl) -> WritingSessionMessageRouter:
    session_manager = SessionManager(cache=InMemorySessionCache())
    return WritingSessionMessageRouter(
        session_manager=session_manager,
        direction_dispatcher=_DummyDispatcher(),  # type: ignore[arg-type]
        control_service=control,  # type: ignore[arg-type]
        registry=object(),  # type: ignore[arg-type]
        composer=object(),  # type: ignore[arg-type]
        config_provider=object(),  # type: ignore[arg-type]
        invocation_pipeline=None,
        run_limit_resolver=object(),  # type: ignore[arg-type]
    )


def _make_context() -> WritingSessionContext:
    return WritingSessionContext(
        session_id=uuid4(),
        user_id=uuid4(),
        project_id=uuid4(),
        chapter_id=uuid4(),
        mode="interactive_session",
    )


class TestRouteRecoverSession:
    """recover_session message routing."""

    async def test_route_recover_session_emits_session_recovered(self) -> None:
        control = _StubControl()
        router = _make_router(control)
        context = _make_context()
        ws = _RecordingSocket()
        session_id = uuid4()

        await router.route(
            ws,  # type: ignore[arg-type]
            context,
            {"type": "recover_session", "session_id": str(session_id)},
        )

        assert control.received_session_id == str(session_id)
        assert control.received_sink is not None
        assert ws.sent == [
            {
                "type": "session_recovered",
                "session_id": str(session_id),
                "stream_status": "streaming",
                "partial_prose": "partial",
                "sequence": 2,
                "transcript_tail": [{"role": "assistant", "content": "partial"}],
            }
        ]

    async def test_route_recover_session_emits_recovery_failed(self) -> None:
        control = _StubControl()
        control.outcome = {"kind": "expired", "session_id": ""}
        router = _make_router(control)
        context = _make_context()
        ws = _RecordingSocket()
        session_id = uuid4()

        await router.route(
            ws,  # type: ignore[arg-type]
            context,
            {"type": "recover_session", "session_id": str(session_id)},
        )

        assert ws.sent == [
            {
                "type": "recovery_failed",
                "reason": "session_expired",
            }
        ]

    async def test_route_recover_session_with_invalid_session_id_sends_error(self) -> None:
        control = _StubControl()
        router = _make_router(control)
        context = _make_context()
        ws = _RecordingSocket()

        await router.route(
            ws,  # type: ignore[arg-type]
            context,
            {"type": "recover_session", "session_id": "not-a-uuid"},
        )

        assert ws.sent[0]["type"] == "error"
