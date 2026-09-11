"""Unit tests for auth/ws_tickets.py — ADR-084 WS ticket registry.

Covers the registry contract sketched in ADR-084 (issue → consume
roundtrip, single-use, 60 s TTL via injected ``now``, anti-enumeration
uniform error, sweep), the ``AuthService.issue_ws_ticket`` seam, and the
``POST /auth/ws-ticket`` route (Bearer-gated mint).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from narrare.auth import ws_tickets
from narrare.auth.schemas import WsTicketResponse
from narrare.auth.service import AuthService
from tests.fakes import FakeAuthRepository, FakeUserProvidersRepository

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Deterministic fake clock — 2026-01-01 is safely in the past, so tickets
# minted by OTHER tests with the real clock expire far in this clock's
# future and are never swept by these tests' injected ``now``.
BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)

USER_A = UUID("00000000-0000-0000-0000-00000000000a")
USER_B = UUID("00000000-0000-0000-0000-00000000000b")


def _at(offset_seconds: float):
    """Injected ``now`` callable at BASE_TIME + offset."""
    moment = BASE_TIME + timedelta(seconds=offset_seconds)
    return lambda: moment


@pytest.fixture(autouse=True)
def _clean_ticket_registry() -> None:
    """Isolate the process-global registry per test (order-independent
    under pytest-randomly — same stance as the export registry tests)."""
    ws_tickets._TICKETS.clear()


class TestWsTicketRegistryIssue:
    """issue(): mint a single-use ticket bound to the user."""

    def test_issue_returns_opaque_token_bound_to_user(self) -> None:
        token = ws_tickets.issue(USER_A)
        assert isinstance(token, str)
        # token_urlsafe(32) → 43 base64url chars; assert opaque strength.
        assert len(token) >= 32
        assert ws_tickets.consume(token) == USER_A

    def test_issue_returns_distinct_tokens_per_mint(self) -> None:
        assert ws_tickets.issue(USER_A) != ws_tickets.issue(USER_A)


class TestWsTicketRegistryConsume:
    """consume(): validate + burn the ticket; derive the bound user_id."""

    def test_issue_consume_roundtrip_returns_bound_user_id(self) -> None:
        token = ws_tickets.issue(USER_A)
        assert ws_tickets.consume(token) == USER_A

    def test_second_consume_of_same_token_raises(self) -> None:
        token = ws_tickets.issue(USER_A)
        ws_tickets.consume(token)
        with pytest.raises(ws_tickets.WsTicketError):
            ws_tickets.consume(token)

    def test_consume_with_expired_ticket_raises(self) -> None:
        token = ws_tickets.issue(USER_A, now=_at(0))  # expires at t=60
        with pytest.raises(ws_tickets.WsTicketError):
            ws_tickets.consume(token, now=_at(61))

    def test_consume_at_exact_ttl_boundary_still_valid(self) -> None:
        """Mirrors export semantics: expired means ``now > expires_at``."""
        token = ws_tickets.issue(USER_A, now=_at(0))  # expires at t=60
        assert ws_tickets.consume(token, now=_at(60)) == USER_A

    def test_consume_with_unknown_token_raises(self) -> None:
        with pytest.raises(ws_tickets.WsTicketError):
            ws_tickets.consume("not-a-real-ticket")

    def test_consume_with_empty_token_raises(self) -> None:
        """Old clients sending no token hit the same rejection path."""
        with pytest.raises(ws_tickets.WsTicketError):
            ws_tickets.consume("")

    def test_all_failures_raise_same_error_type_and_message(self) -> None:
        """Anti-enumeration: unknown ≡ expired ≡ consumed — same typed
        error, identical message (the precise reason is server-side only)."""
        expired = ws_tickets.issue(USER_A, now=_at(0))
        consumed = ws_tickets.issue(USER_B)
        ws_tickets.consume(consumed)

        messages: list[str] = []
        for bad_token in ("totally-unknown", expired, consumed):
            with pytest.raises(ws_tickets.WsTicketError) as exc_info:
                ws_tickets.consume(bad_token, now=_at(61))
            messages.append(str(exc_info.value))

        assert len(set(messages)) == 1


class TestWsTicketRegistrySweep:
    """sweep_expired(): drop expired-unused records only."""

    def test_sweep_drops_expired_unused_only(self) -> None:
        expired_token = ws_tickets.issue(USER_A, now=_at(0))  # expires t=60
        fresh_token = ws_tickets.issue(USER_B, now=_at(30))  # expires t=90

        dropped = ws_tickets.sweep_expired(now=_at(61))

        assert dropped == 1
        # The fresh ticket still works after the sweep.
        assert ws_tickets.consume(fresh_token, now=_at(61)) == USER_B
        # The expired one is gone (behaves as unknown).
        with pytest.raises(ws_tickets.WsTicketError):
            ws_tickets.consume(expired_token, now=_at(61))

    def test_sweep_returns_zero_when_nothing_expired(self) -> None:
        ws_tickets.issue(USER_A, now=_at(0))  # expires t=60
        assert ws_tickets.sweep_expired(now=_at(59)) == 0


def _make_service() -> AuthService:
    """AuthService with real (test-env) settings and fake repositories."""
    from narrare._app.config import get_settings

    return AuthService(
        repo=FakeAuthRepository(),
        settings=get_settings(),
        providers_repo=FakeUserProvidersRepository(),
    )


class TestAuthServiceIssueWsTicket:
    """AuthService.issue_ws_ticket — thin mint seam (RULE-06)."""

    def test_returns_ticket_response_with_60s_expiry(self) -> None:
        result = _make_service().issue_ws_ticket(USER_A)
        assert isinstance(result, WsTicketResponse)
        assert result.expires_in == 60
        assert len(result.token) >= 32

    def test_issued_token_consumes_to_bound_user(self) -> None:
        result = _make_service().issue_ws_ticket(USER_A)
        assert ws_tickets.consume(result.token) == USER_A

    def test_ttl_constant_matches_documented_policy(self) -> None:
        """PO decision D1:a: 60 s TTL (single SSOT constant)."""
        assert timedelta(seconds=60) == ws_tickets.WS_TICKET_TTL


def _make_ws_ticket_client(*, authenticated: bool) -> TestClient:
    """Minimal app exposing the auth router with dependency overrides.

    ``authenticated=False`` leaves ``get_current_user_id`` unwired so the
    Bearer gate itself is under test (no Authorization header sent).
    """
    from narrare._app.database import get_async_session
    from narrare._app.dependencies_auth import get_current_user_id
    from narrare.auth.router import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")

    if authenticated:

        async def _current_user_id() -> str:
            return str(USER_A)

        app.dependency_overrides[get_current_user_id] = _current_user_id

    async def _fake_session() -> AsyncGenerator[MagicMock]:
        # issue_ws_ticket never touches the DB — the session stays unused
        # (opaque DI value, house pattern: MagicMock(spec=[])).
        yield MagicMock(spec=[])

    app.dependency_overrides[get_async_session] = _fake_session
    return TestClient(app)


class TestWsTicketRoute:
    """POST /auth/ws-ticket — Bearer-gated mint (CurrentUserIdDep)."""

    def test_ws_ticket_without_bearer_returns_401(self) -> None:
        client = _make_ws_ticket_client(authenticated=False)
        resp = client.post("/api/v1/auth/ws-ticket")
        assert resp.status_code == 401

    def test_ws_ticket_returns_token_and_expiry(self) -> None:
        client = _make_ws_ticket_client(authenticated=True)
        resp = client.post("/api/v1/auth/ws-ticket")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data) == {"token", "expires_in"}
        assert data["expires_in"] == 60
        assert len(data["token"]) >= 32

    def test_ws_ticket_token_consumes_to_authenticated_user(self) -> None:
        client = _make_ws_ticket_client(authenticated=True)
        resp = client.post("/api/v1/auth/ws-ticket")
        token = resp.json()["token"]
        assert ws_tickets.consume(token) == USER_A
