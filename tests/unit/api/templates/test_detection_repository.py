"""Unit tests for ``TemplateDetectionRepository.detect_updates``.

Covers the version-mismatch loop: the ``based_on_version is None`` skip,
the ``load_default_template`` missing-bundle skip, the no-change case, and
the positive mismatch that yields an update dict.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from narrare.templates.detection_repository import TemplateDetectionRepository
from tests.fakes.fake_db_session import FakeDbSession, FakeResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession


def _override(entity_type: str, based_on_version: str | None) -> SimpleNamespace:
    return SimpleNamespace(entity_type=entity_type, based_on_version=based_on_version)


def _tpl(version: str) -> SimpleNamespace:
    return SimpleNamespace(meta=SimpleNamespace(template_version=version))


def _load(version: str | None) -> Callable[[str], str | None]:
    """Fake ``load_default_template`` returning *version* (None = missing)."""

    def _loader(_entity_type: str) -> str | None:
        if version is None:
            return None
        return f"---\ntemplate_version: {version}\n---\n"

    return _loader


def _parse(version: str) -> Callable[[str], SimpleNamespace]:
    """Fake ``parse_template`` returning a template carrying *version*."""

    def _parser(_raw: str) -> SimpleNamespace:
        return _tpl(version)

    return _parser


class TestDetectUpdates:
    async def test_returns_empty_when_no_overrides(self) -> None:
        session = FakeDbSession([FakeResult(scalars=[])])
        repo = TemplateDetectionRepository(cast("AsyncSession", session))

        result = await repo.detect_updates("user", uuid4())

        assert result == []

    async def test_skips_override_with_none_based_on_version(self) -> None:
        session = FakeDbSession([FakeResult(scalars=[_override("character", None)])])
        repo = TemplateDetectionRepository(cast("AsyncSession", session))

        result = await repo.detect_updates("user", uuid4())

        assert result == []

    async def test_skips_override_when_bundled_template_missing(self) -> None:
        override = _override("character", "1.0.0")
        session = FakeDbSession([FakeResult(scalars=[override])])
        repo = TemplateDetectionRepository(cast("AsyncSession", session))

        with pytest.MonkeyPatch().context() as m:
            m.setattr("narrare_core.templates.load_default_template", _load(None))
            result = await repo.detect_updates("user", uuid4())

        assert result == []

    async def test_no_update_when_versions_match(self) -> None:
        override = _override("character", "1.0.0")
        session = FakeDbSession([FakeResult(scalars=[override])])
        repo = TemplateDetectionRepository(cast("AsyncSession", session))

        with pytest.MonkeyPatch().context() as m:
            m.setattr("narrare_core.templates.load_default_template", _load("1.0.0"))
            m.setattr("narrare_core.templates.parse_template", _parse("1.0.0"))
            result = await repo.detect_updates("user", uuid4())

        assert result == []

    async def test_appends_update_when_versions_differ(self) -> None:
        override = _override("character", "1.0.0")
        session = FakeDbSession([FakeResult(scalars=[override])])
        repo = TemplateDetectionRepository(cast("AsyncSession", session))

        with pytest.MonkeyPatch().context() as m:
            m.setattr("narrare_core.templates.load_default_template", _load("2.0.0"))
            m.setattr("narrare_core.templates.parse_template", _parse("2.0.0"))
            result = await repo.detect_updates("user", uuid4())

        assert result == [
            {
                "entity_type": "character",
                "override_version": "1.0.0",
                "current_bundled_version": "2.0.0",
            }
        ]
