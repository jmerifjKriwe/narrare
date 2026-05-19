"""Unit tests for TemplateRepository — mocked AsyncSession.

These tests verify repository logic without touching a real database.
The AsyncSession is mocked so we control exactly what each query returns.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.templates.models import KBTemplate, TemplateScope
from narrare.templates.repository import TemplateRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with a chainable execute()."""
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock(spec=["scalar_one_or_none", "scalars", "all"])
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value = MagicMock(
        spec=["all"],
        all=MagicMock(spec=["__call__"], return_value=[]),
    )
    session.execute.return_value = mock_result
    session.flush = AsyncMock()
    session.add = MagicMock(spec=["__call__"])
    session.refresh = AsyncMock()
    return session


def _make_kb_template(
    entity_type: str = "character",
    scope: str = "user",
    scope_id: uuid.UUID | None = None,
    content: str = "---\ntemplate_type: character\n---\n# Body",
    based_on_version: str | None = "1.0.0",
) -> KBTemplate:
    """Create a KBTemplate instance for testing."""
    return KBTemplate(
        id=uuid.uuid4(),
        entity_type=entity_type,
        scope=TemplateScope(scope),
        scope_id=scope_id,
        content=content,
        based_on_version=based_on_version,
        schema_version="2.0.0",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> AsyncMock:
    return _make_mock_session()


@pytest.fixture
def repo(mock_session: AsyncMock) -> TemplateRepository:
    return TemplateRepository(session=mock_session)


# ---------------------------------------------------------------------------
# get_override
# ---------------------------------------------------------------------------


class TestGetOverride:
    async def test_get_override_returns_none_when_not_found(
        self, repo: TemplateRepository, mock_session: AsyncMock
    ) -> None:
        """get_override returns None when no row matches."""
        result = await repo.get_override("character", "user", uuid.uuid4())
        assert result is None

    async def test_get_override_returns_template_when_found(
        self, repo: TemplateRepository, mock_session: AsyncMock
    ) -> None:
        """get_override returns parsed Template when row exists."""
        kb_tpl = _make_kb_template()
        mock_session.execute.return_value.scalar_one_or_none.return_value = kb_tpl

        result = await repo.get_override("character", "user", uuid.uuid4())
        assert result is not None
        assert result.meta.template_type == "character"


# ---------------------------------------------------------------------------
# list_overrides
# ---------------------------------------------------------------------------


class TestListOverrides:
    async def test_list_overrides_returns_empty_when_none(
        self, repo: TemplateRepository, mock_session: AsyncMock
    ) -> None:
        """list_overrides returns empty list when no overrides exist."""
        result = await repo.list_overrides("user", uuid.uuid4())
        assert result == []

    async def test_list_overrides_returns_templates(
        self, repo: TemplateRepository, mock_session: AsyncMock
    ) -> None:
        """list_overrides returns parsed templates for all overrides."""
        tpl1 = _make_kb_template(
            entity_type="character",
            content="---\ntemplate_type: character\ntemplate_version: 1.0.0\n---\n# Char body",
        )
        tpl2 = _make_kb_template(
            entity_type="location",
            content="---\ntemplate_type: location\ntemplate_version: 1.0.0\n---\n# Loc body",
        )
        mock_session.execute.return_value.scalars.return_value.all.return_value = [tpl1, tpl2]

        result = await repo.list_overrides("user", uuid.uuid4())
        assert len(result) == 2
        assert result[0].meta.template_type == "character"
        assert result[1].meta.template_type == "location"


# ---------------------------------------------------------------------------
# save_override
# ---------------------------------------------------------------------------


class TestSaveOverride:
    async def test_save_override_inserts_new_row(
        self, repo: TemplateRepository, mock_session: AsyncMock
    ) -> None:
        """save_override inserts a new row when no existing override."""
        scope_id = uuid.uuid4()

        async def fake_flush_and_refresh(entity: Any) -> None:
            entity.id = uuid.uuid4()

        repo._flush_and_refresh = AsyncMock(side_effect=fake_flush_and_refresh)

        result = await repo.save_override(
            entity_type="character",
            scope="user",
            scope_id=scope_id,
            content="---\ntemplate_type: character\n---\n# New body",
            based_on_version="1.0.0",
        )

        assert result is not None
        assert result.meta.template_type == "character"
        mock_session.add.assert_called_once()

    async def test_save_override_updates_existing_row(
        self, repo: TemplateRepository, mock_session: AsyncMock
    ) -> None:
        """save_override updates existing row when one already exists."""
        existing = _make_kb_template()
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing

        async def fake_flush_and_refresh(entity: Any) -> None:
            pass

        repo._flush_and_refresh = AsyncMock(side_effect=fake_flush_and_refresh)

        result = await repo.save_override(
            entity_type="character",
            scope="user",
            scope_id=uuid.uuid4(),
            content="---\ntemplate_type: character\n---\n# Updated body",
            based_on_version="1.1.0",
        )

        assert result is not None
        assert existing.content == "---\ntemplate_type: character\n---\n# Updated body"
        assert existing.based_on_version == "1.1.0"


# ---------------------------------------------------------------------------
# delete_override
# ---------------------------------------------------------------------------


class TestDeleteOverride:
    async def test_delete_override_returns_false_when_none(
        self, repo: TemplateRepository, mock_session: AsyncMock
    ) -> None:
        """delete_override returns False when no row matches."""
        MockCursorResult = MagicMock(spec=["rowcount"], rowcount=0)
        mock_session.execute.return_value = MockCursorResult

        result = await repo.delete_override("character", "user", uuid.uuid4())
        assert result is False

    async def test_delete_override_returns_true_when_deleted(
        self, repo: TemplateRepository, mock_session: AsyncMock
    ) -> None:
        """delete_override returns True when a row is deleted."""
        MockCursorResult = MagicMock(spec=["rowcount"], rowcount=1)
        mock_session.execute.return_value = MockCursorResult

        result = await repo.delete_override("character", "user", uuid.uuid4())
        assert result is True


# ---------------------------------------------------------------------------
# detect_updates (via TemplateDetectionRepository)
# ---------------------------------------------------------------------------


class TestDetectUpdates:
    async def test_detect_updates_returns_empty_when_no_overrides(
        self, repo: TemplateRepository, mock_session: AsyncMock
    ) -> None:
        """detect_updates returns empty list when no overrides exist."""
        from narrare.templates.detection_repository import TemplateDetectionRepository

        detection_repo = TemplateDetectionRepository(session=mock_session)
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        result = await detection_repo.detect_updates("user", uuid.uuid4())
        assert result == []
