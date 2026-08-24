"""Unit tests for the chat DI wiring — novel ownership lookup (P-SEC).

Mirrors ``tests/unit/api/notes/test_dependencies.py``: covers the
module-private ``OwnedLinkLookupProtocol`` adapter and pins the invariant
that ``get_chat_service`` ALWAYS wires ``novel_lookup`` (never ``None``) —
``ChatService`` fails open on a missing lookup (test-context convenience),
so a forgotten lookup in production wiring would silently skip project
ownership validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from tests.fakes.fake_db_session import FakeDbSession

from narrare.chat.chat_service import ChatService
from narrare.chat.dependencies import (
    _NovelOwnedLookup,  # pyright: ignore[reportPrivateUsage] — wiring is the unit under test
    get_chat_service,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.novels.repository import NovelRepository


class _StubNovelRepo:
    """Structurally matches ``NovelRepository.get_by_id`` (ownership-filtered)."""

    def __init__(self, row: object | None) -> None:
        self.row = row
        self.calls: list[tuple[UUID, UUID]] = []

    async def get_by_id(self, novel_id: UUID, user_id: UUID) -> object | None:
        self.calls.append((novel_id, user_id))
        return self.row


class TestNovelOwnedLookup:
    async def test_delegates_to_repository_with_user_scope(self) -> None:
        """The novel adapter is pure delegation — get_by_id already filters by user."""
        novel = object()
        stub = _StubNovelRepo(novel)
        lookup = _NovelOwnedLookup(cast("NovelRepository", stub))
        novel_id, user_id = uuid4(), uuid4()

        assert await lookup.get_owned(novel_id, user_id) is novel
        assert stub.calls == [(novel_id, user_id)]

    async def test_returns_none_when_repository_finds_nothing(self) -> None:
        stub = _StubNovelRepo(None)
        lookup = _NovelOwnedLookup(cast("NovelRepository", stub))

        assert await lookup.get_owned(uuid4(), uuid4()) is None


class TestGetChatService:
    def test_always_wires_novel_lookup(self) -> None:
        """P-SEC invariant: the novel lookup is always wired — never ``None``.

        ``ChatService`` fails open on a missing lookup (test contexts only),
        so unwired production wiring would silently skip project ownership
        validation. This is the regression pin (notes T7-review pattern).
        """
        service = get_chat_service(cast("AsyncSession", FakeDbSession()))

        assert isinstance(service, ChatService)
        assert isinstance(
            service._novel_lookup,  # pyright: ignore[reportPrivateUsage] — see docstring
            _NovelOwnedLookup,
        )
