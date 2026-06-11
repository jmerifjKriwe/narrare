"""Unit tests for check_router_queries — RULE-19 AST-based SQLAlchemy detection.

Covers all three detection patterns:
  Pattern 1: session.execute/scalars/scalar(...)
  Pattern 2: select/insert/update/delete() constructors
  Pattern 3: func.count/func.max/...() SQLAlchemy function calls

Plus multiple-violation scenarios.
"""

from __future__ import annotations

import ast

from scripts.architecture._checkers.router_queries import check_router_queries


def _parse(source: str) -> ast.AST:
    return ast.parse(source)


def _lines(source: str) -> list[str]:
    return source.splitlines()


_ROUTER_PATH = "apps/api/narrare/demo/router.py"


def _check(source: str, rel_path: str = _ROUTER_PATH) -> list[tuple[int, str]]:
    """Run checker and return (line, detail) tuples for non-approved violations."""
    violations = check_router_queries(rel_path, _parse(source), _lines(source))
    return [(v.line, v.detail) for v in violations if not v.approved]


# =====================================================================
# Pattern 1 — session.execute/scalars/scalar(...)
# =====================================================================


class TestSessionQueryMethods:
    """Pattern 1: session.execute/scalars/scalar() in handlers."""

    def test_session_execute_flagged(self) -> None:
        """await session.execute(text(...)) is flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def list_items(session):
    result = await session.execute(text("SELECT 1"))
"""
        viols = _check(source)
        assert len(viols) == 1
        assert viols[0][0] == 7  # line number of session.execute call
        assert "session.execute()" in viols[0][1]

    def test_session_scalars_flagged(self) -> None:
        """await session.scalars(stmt) is flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def list_items(session):
    rows = await session.scalars(some_stmt)
"""
        viols = _check(source)
        assert len(viols) == 1
        assert "session.scalars()" in viols[0][1]

    def test_session_scalar_flagged(self) -> None:
        """await session.scalar(stmt) is flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/count")
async def count_items(session):
    n = await session.scalar(some_stmt)
"""
        viols = _check(source)
        assert len(viols) == 1
        assert "session.scalar()" in viols[0][1]

    def test_sync_session_execute_flagged(self) -> None:
        """session.execute() without await is also flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
def list_items(session):
    result = session.execute(some_stmt)
"""
        viols = _check(source)
        assert len(viols) == 1
        assert "session.execute()" in viols[0][1]

    def test_arbitrary_object_execute_flagged(self) -> None:
        """conn.execute() (any object name) is flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health(conn):
    result = await conn.execute(text("SELECT 1"))
"""
        viols = _check(source)
        assert len(viols) == 1
        assert "conn.execute()" in viols[0][1]


# =====================================================================
# Pattern 2 — select/insert/update/delete() constructors
# =====================================================================


class TestQueryConstructors:
    """Pattern 2: bare select/insert/update/delete() calls in handlers."""

    def test_select_flagged(self) -> None:
        """select(...) call in handler is flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def list_items(session):
    query = select(Item)
    result = await session.execute(query)
"""
        viols = _check(source)
        details = [v[1] for v in viols]
        assert any("select()" in d for d in details)

    def test_insert_flagged(self) -> None:
        """insert(...) call in handler is flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.post("/items")
async def create_item(session):
    stmt = insert(Item).values(name="test")
    await session.execute(stmt)
"""
        viols = _check(source)
        details = [v[1] for v in viols]
        assert any("insert()" in d for d in details)

    def test_update_flagged(self) -> None:
        """update(...) call in handler is flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.patch("/items/{id}")
async def update_item(session, id):
    stmt = update(Item).where(Item.id == id).values(name="new")
    await session.execute(stmt)
"""
        viols = _check(source)
        details = [v[1] for v in viols]
        assert any("update()" in d for d in details)

    def test_delete_flagged(self) -> None:
        """delete(...) call in handler is flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.delete("/items/{id}")
async def delete_item(session, id):
    stmt = delete(Item).where(Item.id == id)
    await session.execute(stmt)
"""
        viols = _check(source)
        details = [v[1] for v in viols]
        assert any("delete()" in d for d in details)


# =====================================================================
# Pattern 3 — func.*() SQLAlchemy function calls
# =====================================================================


class TestSqlalchemyFuncCalls:
    """Pattern 3: func.count/func.max/...() in handlers."""

    def test_func_count_flagged(self) -> None:
        """func.count() in handler is flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/count")
async def count_items(session):
    n = func.count()
"""
        viols = _check(source)
        assert len(viols) == 1
        assert "func.count()" in viols[0][1]

    def test_func_max_flagged(self) -> None:
        """func.max() in handler is flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/max")
async def max_position(session):
    m = func.max(Item.position)
"""
        viols = _check(source)
        assert len(viols) == 1
        assert "func.max()" in viols[0][1]

    def test_func_now_flagged(self) -> None:
        """func.now() in handler is flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/time")
async def get_time(session):
    t = func.now()
"""
        viols = _check(source)
        assert len(viols) == 1
        assert "func.now()" in viols[0][1]


# =====================================================================
# Multiple violations in one handler
# =====================================================================


class TestMultipleViolations:
    """Multiple SQLAlchemy patterns in one handler produce multiple violations."""

    def test_session_execute_plus_select(self) -> None:
        """session.execute(select(...)) produces two violations."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def list_items(session):
    result = await session.execute(select(Item))
"""
        viols = _check(source)
        assert len(viols) == 2
        details = [v[1] for v in viols]
        assert any("session.execute()" in d for d in details)
        assert any("select()" in d for d in details)

    def test_three_violations_in_handler(self) -> None:
        """session.scalar(select(func.count())) produces three violations."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/count")
async def count_items(session):
    n = await session.scalar(select(func.count()))
"""
        viols = _check(source)
        assert len(viols) == 3
        details = [v[1] for v in viols]
        assert any("session.scalar()" in d for d in details)
        assert any("select()" in d for d in details)
        assert any("func.count()" in d for d in details)
