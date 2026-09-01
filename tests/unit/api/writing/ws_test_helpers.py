"""Shared helpers for WebSocket writing-session unit tests.

Hosts the mock WebSocket, fake composer, stream fakes, config builder, and
the ``_make_handler`` wiring shared by the writing-session handler tests.
Keeping the helpers here (instead of in each test module) keeps those
modules under the RULE-04 size limit and avoids duplicating fixtures.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID

from fastapi import WebSocketDisconnect

from narrare._app.config import Settings as AppSettings
from narrare.auth import ws_tickets
from narrare.writing._ws_cache import InMemorySessionCache
from narrare.writing.router_sessions import interactive_session
from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
from narrare.writing.ws_factory import build_writing_session_handler
from narrare.writing.ws_session_control_service import WritingSessionControlService
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.writing.session_manager import SessionManager
from narrare_core.writing.session_turn_state import SessionTurnStateStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from narrare.writing.ws_handler import WritingSessionHandler
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.context import PromptContext


async def wait_for_gateway_calls(gateway: Mock, expected: int) -> None:
    """Wait until decoupled streaming tasks reach the model registry."""
    for _ in range(50):
        if gateway.stream.call_count >= expected:
            return
        await asyncio.sleep(0.02)
    assert gateway.stream.call_count >= expected


def mint_ws_ticket(user_id: UUID | str) -> str:
    """Mint a single-use WS handshake ticket bound to ``user_id`` (ADR-084).

    Registry-direct mint for tests: every connect/reconnect needs a FRESH
    ticket (single-use — a replayed one is rejected with 4401).
    """
    bound = user_id if isinstance(user_id, UUID) else UUID(user_id)
    return ws_tickets.issue(bound)


def owned_project_repos(project_id: UUID) -> tuple[MagicMock, MagicMock]:
    """Class mocks for the IDOR-S3 handshake gate that admit the caller.

    Success-path handshake tests must pass the ownership gate in
    ``ws_session_config.resolve_ws_session_config``: ``NovelRepository``
    yields an owned novel and ``ChapterRepository`` yields a chapter bound
    to ``project_id``. Returns ``(novel_cls, chapter_cls)`` patch targets
    (the established class-level patch points).
    """
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

    novel_cls = MagicMock(spec=NovelRepository, name="NovelRepository")
    # Pure existence sentinel: both gate lookups only test non-None (no
    # novel attribute is read), so a value container beats a mock here.
    novel_cls.return_value.get_by_id = AsyncMock(return_value=SimpleNamespace(id=project_id))
    chapter_cls = MagicMock(spec=ChapterRepository, name="ChapterRepository")
    chapter_cls.return_value.get = AsyncMock(return_value=SimpleNamespace(novel_id=project_id))
    return novel_cls, chapter_cls


def stream_kwargs_for_intent(gateway: Mock, intent_value: str) -> dict[str, Any]:
    """Return kwargs for the first model-registry stream call by intent."""
    for call in gateway.stream.call_args_list:
        if call.kwargs["intent"].value == intent_value:
            return dict(call.kwargs)
    raise AssertionError(f"No stream call for intent {intent_value!r}")


class MockWebSocket:
    """Simplified async WebSocket mock for unit tests.

    After ``close()`` is called, ``receive_json()`` raises
    ``WebSocketDisconnect`` to simulate real WebSocket behaviour.
    """

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self._incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._closed = False

    async def accept(self) -> None:
        """Accept the WebSocket connection."""

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent.append(data)

    async def receive_json(self) -> dict[str, Any]:
        if self._closed:
            raise WebSocketDisconnect()
        return await self._incoming.get()

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self._closed = True

    async def receive_text(self) -> str:
        return "{}"

    async def send_text(self, message: str) -> None:
        pass

    async def enqueue(self, message: dict[str, Any]) -> None:
        await self._incoming.put(message)

    async def enqueue_end_session(self) -> None:
        """Enqueue an end_session message to break the message loop."""
        await self._incoming.put({"type": "end_session"})

    async def enqueue_disconnect(self) -> None:
        """Enqueue a sentinel that raises WebSocketDisconnect."""
        await self._incoming.put({"__disconnect__": True})


class _FakeComposer:
    """Stub PromptComposer that returns a fixed prompt."""

    async def build(
        self,
        intent: LLMIntent,
        context: PromptContext,
        *,
        db_content: str | None = None,
        user_prompt: str = "",
    ) -> ComposedPrompt:
        return ComposedPrompt(system="system-prompt", user="user-prompt")


async def _fake_stream_empty(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
    """Yield a single final chunk with empty text."""
    yield StreamChunk(text="", is_final=True, usage=TokenUsage(0, 0, 0))


async def _fake_stream_hello(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
    """Yield text chunks then a final chunk."""
    yield StreamChunk(text="Hello ")
    yield StreamChunk(text="world!", is_final=True, usage=TokenUsage(10, 20, 30))


def _make_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=100,
    )


def _make_handler(
    mode: str = "interactive_session",
) -> tuple[WritingSessionHandler, SessionManager, Mock, _FakeComposer]:
    """Create a WritingSessionHandler with mock dependencies.

    Wires a real (no-op) InvocationPipeline and DefaultRunLimitResolver
    so the full invocation contract runs for draft generation (ADR-045).
    The handler constructs WritingTurnService internally from these deps,
    so direction handling also runs the invocation contract.
    """
    cache = InMemorySessionCache()
    session_manager = SessionManager(cache=cache)
    active_turn_registry = ActiveTurnRegistry()
    turn_state = SessionTurnStateStore()
    control_service = WritingSessionControlService(
        session_manager=session_manager,
        turn_state=turn_state,
        registry=active_turn_registry,
    )
    model_registry = Mock()
    # Use Mock (not AsyncMock) for stream — code does `async for` directly
    model_registry.stream = Mock(side_effect=_fake_stream_hello)
    composer = _FakeComposer()
    config = _make_config()
    handler = build_writing_session_handler(
        session_manager=session_manager,
        registry=active_turn_registry,
        turn_state=turn_state,
        control_service=control_service,
        model_registry=model_registry,
        composer=cast("PromptComposer", composer),
        config=config,
        invocation_pipeline=InvocationPipeline(),
        run_limit_resolver=DefaultRunLimitResolver(),
        mode=mode,
    )
    return handler, session_manager, model_registry, composer


# ---------------------------------------------------------------------------
# Ownership-gate handshake harness (IDOR S3 matrix)
# ---------------------------------------------------------------------------

#: Ticket-bound caller vs. the foreign resource owner (IDOR S3 matrix).
TICKET_USER = UUID("00000000-0000-0000-0000-0000000000aa")
FOREIGN_OWNER = UUID("00000000-0000-0000-0000-0000000000bb")


def seeded_novel_repo(novel_owners: dict[UUID, UUID]) -> MagicMock:
    """Class mock honoring ``NovelRepository``'s user-scoped contract.

    ``get_by_id(novel_id, user_id)`` returns a row only for its owner:
    foreign (row exists, other owner) and unknown (no row) both yield
    ``None`` — the seam where the two scenarios actually differ.
    """
    from narrare.novels.repository import NovelRepository

    cls = MagicMock(spec=NovelRepository, name="NovelRepository")

    async def get_by_id(novel_id: UUID, user_id: UUID) -> object:
        if novel_owners.get(novel_id) == user_id:
            return SimpleNamespace(id=novel_id)
        return None

    cls.return_value.get_by_id = AsyncMock(side_effect=get_by_id)
    return cls


def seeded_chapter_repo(chapter_novels: dict[UUID, UUID]) -> MagicMock:
    """Class mock honoring ``ChapterRepository.get``'s existence contract.

    ``chapter_novels`` maps chapter_id → the novel it belongs to; a
    missing entry is an unknown chapter.
    """
    from narrare.chapters.repository import ChapterRepository

    cls = MagicMock(spec=ChapterRepository, name="ChapterRepository")

    async def get(chapter_id: UUID) -> object:
        novel_id = chapter_novels.get(chapter_id)
        if novel_id is None:
            return None
        return SimpleNamespace(id=chapter_id, novel_id=novel_id)

    cls.return_value.get = AsyncMock(side_effect=get)
    return cls


@dataclass(slots=True)
class HandshakeRun:
    """One handshake run: the socket plus the seams assertions inspect."""

    websocket: AsyncMock
    build: MagicMock
    handler: AsyncMock
    token_limits_cls: MagicMock
    resolver: MagicMock
    db_gen: AsyncMock
    control_service: MagicMock


@contextmanager
def handshake_env(
    novel_owners: dict[UUID, UUID],
    chapter_novels: dict[UUID, UUID],
    reattach_outcome: dict[str, str] | None = None,
) -> Iterator[tuple[MagicMock, AsyncMock, MagicMock, MagicMock, AsyncMock, MagicMock]]:
    """Patch the full handshake stack over ownership-seeded repositories.

    Mirrors ``test_router_sessions_auth._success_path_env`` so runs reach
    the DB block; yields ``(build, handler, token_limits_cls, resolver,
    db_gen, control_service)``.
    """
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.llm.model_routing import ResolvedModel

    resolved_model = ResolvedModel(config=ResolvedModelConfig(provider_name="t", model_id="m"))
    mock_handler = AsyncMock()
    mock_db_session = AsyncMock()
    mock_db_gen = AsyncMock()
    mock_db_gen.__anext__ = AsyncMock(return_value=mock_db_session)
    mock_db_gen.aclose = AsyncMock()
    mock_resolver = MagicMock(spec=["resolve"])
    mock_resolver.resolve = AsyncMock(return_value=resolved_model)
    token_instance = AsyncMock()
    token_instance.get_resolved_limits = AsyncMock(return_value=TokenLimitOverrides())

    with (
        patch("narrare._app.config.get_settings") as mock_get_settings,
        patch("narrare.writing.deps_ws.get_session_manager"),
        patch("narrare.writing.deps_ws.get_active_turn_registry"),
        patch("narrare.writing.deps_ws.get_turn_state"),
        patch("narrare.writing.deps_ws.get_session_control_service") as mock_css,
        patch("narrare._app.dependencies.get_model_registry"),
        patch("narrare._app.dependencies.get_composer"),
        patch("narrare._app.database.get_async_session", return_value=mock_db_gen),
        patch("narrare._app.dependencies_pipeline.get_invocation_pipeline"),
        patch(
            "narrare.settings.token_limits.service.TokenLimitsService",
            return_value=token_instance,
        ) as mock_token_cls,
        patch(
            "narrare._app.dependencies_services.get_model_routing_resolver",
            return_value=mock_resolver,
        ),
        patch(
            "narrare.writing.ws_factory.build_writing_session_handler",
        ) as mock_build,
        patch("narrare_core.llm.run_limits.DefaultRunLimitResolver"),
        patch("narrare._app.rate_limits.AI_WS_LIMITER.try_acquire", return_value=True),
        patch("narrare.novels.repository.NovelRepository", seeded_novel_repo(novel_owners)),
        patch(
            "narrare.chapters.repository.ChapterRepository",
            seeded_chapter_repo(chapter_novels),
        ),
    ):
        mock_build.return_value = mock_handler
        mock_settings = MagicMock(spec=AppSettings)
        mock_settings.csrf_trusted_origins = ["http://localhost:3000"]
        mock_get_settings.return_value = mock_settings
        if reattach_outcome is not None:
            mock_css.return_value.reattach_session = AsyncMock(return_value=reattach_outcome)
        yield mock_build, mock_handler, mock_token_cls, mock_resolver, mock_db_gen, mock_css


async def run_handshake(
    chapter_id: UUID,
    project_id: UUID,
    *,
    novel_owners: dict[UUID, UUID],
    chapter_novels: dict[UUID, UUID],
    session_id: UUID | None = None,
    reattach_outcome: dict[str, str] | None = None,
) -> HandshakeRun:
    """Run one handshake against ownership-seeded stores (fresh ticket)."""
    ws = AsyncMock()
    ws.app = MagicMock(spec=["state"])
    ws.headers = {"origin": "http://localhost:3000"}
    token = ws_tickets.issue(TICKET_USER)
    with handshake_env(novel_owners, chapter_novels, reattach_outcome) as (
        build,
        handler,
        token_limits_cls,
        resolver,
        db_gen,
        css,
    ):
        await interactive_session(
            ws,
            chapter_id,
            token=token,
            project_id=project_id,
            session_id=session_id,
        )
    return HandshakeRun(
        websocket=ws,
        build=build,
        handler=handler,
        token_limits_cls=token_limits_cls,
        resolver=resolver,
        db_gen=db_gen,
        control_service=css,
    )
