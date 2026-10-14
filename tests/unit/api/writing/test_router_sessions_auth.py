"""Regression tests — ADR-084 ticket authentication on the writing WS route.

Regression-first: the spoofable client-supplied ``user_id`` query param is
GONE. Identity is derived server-side from a single-use ticket consumed at
the handshake (close-code order: ticket→4401, project_id→4001,
origin→1008, rate-limit on derived id→4003).
"""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from narrare._app.config import Settings as AppSettings
from narrare.auth import ws_tickets
from narrare.writing.router_sessions import interactive_session

if TYPE_CHECKING:
    from collections.abc import Iterator

USER = UUID("00000000-0000-0000-0000-0000000000aa")

TICKET_CLOSE_CODE = 4401


@pytest.fixture(autouse=True)
def _clean_ticket_registry() -> None:
    """Isolate the process-global ticket registry per test."""
    ws_tickets._TICKETS.clear()


@pytest.fixture
def mock_websocket() -> AsyncMock:
    """A mock WebSocket with a trusted localhost origin."""
    ws = AsyncMock()
    ws.app = MagicMock(spec=["state"])
    ws.headers = {"origin": "http://localhost:3000"}
    return ws


@pytest.fixture
def chapter_id() -> UUID:
    return uuid4()


@pytest.fixture
def project_id() -> UUID:
    return uuid4()


def _expired_ticket(user_id: UUID) -> str:
    """Mint a ticket whose TTL already elapsed (injected past ``now``)."""
    past = datetime.now(UTC) - timedelta(seconds=120)
    return ws_tickets.issue(user_id, now=lambda: past)


@contextmanager
def _success_path_env(project_id: UUID) -> Iterator[tuple[AsyncMock, MagicMock]]:
    """Patch the full success-path dependency stack; yield (handler, limiter).

    Mirrors ``test_router_sessions_basic.py``'s wiring so the derived
    identity can be asserted end-to-end through handler.handle(). The
    ownership-seeded repositories (IDOR S3 gate) admit the caller for
    ``project_id``.
    """
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.llm.model_routing import ResolvedModel
    from tests.unit.api.writing.ws_test_helpers import owned_project_repos

    resolved_model = ResolvedModel(config=ResolvedModelConfig(provider_name="t", model_id="m"))
    mock_handler = AsyncMock()
    mock_db_session = AsyncMock()
    mock_async_gen = AsyncMock()
    mock_async_gen.__anext__ = AsyncMock(return_value=mock_db_session)
    mock_async_gen.aclose = AsyncMock()
    mock_resolver = AsyncMock()
    mock_resolver.resolve = AsyncMock(return_value=resolved_model)
    token_instance = AsyncMock()
    token_instance.get_resolved_limits = AsyncMock(return_value=TokenLimitOverrides())
    novel_cls, chapter_cls = owned_project_repos(project_id)

    with (
        patch("narrare._app.config.get_settings") as mock_get_settings,
        patch("narrare.writing.deps_ws.get_session_manager"),
        patch("narrare.writing.deps_ws.get_active_turn_registry"),
        patch("narrare.writing.deps_ws.get_turn_state"),
        patch("narrare.writing.deps_ws.get_session_control_service"),
        patch("narrare._app.dependencies.get_model_registry"),
        patch("narrare._app.dependencies.get_composer"),
        patch("narrare._app.database.get_async_session", return_value=mock_async_gen),
        patch("narrare._app.dependencies_pipeline.get_invocation_pipeline"),
        patch(
            "narrare.settings.token_limits.service.TokenLimitsService",
            return_value=token_instance,
        ),
        patch(
            "narrare._app.dependencies_services.get_model_routing_resolver",
            return_value=mock_resolver,
        ),
        patch(
            "narrare.writing.ws_factory.build_writing_session_handler",
            return_value=mock_handler,
        ),
        patch("narrare_core.llm.run_limits.DefaultRunLimitResolver"),
        patch("narrare._app.rate_limits.AI_WS_LIMITER.try_acquire") as mock_try_acquire,
        patch("narrare.novels.repository.NovelRepository", novel_cls),
        patch("narrare.chapters.repository.ChapterRepository", chapter_cls),
    ):
        mock_settings = MagicMock(spec=AppSettings)
        mock_settings.csrf_trusted_origins = ["http://localhost:3000"]
        mock_get_settings.return_value = mock_settings
        mock_try_acquire.return_value = True
        yield mock_handler, mock_try_acquire


class TestSignatureRegression:
    """The spoofable ``user_id`` query param is removed outright (D1:a)."""

    def test_user_id_query_param_is_gone_and_token_exists(self) -> None:
        params = inspect.signature(interactive_session).parameters
        assert "user_id" not in params, "client-asserted identity must not exist (ADR-084)"
        assert "token" in params


class TestTicketGate:
    """Missing/unknown/expired/consumed tickets → uniform 4401 rejection."""

    async def _reject_and_capture(
        self,
        chapter_id: UUID,
        project_id: UUID,
        token: str,
    ) -> str:
        """Run one rejected handshake on a FRESH socket; return the client message."""
        ws = AsyncMock()
        ws.app = MagicMock(spec=["state"])
        ws.headers = {"origin": "http://localhost:3000"}
        await interactive_session(ws, chapter_id, token=token, project_id=project_id)
        ws.accept.assert_awaited_once()
        ws.send_json.assert_awaited_once()
        assert ws.close.await_args.kwargs["code"] == TICKET_CLOSE_CODE
        assert ws.close.await_count == 1
        return str(ws.send_json.await_args.args[0]["message"])

    async def test_connect_without_token_rejected_4401(
        self, mock_websocket: AsyncMock, chapter_id: UUID, project_id: UUID
    ) -> None:
        await self._reject_and_capture(chapter_id, project_id, token="")

    async def test_old_client_sending_only_user_id_rejected_4401(
        self, mock_websocket: AsyncMock, chapter_id: UUID, project_id: UUID
    ) -> None:
        """Old clients still sending ``?user_id=…`` (no token) are rejected —
        unknown extra query params are ignored by FastAPI, the missing
        ticket is what closes the socket (sanctioned break, ADR-084 §5)."""
        message = await self._reject_and_capture(chapter_id, project_id, token="")
        assert "ticket" in message.lower()

    async def test_unknown_token_rejected_4401(
        self, mock_websocket: AsyncMock, chapter_id: UUID, project_id: UUID
    ) -> None:
        await self._reject_and_capture(chapter_id, project_id, token="forged-ticket-value")

    async def test_consumed_ticket_rejected_4401(
        self, mock_websocket: AsyncMock, chapter_id: UUID, project_id: UUID
    ) -> None:
        token = ws_tickets.issue(USER)
        ws_tickets.consume(token)  # burn it (replay)
        await self._reject_and_capture(chapter_id, project_id, token)

    async def test_expired_ticket_rejected_4401(
        self, mock_websocket: AsyncMock, chapter_id: UUID, project_id: UUID
    ) -> None:
        token = _expired_ticket(USER)
        await self._reject_and_capture(chapter_id, project_id, token)

    async def test_all_ticket_failures_send_identical_client_message(
        self, mock_websocket: AsyncMock, chapter_id: UUID, project_id: UUID
    ) -> None:
        """Anti-enumeration: missing ≡ unknown ≡ expired ≡ consumed — the
        client message is one uniform string (the registry's own)."""
        consumed = ws_tickets.issue(USER)
        ws_tickets.consume(consumed)
        cases = ["", "forged-ticket-value", _expired_ticket(USER), consumed]

        messages = [
            await self._reject_and_capture(chapter_id, project_id, token) for token in cases
        ]

        assert len(set(messages)) == 1
        with pytest.raises(ws_tickets.WsTicketError) as exc_info:
            ws_tickets.consume("garbage")
        assert messages[0] == str(exc_info.value)


class TestHandshakeOrder:
    """ticket → project_id → origin → rate limit (ADR-084 §4)."""

    async def test_invalid_ticket_rejected_before_origin_and_rate_limit(
        self, mock_websocket: AsyncMock, chapter_id: UUID, project_id: UUID
    ) -> None:
        mock_websocket.headers["origin"] = "http://evil.com"
        with patch("narrare._app.rate_limits.AI_WS_LIMITER.try_acquire") as mock_try:
            await interactive_session(
                mock_websocket, chapter_id, token="bad", project_id=project_id
            )
            mock_try.assert_not_called()
        assert mock_websocket.close.await_args.kwargs["code"] == TICKET_CLOSE_CODE

    async def test_missing_project_id_after_valid_ticket_closes_4001(
        self, mock_websocket: AsyncMock, chapter_id: UUID
    ) -> None:
        token = ws_tickets.issue(USER)
        await interactive_session(mock_websocket, chapter_id, token=token, project_id=None)
        assert mock_websocket.close.await_args.kwargs["code"] == 4001

    async def test_untrusted_origin_after_valid_ticket_closes_1008(
        self, mock_websocket: AsyncMock, chapter_id: UUID, project_id: UUID
    ) -> None:
        mock_websocket.headers["origin"] = "http://evil.com"
        token = ws_tickets.issue(USER)
        # N08: pin a NON-test environment — the suite runs under
        # ENVIRONMENT=test (where the origin gate relaxes, REST CSRF
        # parity); this handshake-ORDER pin requires the strict posture.
        # Alias key via model_validate: a field-name ctor kwarg for the
        # aliased csrf field would be silently dropped.
        dev_settings = AppSettings.model_validate(
            {
                "environment": "development",
                "NARRARE_CSRF_TRUSTED_ORIGINS": ["http://localhost:3000"],
            },
        )
        with patch("narrare._app.config.get_settings", return_value=dev_settings):
            await interactive_session(
                mock_websocket, chapter_id, token=token, project_id=project_id
            )
        assert mock_websocket.close.await_args.kwargs["code"] == 1008

    async def test_rate_limited_after_valid_ticket_closes_4003(
        self, mock_websocket: AsyncMock, chapter_id: UUID, project_id: UUID
    ) -> None:
        token = ws_tickets.issue(USER)
        with patch("narrare._app.rate_limits.AI_WS_LIMITER.try_acquire", return_value=False):
            await interactive_session(
                mock_websocket, chapter_id, token=token, project_id=project_id
            )
        assert mock_websocket.close.await_args.kwargs["code"] == 4003


class TestDerivedIdentity:
    """The ticket-bound identity flows downstream; nothing is client-asserted."""

    async def test_valid_ticket_proceeds_with_derived_identity(
        self, mock_websocket: AsyncMock, chapter_id: UUID, project_id: UUID
    ) -> None:
        token = ws_tickets.issue(USER)  # server-side mint; client sends only token
        with _success_path_env(project_id) as (mock_handler, mock_try_acquire):
            await interactive_session(
                mock_websocket, chapter_id, token=token, project_id=project_id
            )

        mock_handler.handle.assert_awaited_once_with(
            mock_websocket,
            chapter_id,
            str(USER),  # derived from the ticket, never from the query string
            project_id,
            session_id=None,
        )
        # Rate-limit key uses the DERIVED identity (unspoofable per-user limit).
        rate_key = mock_try_acquire.call_args.args[0]  # sync call, not awaited
        assert rate_key == f"ws:writing:{USER}:{chapter_id}"
        # Ticket was burned by the handshake.
        with pytest.raises(ws_tickets.WsTicketError):
            ws_tickets.consume(token)
        mock_websocket.send_json.assert_not_called()
        mock_websocket.close.assert_not_called()
