"""Tests for RULE-19 router query checker — AST-based SQLAlchemy detection.

Positive cases:  session.execute/scalars/scalar, select/insert/update/delete in handlers.
Negative cases:  dependency factories, TYPE_CHECKING blocks, non-router files,
                 repository files, approved exceptions.
"""

from __future__ import annotations

import ast

from scripts.architecture._checkers.router_queries import check_router_queries


def _parse(source: str) -> ast.AST:
    return ast.parse(source)


def _lines(source: str) -> list[str]:
    return source.splitlines()


# =====================================================================
# Positive cases — should be flagged
# =====================================================================


class TestSessionExecuteInHandler:
    """session.execute() in a route handler is flagged."""

    def test_await_session_execute_flagged(self) -> None:
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def get_items(session):
    result = await session.execute(select(Item))
    return result.all()
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        # Both session.execute() AND select() are flagged
        assert len(violations) == 2
        assert violations[0].rule == "RULE-19"
        assert any("session.execute()" in v.detail for v in violations)
        assert any("select()" in v.detail for v in violations)

    def test_session_scalars_flagged(self) -> None:
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def list_items(session):
    result = await session.scalars(select(Item))
    return list(result)
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        # Both session.scalars() AND select() are flagged
        assert len(violations) == 2
        assert any("session.scalars()" in v.detail for v in violations)
        assert any("select()" in v.detail for v in violations)

    def test_session_scalar_flagged(self) -> None:
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/items/{id}")
async def get_item(session, id):
    result = await session.scalar(select(Item).where(Item.id == id))
    return result
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        # Both session.scalar() AND select() are flagged
        assert len(violations) == 2
        assert any("session.scalar()" in v.detail for v in violations)
        assert any("select()" in v.detail for v in violations)


class TestQueryConstructorsInHandler:
    """select/insert/update/delete() calls in route handlers are flagged."""

    def test_select_in_handler_flagged(self) -> None:
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def get_items(session):
    query = select(Item)  # constructing query in router — forbidden
    return []
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert "select()" in violations[0].detail

    def test_insert_in_handler_flagged(self) -> None:
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.post("/items")
async def create_item(session):
    stmt = insert(Item).values(name="test")
    return {}
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert "insert()" in violations[0].detail

    def test_update_in_handler_flagged(self) -> None:
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.patch("/items/{id}")
async def update_item(session, id):
    stmt = update(Item).where(Item.id == id)
    return {}
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert "update()" in violations[0].detail

    def test_delete_in_handler_flagged(self) -> None:
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.delete("/items/{id}")
async def delete_item(session, id):
    stmt = delete(Item).where(Item.id == id)
    return {}
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert "delete()" in violations[0].detail


class TestMultipleViolations:
    """Multiple violations in one handler are all detected."""

    def test_session_execute_and_select_both_flagged(self) -> None:
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def get_items(session):
    query = select(Item)
    result = await session.execute(query)
    return result.all()
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 2
