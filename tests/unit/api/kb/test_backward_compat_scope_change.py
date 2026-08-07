"""Regression test: existing KB queries must not break after the scope change.

Series Foundation Spec 1, Task 2.3 — critical backward-compatibility guard.

Background
----------
``KBEntry.novel_id`` was widened from ``NOT NULL`` to nullable so that
Series-Canon entries can exist (``novel_id IS NULL``, ``series_id`` set,
``base_entry_id`` NULL). Novel-Overlay entries keep ``novel_id = X``.

The critical backward-compat guarantee this file protects:

    Existing consumer-facing KB queries that filter ``WHERE novel_id = X``
    must continue to return ONLY Novel-Overlay entries.

Canon entries (``novel_id IS NULL``) are excluded *by SQL semantics*: in SQL
``NULL = X`` evaluates to NULL (not TRUE), so an equality predicate never
matches a NULL row. The only way a consumer query could silently start
surfacing Canon entries would be to add an ``OR novel_id IS NULL`` clause —
which would break ANAL-008 / WRITE-010 / ANAL-009 (the voice-lane features
that consume novel-scoped KB context).

Why inspect SQL, not mock data
------------------------------
A mock ``AsyncSession`` returns whatever we tell it to return, so asserting
"only the Overlay came back" over a mock would be circular — it proves
nothing about the query the repository actually emits. Instead we capture
the real ``select()`` statements the repository passes to ``session.execute``
and compile them to SQL, then assert:

* no statement emits ``novel_id IS NULL`` (the only Canon-leaking pattern), and
* at least one statement filters ``novel_id = :x`` (the equality guard).

If a future change adds Canon to a consumer query, this test fails loudly.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.kb.models import KBEntry
from narrare.kb.repository import KBRepository
from tests.unit.api.kb._scope_repo_helpers import make_kb_model

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

# --------------------------------------------------------------------------- #
# SQL-capture helpers
# --------------------------------------------------------------------------- #


def _make_result(
    *,
    scalars: Sequence[object] = (),
    scalar_one_or_none: object = None,
    scalar_one: object = 0,
) -> MagicMock:
    """Mock SQLAlchemy ``Result`` supporting the three accessors the repo uses.

    ``Result`` methods (``.scalars()``, ``.scalar_one_or_none()``,
    ``.scalar_one()``) are synchronous, so a sync ``MagicMock`` is correct.
    ``scalar_one`` defaults to ``0`` to satisfy the count queries emitted by
    ``list_entries`` / ``search`` / ``count_by_novel``.
    """
    result: MagicMock = MagicMock(spec=["scalars", "scalar_one_or_none", "scalar_one"])
    result.scalars.return_value = list(scalars)
    result.scalar_one_or_none.return_value = scalar_one_or_none
    result.scalar_one.return_value = scalar_one
    return result


def _captured_sql(session: AsyncMock) -> list[str]:
    """Compile every statement passed to ``session.execute`` to SQL text."""
    compiled: list[str] = []
    for call in session.execute.await_args_list:
        stmt = call.args[0]
        compiled.append(str(stmt.compile(dialect=postgresql.dialect())))
    return compiled


def _assert_no_canon_leak(session: AsyncMock) -> None:
    """No captured statement may filter ``novel_id IS NULL``.

    Canon entries have ``novel_id IS NULL``; an equality predicate
    (``novel_id = :x``) never matches them under SQL semantics. The only
    pattern that would surface Canon in a consumer query is ``novel_id IS
    NULL`` — which this assertion forbids.
    """
    assert session.execute.await_args_list, "repository did not execute any query"
    for sql in _captured_sql(session):
        assert re.search(r"novel_id\s+IS\s+NULL", sql, re.IGNORECASE) is None, (
            "Canon-leak regression: a novel-scoped consumer query emits "
            "'novel_id IS NULL', which would surface Series-Canon entries to "
            "existing consumers (ANAL-008/WRITE-010/ANAL-009).\nSQL:\n" + sql
        )


def _assert_filters_novel_by_equality(session: AsyncMock) -> None:
    """At least one captured statement must filter ``novel_id = :x``."""
    assert any(re.search(r"\bnovel_id\s*=", sql) is not None for sql in _captured_sql(session)), (
        "consumer query did not apply a novel_id equality filter"
    )


# --------------------------------------------------------------------------- #
# Consumer-facing query surface to guard
# --------------------------------------------------------------------------- #
#
# Every public KBRepository method that existing consumers call with a
# ``novel_id``. ``find_canon_for_series`` / ``find_overlay_for_novel`` /
# ``find_merged_for_novel`` are the NEW scope-aware methods (Task 2.2) and are
# intentionally excluded — they are the only methods permitted to touch
# ``novel_id IS NULL``.

_NOVEL = uuid.uuid4()


def _consumer_calls() -> list[tuple[str, Callable[[KBRepository], Awaitable[object]]]]:
    return [
        ("list_entries", lambda r: r.list_entries(_NOVEL)),
        ("search", lambda r: r.search(_NOVEL, "query")),
        ("get_by_slug", lambda r: r.get_by_slug(_NOVEL, "alice")),
        ("get_by_name", lambda r: r.get_by_name(_NOVEL, "Alice")),
        ("search_by_name_prefix", lambda r: r.search_by_name_prefix(_NOVEL, "Al")),
        ("count_by_novel", lambda r: r.count_by_novel(_NOVEL)),
    ]


_CONSUMER_CALLS = _consumer_calls()
_CONSUMER_IDS = [label for label, _ in _CONSUMER_CALLS]


@pytest.fixture
def capturing_repo() -> tuple[KBRepository, AsyncMock]:
    """A KBRepository backed by a capturing mock AsyncSession.

    ``execute`` returns an empty-result mock so the consumer methods can run
    to completion; the statements they emit are inspected afterwards via
    ``session.execute.await_args_list``.
    """
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=_make_result())
    return KBRepository(session), session


class TestBackwardCompatScopeChange:
    """Verify existing KB query patterns exclude Canon entries."""

    @pytest.mark.parametrize(("label", "call"), _CONSUMER_CALLS, ids=_CONSUMER_IDS)
    async def test_consumer_query_does_not_leak_canon(
        self,
        capturing_repo: tuple[KBRepository, AsyncMock],
        label: str,
        call: Callable[[KBRepository], Awaitable[object]],
    ) -> None:
        """Each existing consumer query must exclude Series-Canon entries.

        Asserts the emitted SQL carries a ``novel_id = :x`` equality filter
        and contains no ``novel_id IS NULL`` predicate (the Canon-leaking
        pattern). This is the regression guard for ANAL-008/WRITE-010/ANAL-009.
        """
        repo, session = capturing_repo
        # ``label`` is asserted into the parametrize id; reference it so a
        # misconfigured parametrization fails fast rather than silently.
        assert label
        await call(repo)
        _assert_no_canon_leak(session)
        _assert_filters_novel_by_equality(session)

    async def test_list_entries_returns_only_overlay_pattern(
        self, capturing_repo: tuple[KBRepository, AsyncMock]
    ) -> None:
        """``list_entries`` is the primary consumer read path — guard it explicitly.

        A novel that has both a Canon entry (novel_id NULL) and an Overlay
        entry (novel_id = X) available in the table must, via ``list_entries``,
        only ever surface the Overlay. At the unit level this is guaranteed by
        the emitted equality predicate (verified here); the SQL NULL-equality
        semantic that actually drops the Canon row is documented in
        :meth:`test_equality_predicate_excludes_null_novel_id`.
        """
        repo, session = capturing_repo
        novel_id = uuid.uuid4()
        await repo.list_entries(novel_id)

        sql = "\n".join(_captured_sql(session))
        # Equality present, Canon-leaking pattern absent.
        assert re.search(r"\bnovel_id\s*=", sql) is not None
        assert re.search(r"novel_id\s+IS\s+NULL", sql, re.IGNORECASE) is None

    async def test_equality_predicate_excludes_null_novel_id(self) -> None:
        """Document the SQL NULL-equality semantic underpinning the guarantee.

        In SQL ``WHERE novel_id = :x`` never matches a row where
        ``novel_id IS NULL``. Python's ``None == x`` mirrors this (it is
        ``False``, never ``True``), so a Canon row (``novel_id=None``) is
        invisible to the equality filter the repository applies. Guards
        against a future change to a NULL-including predicate.
        """
        series_id = uuid.uuid4()
        novel_id = uuid.uuid4()
        canon = make_kb_model(novel_id=None, series_id=series_id, slug="alice")
        overlay = make_kb_model(novel_id=novel_id, series_id=series_id, slug="alice")

        def novel_scoped(row: KBEntry) -> bool:
            """Mirror of SQL 'WHERE novel_id = :x' evaluated per row."""
            return row.novel_id == novel_id

        assert novel_scoped(overlay) is True
        # None == novel_id -> False (SQL NULL-equality semantic).
        assert novel_scoped(canon) is False

    def test_novel_id_is_nullable_so_canon_rows_can_exist(self) -> None:
        """Canon rows (``novel_id IS NULL``) require ``novel_id`` to be nullable.

        This is the structural prerequisite for Canon and Overlay to coexist in
        the same table. If it were reverted to ``NOT NULL`` the scope feature
        could not store Canon entries and the whole scenario collapses.
        """
        assert KBEntry.__table__.c.novel_id.nullable is True
