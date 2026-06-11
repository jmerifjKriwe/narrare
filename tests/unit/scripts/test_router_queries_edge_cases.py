"""Edge-case tests for check_router_queries — RULE-19 SQLAlchemy detection.

Covers: negative cases (no violations), approval markers, file identification.
"""

from __future__ import annotations

import ast

from scripts.architecture._checkers.router_queries import check_router_queries


def _parse(source: str) -> ast.AST:
    return ast.parse(source)


def _lines(source: str) -> list[str]:
    return source.splitlines()


_ROUTER_PATH = "apps/api/narrare/demo/router.py"
_ROUTER_SUB_PATH = "apps/api/narrare/demo/router_items.py"
_NON_ROUTER_PATH = "apps/api/narrare/demo/service.py"


def _check(source: str, rel_path: str = _ROUTER_PATH) -> list[tuple[int, str]]:
    """Run checker and return (line, detail) tuples for non-approved violations."""
    violations = check_router_queries(rel_path, _parse(source), _lines(source))
    return [(v.line, v.detail) for v in violations if not v.approved]


# =====================================================================
# Negative cases — should NOT be flagged
# =====================================================================


class TestNegativeCases:
    """Valid patterns that must NOT produce violations."""

    def test_clean_router_no_violations(self) -> None:
        """A clean router that delegates to service produces no violations."""
        source = """\
from fastapi import APIRouter

from narrare.items.service import ItemService

router = APIRouter()

@router.get("/items")
async def list_items(session, user_id):
    service = ItemService(session)
    return await service.list_items(user_id)
"""
        viols = _check(source)
        assert viols == []

    def test_dependency_factory_not_flagged(self) -> None:
        """_get_service() factory with session.execute is NOT flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

async def _get_service(session, user_id):
    from narrare.items.repository import ItemRepository
    repo = ItemRepository(session)
    result = await session.execute(select(Item))
    return ItemService(repo)

@router.get("/items")
async def list_items(session, user_id):
    service = await _get_service(session, user_id)
    return await service.list_items()
"""
        viols = _check(source)
        assert viols == []

    def test_type_checking_import_not_flagged(self) -> None:
        """select() inside if TYPE_CHECKING: is NOT flagged."""
        source = """\
from typing import TYPE_CHECKING
from fastapi import APIRouter

if TYPE_CHECKING:
    from sqlalchemy import select

router = APIRouter()

@router.get("/items")
async def list_items(session):
    return []
"""
        viols = _check(source)
        assert viols == []

    def test_non_router_file_not_checked(self) -> None:
        """A service file with session.execute is NOT flagged."""
        source = """\
from sqlalchemy import select

class ItemService:
    async def list_items(self, session):
        result = await session.execute(select(Item))
        return result.scalars().all()
"""
        viols = _check(source, rel_path=_NON_ROUTER_PATH)
        assert viols == []

    def test_non_api_path_not_checked(self) -> None:
        """A router file outside apps/api/narrare/ is NOT checked."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def list_items(session):
    result = await session.execute(select(Item))
"""
        viols = _check(source, rel_path="packages/core/router.py")
        assert viols == []

    def test_undecorated_function_not_checked(self) -> None:
        """A plain function (no @router.* decorator) is NOT flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

async def helper(session):
    result = await session.execute(select(Item))
    return result

@router.get("/items")
async def list_items(session):
    return await helper(session)
"""
        viols = _check(source)
        assert viols == []

    def test_router_subname_recognized(self) -> None:
        """router_me.py is recognized as a router file."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/me")
async def get_me(session):
    result = await session.execute(select(User))
"""
        viols = _check(source, rel_path=_ROUTER_SUB_PATH)
        assert len(viols) >= 1

    def test_handler_only_session_in_factory_ok(self) -> None:
        """Handler uses session only to pass to repository — no violations."""
        source = """\
from fastapi import APIRouter

from narrare.auth.repository import AuthRepository

router = APIRouter()

@router.get("/me")
async def get_me(session, user_id):
    repo = AuthRepository(session)
    return await repo.get_by_id(user_id)
"""
        viols = _check(source)
        assert viols == []


# =====================================================================
# Approval markers
# =====================================================================


class TestApprovalMarkers:
    """Inline approval markers suppress violations."""

    def test_narrare_allow_suppresses(self) -> None:
        """# narrare: allow suppresses the violation."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health(conn):
    result = await conn.execute(text("SELECT 1"))  # narrare: allow reason="health check"
"""
        violations = check_router_queries(_ROUTER_PATH, _parse(source), _lines(source))
        approved = [v for v in violations if v.approved]
        non_approved = [v for v in violations if not v.approved]
        assert len(approved) >= 1
        assert len(non_approved) == 0
        assert "health check" in approved[0].approval_reason


# =====================================================================
# File identification
# =====================================================================


class TestRouterFileIdentification:
    """Router files are correctly identified by name and path."""

    def test_router_py_identified(self) -> None:
        """router.py is a valid router file."""
        source = """\
from fastapi import APIRouter
router = APIRouter()

@router.get("/x")
async def x(session):
    await session.execute(text("SELECT 1"))
"""
        viols = _check(source, rel_path="apps/api/narrare/mod/router.py")
        assert len(viols) >= 1

    def test_router_subpath_identified(self) -> None:
        """router_items.py is a valid router file."""
        source = """\
from fastapi import APIRouter
router = APIRouter()

@router.get("/x")
async def x(session):
    await session.execute(text("SELECT 1"))
"""
        viols = _check(source, rel_path="apps/api/narrare/mod/router_items.py")
        assert len(viols) >= 1

    def test_service_py_not_identified(self) -> None:
        """service.py is NOT a router file."""
        source = """\
from fastapi import APIRouter
router = APIRouter()

@router.get("/x")
async def x(session):
    await session.execute(text("SELECT 1"))
"""
        viols = _check(source, rel_path="apps/api/narrare/mod/service.py")
        assert viols == []

    def test_routes_py_not_identified(self) -> None:
        """routes.py (no router prefix) is NOT checked."""
        source = """\
from fastapi import APIRouter
router = APIRouter()

@router.get("/x")
async def x(session):
    await session.execute(text("SELECT 1"))
"""
        viols = _check(source, rel_path="apps/api/narrare/mod/routes.py")
        assert viols == []

    def test_non_narrare_path_not_identified(self) -> None:
        """apps/other/router.py is NOT checked (not narrare/)."""
        source = """\
from fastapi import APIRouter
router = APIRouter()

@router.get("/x")
async def x(session):
    await session.execute(text("SELECT 1"))
"""
        viols = _check(source, rel_path="apps/other/router.py")
        assert viols == []
