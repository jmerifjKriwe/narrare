"""Tests for WritingSessionMessageRouter stop_generation routing (ADR-052).

Covers:
1. ``stop_generation`` message calls the control service and emits
   ``generation_stopped`` with the partial prose.
2. ``stop_generation`` with missing ``invocation_id`` sends an error.
"""

from __future__ import annotations

from uuid import uuid4

from narrare.writing._ws_cache import InMemorySessionCache
from narrare.writing.ws_message_router import WritingSessionMessageRouter
from narrare.writing.ws_session_context import WritingSessionContext
from narrare_core.writing.session_manager import SessionManager

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _RecordingSocket:
    """Minimal WebSocket-like that records sent messages."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_json(self, data: dict[str, object]) -> None:
        self.sent.append(data)


class _StubControl:
    """Stub WritingSessionControlProtocol for testing."""

    def __init__(self) -> None:
        self.received_invocation: str | None = None
        self.received_session_id: object | None = None
        self.stop_result: dict[str, object] = {
            "status": "stopped",
            "partial_prose": "partial text",
            "invocation_id": None,
        }

    async def stop_generation(
        self,
        session_id: object,
        invocation_id: object,
    ) -> dict[str, object]:
        self.received_session_id = session_id
        self.received_invocation = str(invocation_id)
        result = dict(self.stop_result)
        result["invocation_id"] = str(invocation_id)
        return result

    async def reattach_session(
        self,
        session_id: object,
        user_id: object,
        project_id: object,
    ) -> dict[str, object]:
        return {"kind": "not_found"}


class _DummyDispatcher:
    """Stub dispatcher that does nothing."""

    async def dispatch(self, *args: object, **kwargs: object) -> None:
        pass


def _make_router(control: _StubControl) -> WritingSessionMessageRouter:
    session_manager = SessionManager(cache=InMemorySessionCache())
    return WritingSessionMessageRouter(
        session_manager=session_manager,
        direction_dispatcher=_DummyDispatcher(),  # type: ignore[arg-type]
        control_service=control,  # type: ignore[arg-type]
        registry=object(),  # type: ignore[arg-type]
        composer=object(),  # type: ignore[arg-type]
        config=object(),  # type: ignore[arg-type]
        invocation_pipeline=None,
        run_limit_resolver=object(),  # type: ignore[arg-type]
    )


async def _make_context(session_manager: SessionManager) -> WritingSessionContext:
    from uuid import uuid4 as _uuid4

    session_id = await session_manager.create_session(
        chapter_id=_uuid4(),
        project_id=_uuid4(),
        user_id=_uuid4(),
    )
    return WritingSessionContext(
        session_id=session_id,
        user_id=_uuid4(),
        project_id=_uuid4(),
        chapter_id=_uuid4(),
        mode="interactive_session",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRouteStopGeneration:
    """stop_generation message routing."""

    async def test_route_stop_generation_calls_control_and_emits_generation_stopped(
        self,
    ) -> None:
        control = _StubControl()
        router = _make_router(control)
        session_manager = SessionManager(cache=InMemorySessionCache())
        context = await _make_context(session_manager)
        ws = _RecordingSocket()
        invocation = uuid4()

        await router.route(
            ws,  # type: ignore[arg-type]
            context,
            {"type": "stop_generation", "invocation_id": str(invocation)},
        )

        assert control.received_invocation == str(invocation)
        stopped = [m for m in ws.sent if m.get("type") == "generation_stopped"]
        assert len(stopped) == 1
        assert stopped[0]["reason"] == "user_stop"
        assert stopped[0]["partial_prose"] == "partial text"
        assert stopped[0]["invocation_id"] == str(invocation)
        assert stopped[0]["sequence"] == 0
        assert "status" not in stopped[0]

    async def test_route_stop_generation_with_missing_invocation_sends_error(
        self,
    ) -> None:
        control = _StubControl()
        router = _make_router(control)
        session_manager = SessionManager(cache=InMemorySessionCache())
        context = await _make_context(session_manager)
        ws = _RecordingSocket()

        await router.route(
            ws,  # type: ignore[arg-type]
            context,
            {"type": "stop_generation"},
        )

        errors = [m for m in ws.sent if m.get("type") == "error"]
        assert len(errors) == 1
