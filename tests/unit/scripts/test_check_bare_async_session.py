"""Tests for RULE-19: bare AsyncSession in dependency factories."""

from __future__ import annotations

import ast

from scripts.architecture.checkers import check_bare_async_session


def _parse(source: str) -> ast.AST:
    """Parse source code into an AST."""
    return ast.parse(source)


def _lines(source: str) -> list[str]:
    """Split source into lines."""
    return source.splitlines()


# =====================================================================
# Violation detected
# =====================================================================


class TestViolationDetected:
    """Code with bare AsyncSession in dependencies.py IS flagged."""

    def test_single_bare_async_session(self) -> None:
        source = """\
from sqlalchemy.ext.asyncio import AsyncSession

def get_repo(session: AsyncSession) -> Repo:
    return Repo(session)
"""
        violations = check_bare_async_session(
            "apps/api/narrare/kb/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].rule == "RULE-19"
        assert "SessionDep" in violations[0].detail

    def test_multiple_bare_params(self) -> None:
        source = """\
from sqlalchemy.ext.asyncio import AsyncSession

def get_service(db: AsyncSession, conn: AsyncSession) -> Svc:
    return Svc(db, conn)
"""
        violations = check_bare_async_session(
            "apps/api/narrare/_app/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 2

    def test_kwonly_bare_async_session(self) -> None:
        source = """\
from sqlalchemy.ext.asyncio import AsyncSession

def get_repo(*, session: AsyncSession) -> Repo:
    return Repo(session)
"""
        violations = check_bare_async_session(
            "apps/api/narrare/kb/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1

    def test_async_function_def(self) -> None:
        source = """\
from sqlalchemy.ext.asyncio import AsyncSession

async def get_repo(session: AsyncSession) -> Repo:
    return Repo(session)
"""
        violations = check_bare_async_session(
            "apps/api/narrare/kb/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1

    def test_mixed_violation_and_correct(self) -> None:
        source = """\
from sqlalchemy.ext.asyncio import AsyncSession

def get_repo(session: AsyncSession) -> Repo:
    return Repo(session)

def get_service(session: SessionDep) -> Svc:
    return Svc(session)
"""
        violations = check_bare_async_session(
            "apps/api/narrare/kb/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].line == 3  # The `def get_repo(session: AsyncSession)` line


# =====================================================================
# No violation — correct code
# =====================================================================


class TestNoViolation:
    """Code with SessionDep is NOT flagged."""

    def test_session_dep_used(self) -> None:
        source = """\
from narrare._app.dependencies import SessionDep

def get_repo(session: SessionDep) -> Repo:
    return Repo(session)
"""
        violations = check_bare_async_session(
            "apps/api/narrare/kb/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_annotated_form_is_valid(self) -> None:
        """Annotated[AsyncSession, Depends(...)] includes Depends, so it's valid."""
        source = """\
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

def get_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Repo:
    return Repo(session)
"""
        violations = check_bare_async_session(
            "apps/api/narrare/kb/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_no_annotation(self) -> None:
        source = """\
def get_repo(session) -> Repo:
    return Repo(session)
"""
        violations = check_bare_async_session(
            "apps/api/narrare/kb/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


# =====================================================================
# Scope filtering — non-dependencies files and non-apps paths
# =====================================================================


class TestScopeFiltering:
    """Check is only applied to dependencies.py under apps/api/."""

    def test_non_dependencies_file_not_checked(self) -> None:
        source = """\
from sqlalchemy.ext.asyncio import AsyncSession

def get_repo(session: AsyncSession) -> Repo:
    return Repo(session)
"""
        violations = check_bare_async_session(
            "apps/api/narrare/kb/repository.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_non_apps_path_not_checked(self) -> None:
        source = """\
from sqlalchemy.ext.asyncio import AsyncSession

def get_repo(session: AsyncSession) -> Repo:
    return Repo(session)
"""
        violations = check_bare_async_session(
            "packages/core/narrare_core/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_root_dependencies_not_checked(self) -> None:
        source = """\
from sqlalchemy.ext.asyncio import AsyncSession

def get_repo(session: AsyncSession) -> Repo:
    return Repo(session)
"""
        violations = check_bare_async_session(
            "dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


# =====================================================================
# Approved exceptions
# =====================================================================


class TestApprovedExceptions:
    """Approved exceptions are marked accordingly."""

    def test_approval_marker_accepted(self) -> None:
        source = """\
from sqlalchemy.ext.asyncio import AsyncSession

# narrare: allow reason="legacy adapter, migrating in sprint 14"
def get_repo(session: AsyncSession) -> Repo:
    return Repo(session)
"""
        violations = check_bare_async_session(
            "apps/api/narrare/kb/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].approved is True
        assert "legacy adapter" in violations[0].approval_reason
