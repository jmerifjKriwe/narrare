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

Conventions follow ``test_router_sessions_auth.py`` (ticket mint,
close-code assertions); the repository class mocks follow the
established factory-gate patch points
(``test_deps_factory_ownership_gate.py``).
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from narrare._app.config import Settings as AppSettings
from narrare.auth import ws_tickets
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.writing.router_sessions import interactive_session

if TYPE_CHECKING:
    from collections.abc import Iterator

# Ticket-bound caller vs. the foreign resource owner.
USER = UUID("00000000-0000-0000-0000-0000000000aa")
OTHER = UUID("00000000-0000-0000-0000-0000000000bb")

OWNERSHIP_CLOSE_CODE = 4001


@pytest.fixture(autouse=True)
def _clean_ticket_registry() -> None:
    """Isolate the process-global ticket registry per test."""
    ws_tickets._TICKETS.clear()


def _novel_repo(novel_owners: dict[UUID, UUID]) -> MagicMock:
    """Class mock honoring ``NovelRepository``'s user-scoped contract.

    ``get_by_id(novel_id, user_id)`` returns a row only for its owner:
    foreign (row exists, other owner) and unknown (no row) both yield
    ``None`` — the seam where the two scenarios actually differ.
    """
    cls = MagicMock(spec=NovelRepository, name="NovelRepository")

    async def get_by_id(novel_id: UUID, user_id: UUID) -> object:
        if novel_owners.get(novel_id) == user_id:
            return SimpleNamespace(id=novel_id)
        return None

    cls.return_value.get_by_id = AsyncMock(side_effect=get_by_id)
    return cls


def _chapter_repo(chapter_novels: dict[UUID, UUID]) -> MagicMock:
    """Class mock honoring ``ChapterRepository.get``'s existence contract.

    ``chapter_novels`` maps chapter_id → the novel it belongs to; a
    missing entry is an unknown chapter.
    """
    cls = MagicMock(spec=ChapterRepository, name="ChapterRepository")

    async def get(chapter_id: UUID) -> object:
        novel_id = chapter_novels.get(chapter_id)
        if novel_id is None:
            return None
        return SimpleNamespace(id=chapter_id, novel_id=novel_id)

    cls.return_value.get = AsyncMock(side_effect=get)
    return cls


@dataclass(slots=True)
class _Run:
    """One handshake run: the socket plus the seams assertions inspect."""

    websocket: AsyncMock
    build: MagicMock
    handler: AsyncMock
    token_limits_cls: MagicMock
    resolver: MagicMock
    db_gen: AsyncMock


@contextmanager
def _handshake_env(
    novel_owners: dict[UUID, UUID],
    chapter_novels: dict[UUID, UUID],
) -> Iterator[tuple[MagicMock, AsyncMock, MagicMock, MagicMock, AsyncMock]]:
    """Patch the full handshake stack over ownership-seeded repositories.

    Mirrors ``test_router_sessions_auth._success_path_env`` so runs reach
    the DB block; yields ``(build, handler, token_limits_cls, resolver,
    db_gen)``.
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
        patch("narrare.writing.deps_ws.get_session_control_service"),
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
        patch("narrare.novels.repository.NovelRepository", _novel_repo(novel_owners)),
        patch("narrare.chapters.repository.ChapterRepository", _chapter_repo(chapter_novels)),
    ):
        mock_build.return_value = mock_handler
        mock_settings = MagicMock(spec=AppSettings)
        mock_settings.csrf_trusted_origins = ["http://localhost:3000"]
        mock_get_settings.return_value = mock_settings
        yield mock_build, mock_handler, mock_token_cls, mock_resolver, mock_db_gen


async def _run_handshake(
    chapter_id: UUID,
    project_id: UUID,
    *,
    novel_owners: dict[UUID, UUID],
    chapter_novels: dict[UUID, UUID],
) -> _Run:
    """Run one handshake against ownership-seeded stores (fresh ticket)."""
    ws = AsyncMock()
    ws.app = MagicMock(spec=["state"])
    ws.headers = {"origin": "http://localhost:3000"}
    token = ws_tickets.issue(USER)
    with _handshake_env(novel_owners, chapter_novels) as (
        build,
        handler,
        token_limits_cls,
        resolver,
        db_gen,
    ):
        await interactive_session(ws, chapter_id, token=token, project_id=project_id)
    return _Run(
        websocket=ws,
        build=build,
        handler=handler,
        token_limits_cls=token_limits_cls,
        resolver=resolver,
        db_gen=db_gen,
    )


def _assert_rejected_4001(ws: AsyncMock) -> None:
    """Assert the house reject convention: accept → error frame → close 4001."""
    ws.accept.assert_awaited_once()
    ws.send_json.assert_awaited_once()
    assert ws.close.await_count == 1, "handshake must close the socket on rejection"
    close_kwargs = ws.close.await_args.kwargs
    assert close_kwargs["code"] == OWNERSHIP_CLOSE_CODE


def _client_visible_bytes(run: _Run) -> tuple[object, object, object]:
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
        project = uuid4()  # row exists — but OTHER owns it
        run = await _run_handshake(
            uuid4(), project, novel_owners={project: OTHER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)

    async def test_handshake_with_unknown_project_closes_4001(self) -> None:
        project = uuid4()  # no row at all
        run = await _run_handshake(uuid4(), project, novel_owners={}, chapter_novels={})
        _assert_rejected_4001(run.websocket)

    async def test_foreign_and_unknown_project_are_byte_identical(self) -> None:
        """Anti-enumeration: same sent id ⇒ same client-visible bytes,
        whether the project exists under another owner or not at all."""
        project, chapter = uuid4(), uuid4()
        foreign = await _run_handshake(
            chapter, project, novel_owners={project: OTHER}, chapter_novels={}
        )
        unknown = await _run_handshake(chapter, project, novel_owners={}, chapter_novels={})
        assert _client_visible_bytes(foreign) == _client_visible_bytes(unknown)


class TestChapterAccessGate:
    """The chapter must exist and belong to the addressed project."""

    async def test_handshake_with_chapter_outside_project_closes_4001(self) -> None:
        """Chapter of the caller's OTHER novel is still ∉ the project."""
        project, other_novel, chapter = uuid4(), uuid4(), uuid4()
        run = await _run_handshake(
            chapter,
            project,
            novel_owners={project: USER, other_novel: USER},
            chapter_novels={chapter: other_novel},
        )
        _assert_rejected_4001(run.websocket)

    async def test_handshake_with_foreign_chapter_closes_4001(self) -> None:
        """Chapter of another user's novel — even naming that novel as
        the project (foreign project) must not open a session."""
        foreign_novel, chapter = uuid4(), uuid4()
        run = await _run_handshake(
            chapter,
            foreign_novel,
            novel_owners={foreign_novel: OTHER},
            chapter_novels={chapter: foreign_novel},
        )
        _assert_rejected_4001(run.websocket)

    async def test_handshake_with_unknown_chapter_closes_4001(self) -> None:
        project = uuid4()
        run = await _run_handshake(
            uuid4(), project, novel_owners={project: USER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)

    async def test_foreign_and_unknown_chapter_are_byte_identical(self) -> None:
        """Same sent chapter+project ids: a chapter bound to some other
        novel vs. no chapter row are indistinguishable."""
        project, chapter = uuid4(), uuid4()
        foreign = await _run_handshake(
            chapter,
            project,
            novel_owners={project: USER},
            chapter_novels={chapter: uuid4()},  # exists — belongs elsewhere
        )
        unknown = await _run_handshake(
            chapter, project, novel_owners={project: USER}, chapter_novels={}
        )
        assert _client_visible_bytes(foreign) == _client_visible_bytes(unknown)


class TestGateOrdering:
    """Rejection happens BEFORE token-limit / model-routing resolution."""

    async def test_unknown_project_never_reaches_token_limit_resolution(
        self,
    ) -> None:
        run = await _run_handshake(uuid4(), uuid4(), novel_owners={}, chapter_novels={})
        _assert_rejected_4001(run.websocket)
        # Not even constructed ⇒ the auto-creating project repos never ran
        # (no ProjectSettings/ProjectTokenLimits row, no FK oracle).
        run.token_limits_cls.assert_not_called()
        run.token_limits_cls.return_value.get_resolved_limits.assert_not_awaited()
        run.resolver.resolve.assert_not_awaited()

    async def test_foreign_project_never_reaches_model_routing(self) -> None:
        project = uuid4()
        run = await _run_handshake(
            uuid4(), project, novel_owners={project: OTHER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)
        run.token_limits_cls.return_value.get_resolved_limits.assert_not_awaited()
        run.resolver.resolve.assert_not_awaited()

    async def test_unknown_chapter_never_reaches_token_limit_resolution(
        self,
    ) -> None:
        project = uuid4()
        run = await _run_handshake(
            uuid4(), project, novel_owners={project: USER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)
        run.token_limits_cls.return_value.get_resolved_limits.assert_not_awaited()
        run.resolver.resolve.assert_not_awaited()

    async def test_rejection_still_releases_the_db_session(self) -> None:
        """The close path must not leak the handshake's DB session."""
        project = uuid4()
        run = await _run_handshake(
            uuid4(), project, novel_owners={project: OTHER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)
        run.db_gen.aclose.assert_awaited_once()


class TestZeroPersistenceOnRejection:
    """No handler built or run ⇒ zero writing-session rows, zero mem0."""

    async def test_foreign_project_builds_no_handler(self) -> None:
        project = uuid4()
        run = await _run_handshake(
            uuid4(), project, novel_owners={project: OTHER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)
        run.build.assert_not_called()
        run.handler.handle.assert_not_awaited()

    async def test_unknown_chapter_handles_no_session(self) -> None:
        project = uuid4()
        run = await _run_handshake(
            uuid4(), project, novel_owners={project: USER}, chapter_novels={}
        )
        _assert_rejected_4001(run.websocket)
        run.handler.handle.assert_not_awaited()


class TestOwnerStillConnects:
    """Happy-path control: owner + own chapter passes the gate."""

    async def test_own_project_and_chapter_connect_with_derived_identity(
        self,
    ) -> None:
        project, chapter = uuid4(), uuid4()
        run = await _run_handshake(
            chapter,
            project,
            novel_owners={project: USER},
            chapter_novels={chapter: project},
        )
        run.build.assert_called_once()
        run.handler.handle.assert_awaited_once_with(
            run.websocket, chapter, str(USER), project, session_id=None
        )
        # Post-gate resolution did run (and only once).
        run.resolver.resolve.assert_awaited_once()
        run.token_limits_cls.return_value.get_resolved_limits.assert_awaited_once()
        run.db_gen.aclose.assert_awaited_once()
        run.websocket.send_json.assert_not_called()
        run.websocket.close.assert_not_called()
