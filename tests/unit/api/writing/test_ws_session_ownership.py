"""Regression tests — IDOR S3 ownership gate on the writing WS handshake.

Matrix (plan ``docs/superpowers/plans/2026-08-26-idor-remediation.md``, S3
follow-up item 4): the ticket-derived identity must own the addressed
project AND the chapter must belong to it BEFORE any token-limit or
model-routing read —

* foreign/unknown project → handshake closed 4001, byte-identical
  (anti-enumeration: same sent id ⇒ same client-visible bytes);
* chapter outside the addressed project (own or foreign) / unknown
  chapter → 4001, byte-identical;
* gate ordering: a rejected ``project_id`` never reaches
  ``TokenLimitsService`` / model routing — no auto-created settings row,
  no FK ``IntegrityError`` 500-oracle;
* zero persistence on rejection: no handler is built or run ⇒ zero
  writing-session rows, zero mem0 writes;
* owner + own chapter still connect (happy-path control).

The reattach-precondition ordering (typed ``recovery_failed`` BEFORE the
gate for reconnects, ADR-052) lives in
``test_ws_reattach_admission.py``; the shared ownership-seeded handshake
harness lives in ``ws_test_helpers.py``.

Conventions follow ``test_router_sessions_auth.py`` (ticket mint,
close-code assertions); the repository class mocks follow the
established factory-gate patch points
(``test_deps_factory_ownership_gate.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare.auth import ws_tickets
from tests.unit.api.writing.ws_test_helpers import (
    FOREIGN_OWNER,
    TICKET_USER,
    HandshakeRun,
    run_handshake,
)

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

OWNERSHIP_CLOSE_CODE = 4001


@pytest.fixture(autouse=True)
def _clean_ticket_registry() -> None:
    """Isolate the process-global ticket registry per test."""
    ws_tickets._TICKETS.clear()


def _assert_rejected_4001(ws: AsyncMock) -> None:
    """Assert the house reject convention: accept → error frame → close 4001."""
    ws.accept.assert_awaited_once()
    ws.send_json.assert_awaited_once()
    assert ws.close.await_count == 1, "handshake must close the socket on rejection"
    close_kwargs = ws.close.await_args.kwargs
    assert close_kwargs["code"] == OWNERSHIP_CLOSE_CODE


def _client_visible_bytes(run: HandshakeRun) -> tuple[object, object, object]:
    """Everything the client sees on rejection: frame + close code/reason."""
    assert run.websocket.close.await_count == 1, "handshake must close on rejection"
    return (
        run.websocket.send_json.await_args.args[0],
        run.websocket.close.await_args.kwargs.get("code"),
        run.websocket.close.await_args.kwargs.get("reason"),
    )


class TestProjectOwnershipGate:
    """The client-supplied ``project_id`` must be owned by the caller."""

    async def test_handshake_with_foreign_project_closes_4001(self) -> None:
        project = uuid4()  # row exists — but FOREIGN_OWNER owns it
        run = await run_handshake(
            uuid4(), project, novel_owners={project: FOREIGN_OWNER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)

    async def test_handshake_with_unknown_project_closes_4001(self) -> None:
        project = uuid4()  # no row at all
        run = await run_handshake(uuid4(), project, novel_owners={}, chapter_novels={})
        _assert_rejected_4001(run.websocket)

    async def test_foreign_and_unknown_project_are_byte_identical(self) -> None:
        """Anti-enumeration: same sent id ⇒ same client-visible bytes,
        whether the project exists under another owner or not at all."""
        project, chapter = uuid4(), uuid4()
        foreign = await run_handshake(
            chapter, project, novel_owners={project: FOREIGN_OWNER}, chapter_novels={}
        )
        unknown = await run_handshake(chapter, project, novel_owners={}, chapter_novels={})
        assert _client_visible_bytes(foreign) == _client_visible_bytes(unknown)


class TestChapterAccessGate:
    """The chapter must exist and belong to the addressed project."""

    async def test_handshake_with_chapter_outside_project_closes_4001(self) -> None:
        """Chapter of the caller's OTHER novel is still ∉ the project."""
        project, other_novel, chapter = uuid4(), uuid4(), uuid4()
        run = await run_handshake(
            chapter,
            project,
            novel_owners={project: TICKET_USER, other_novel: TICKET_USER},
            chapter_novels={chapter: other_novel},
        )
        _assert_rejected_4001(run.websocket)

    async def test_handshake_with_foreign_chapter_closes_4001(self) -> None:
        """Chapter of another user's novel — even naming that novel as
        the project (foreign project) must not open a session."""
        foreign_novel, chapter = uuid4(), uuid4()
        run = await run_handshake(
            chapter,
            foreign_novel,
            novel_owners={foreign_novel: FOREIGN_OWNER},
            chapter_novels={chapter: foreign_novel},
        )
        _assert_rejected_4001(run.websocket)

    async def test_handshake_with_unknown_chapter_closes_4001(self) -> None:
        project = uuid4()
        run = await run_handshake(
            uuid4(), project, novel_owners={project: TICKET_USER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)

    async def test_foreign_and_unknown_chapter_are_byte_identical(self) -> None:
        """Same sent chapter+project ids: a chapter bound to some other
        novel vs. no chapter row are indistinguishable."""
        project, chapter = uuid4(), uuid4()
        foreign = await run_handshake(
            chapter,
            project,
            novel_owners={project: TICKET_USER},
            chapter_novels={chapter: uuid4()},  # exists — belongs elsewhere
        )
        unknown = await run_handshake(
            chapter, project, novel_owners={project: TICKET_USER}, chapter_novels={}
        )
        assert _client_visible_bytes(foreign) == _client_visible_bytes(unknown)


class TestGateOrdering:
    """Rejection happens BEFORE token-limit / model-routing resolution."""

    async def test_unknown_project_never_reaches_token_limit_resolution(
        self,
    ) -> None:
        run = await run_handshake(uuid4(), uuid4(), novel_owners={}, chapter_novels={})
        _assert_rejected_4001(run.websocket)
        # Not even constructed ⇒ the auto-creating project repos never ran
        # (no ProjectSettings/ProjectTokenLimits row, no FK oracle).
        run.token_limits_cls.assert_not_called()
        run.token_limits_cls.return_value.get_resolved_limits.assert_not_awaited()
        run.resolver.resolve.assert_not_awaited()

    async def test_foreign_project_never_reaches_model_routing(self) -> None:
        project = uuid4()
        run = await run_handshake(
            uuid4(), project, novel_owners={project: FOREIGN_OWNER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)
        run.token_limits_cls.return_value.get_resolved_limits.assert_not_awaited()
        run.resolver.resolve.assert_not_awaited()

    async def test_unknown_chapter_never_reaches_token_limit_resolution(
        self,
    ) -> None:
        project = uuid4()
        run = await run_handshake(
            uuid4(), project, novel_owners={project: TICKET_USER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)
        run.token_limits_cls.return_value.get_resolved_limits.assert_not_awaited()
        run.resolver.resolve.assert_not_awaited()

    async def test_rejection_still_releases_the_db_session(self) -> None:
        """The close path must not leak the handshake's DB session."""
        project = uuid4()
        run = await run_handshake(
            uuid4(), project, novel_owners={project: FOREIGN_OWNER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)
        run.db_gen.aclose.assert_awaited_once()


class TestZeroPersistenceOnRejection:
    """No handler built or run ⇒ zero writing-session rows, zero mem0."""

    async def test_foreign_project_builds_no_handler(self) -> None:
        project = uuid4()
        run = await run_handshake(
            uuid4(), project, novel_owners={project: FOREIGN_OWNER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)
        run.build.assert_not_called()
        run.handler.handle.assert_not_awaited()

    async def test_unknown_chapter_handles_no_session(self) -> None:
        project = uuid4()
        run = await run_handshake(
            uuid4(), project, novel_owners={project: TICKET_USER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)
        run.handler.handle.assert_not_awaited()


class TestOwnerStillConnects:
    """Happy-path control: owner + own chapter passes the gate."""

    async def test_own_project_and_chapter_connect_with_derived_identity(
        self,
    ) -> None:
        project, chapter = uuid4(), uuid4()
        run = await run_handshake(
            chapter,
            project,
            novel_owners={project: TICKET_USER},
            chapter_novels={chapter: project},
        )
        run.build.assert_called_once()
        run.handler.handle.assert_awaited_once_with(
            run.websocket, chapter, str(TICKET_USER), project, session_id=None
        )
        # Post-gate resolution did run (and only once).
        run.resolver.resolve.assert_awaited_once()
        run.token_limits_cls.return_value.get_resolved_limits.assert_awaited_once()
        run.db_gen.aclose.assert_awaited_once()
        run.websocket.send_json.assert_not_called()
        run.websocket.close.assert_not_called()
