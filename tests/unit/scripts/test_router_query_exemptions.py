"""Tests for RULE-19 router query checker — exemption and negative cases.

Negative cases:  dependency factories, TYPE_CHECKING blocks, non-router files,
                 repository files, approved exceptions, edge cases.
"""

from __future__ import annotations

import ast

from scripts.architecture._checkers.router_queries import check_router_queries


def _parse(source: str) -> ast.AST:
    return ast.parse(source)


def _lines(source: str) -> list[str]:
    return source.splitlines()


# =====================================================================
# Negative cases — should NOT be flagged
# =====================================================================


class TestDependencyFactoryExempt:
    """Dependency factory functions (_get_*) are exempt from checks."""

    def test_get_service_with_session_execute_not_flagged(self) -> None:
        """A _get_service function is NOT flagged even if it has session calls."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

def _get_service(session):
    repo = ItemRepository(session)
    return ItemService(repo=repo)

@router.get("/items")
async def get_items(service):
    return await service.list_items()
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


class TestNonRouterFilesExempt:
    """Non-router files are not scanned."""

    def test_service_file_not_scanned(self) -> None:
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def get_items(session):
    result = await session.execute(select(Item))
    return result.all()
"""
        violations = check_router_queries(
            "apps/api/narrare/items/service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_repository_file_not_scanned(self) -> None:
        source = """\
class ItemRepository:
    async def get_all(self, session):
        result = await session.execute(select(Item))
        return result.all()
"""
        violations = check_router_queries(
            "apps/api/narrare/items/repository.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_core_file_not_scanned(self) -> None:
        source = """\
async def query_things(session):
    result = await session.execute(select(Item))
    return result.all()
"""
        violations = check_router_queries(
            "packages/core/narrare_core/something/router.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


class TestRouterPrefixFiles:
    """router_*.py files are correctly identified as routers."""

    def test_router_me_file_scanned(self) -> None:
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/me")
async def get_me(session):
    result = await session.execute(select(User))
    return result.scalar()
"""
        violations = check_router_queries(
            "apps/api/narrare/auth/router_me.py",
            _parse(source),
            _lines(source),
        )
        # session.execute + select + result.scalar = 3 violations
        assert len(violations) == 3

    def test_router_sessions_file_scanned(self) -> None:
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.post("/sessions")
async def create_session(session):
    stmt = insert(Session).values(name="test")
    await session.execute(stmt)
    return {}
"""
        violations = check_router_queries(
            "apps/api/narrare/writing/router_sessions.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 2  # insert + execute


class TestTypeCheckingExempt:
    """Code inside if TYPE_CHECKING: blocks is not flagged."""

    def test_select_in_type_checking_not_flagged(self) -> None:
        source = """\
from __future__ import annotations
from typing import TYPE_CHECKING
from fastapi import APIRouter

if TYPE_CHECKING:
    from sqlalchemy import select

router = APIRouter()

@router.get("/items")
async def get_items(service):
    return await service.list_items()
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


class TestApprovedException:
    """Approved exceptions with # narrare: allow are not violations."""

    def test_approved_session_execute_not_flagged(self) -> None:
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health(conn):
    await conn.execute(text("SELECT 1"))  # narrare: allow reason="Health check"
    return {"status": "ok"}
"""
        violations = check_router_queries(
            "apps/api/narrare/metrics/router.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].approved is True


class TestCorrectRouterPattern:
    """Correctly structured routers produce zero violations."""

    def test_delegating_router_clean(self) -> None:
        """A router that only delegates to services/repos has no violations."""
        source = """\
from fastapi import APIRouter, Depends

from narrare.items.service import ItemService

router = APIRouter()

def _get_service(session):
    repo = ItemRepository(session)
    return ItemService(repo=repo)

@router.get("/items")
async def list_items(service: ItemService = Depends(_get_service)):
    return await service.list_items()

@router.post("/items")
async def create_item(request, service: ItemService = Depends(_get_service)):
    return await service.create(request)
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_real_world_auth_me_pattern_clean(self) -> None:
        """The fixed router_me.py pattern (delegating to repository) is clean."""
        source = """\
from fastapi import APIRouter, HTTPException, status

from narrare.auth.repository import AuthRepository
from narrare.auth.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/me", response_model=UserResponse)
async def get_current_user(user_id, session):
    auth_repo = AuthRepository(session)
    user = await auth_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    return UserResponse.model_validate(user)
"""
        violations = check_router_queries(
            "apps/api/narrare/auth/router_me.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_sync_handler_flagged(self) -> None:
        """Sync route handlers are also checked."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/sync-items")
def get_sync_items(session):
    result = session.execute(select(Item))
    return result.all()
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 2  # execute + select

    def test_conn_execute_flagged(self) -> None:
        """conn.execute() (not session) is also flagged."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/ready")
async def ready():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ready"}
"""
        violations = check_router_queries(
            "apps/api/narrare/metrics/router.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert "conn.execute()" in violations[0].detail

    def test_non_router_decorator_not_flagged(self) -> None:
        """Functions without @router.* decorators are not scanned."""
        source = """\
from fastapi import APIRouter

router = APIRouter()

async def helper_function(session):
    result = await session.execute(select(Item))
    return result.all()

@router.get("/items")
async def get_items(service):
    return await service.list_items()
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_empty_router_no_crash(self) -> None:
        """Empty router file doesn't crash the checker."""
        source = """\
from fastapi import APIRouter

router = APIRouter()
"""
        violations = check_router_queries(
            "apps/api/narrare/items/router.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []
