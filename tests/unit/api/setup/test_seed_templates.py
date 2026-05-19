"""Unit tests for seed_templates service.

Tests cover:
- Inserting new global templates when none exist
- Updating existing global templates when bundled version is newer
- Skipping existing global templates when versions match
- Skipping existing global templates when stored version is newer
- Skipping when bundled template is missing
- Returning correct count of inserts + updates
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.setup.seed_templates import seed_templates
from narrare.templates.models import KBTemplate, TemplateScope
from narrare_core.templates.models import Template, TemplateMeta


def _make_template(version: str, schema_version: str = "1.0.0") -> Template:
    """Create a minimal Template with the given version."""
    return Template(
        meta=TemplateMeta(
            template_type="character",
            template_version=version,
            schema_version=schema_version,
        ),
    )


def _make_existing(
    entity_type: str = "character",
    based_on_version: str | None = "1.0.0",
) -> MagicMock:
    """Create an existing KBTemplate row mock.

    Uses MagicMock(spec=KBTemplate) because SQLAlchemy mapped attributes
    require instance instrumentation that bypasses ``__new__``.
    """
    tmpl = MagicMock(spec=KBTemplate)
    tmpl.entity_type = entity_type
    tmpl.scope = TemplateScope.GLOBAL
    tmpl.scope_id = None
    tmpl.based_on_version = based_on_version
    tmpl.content = "old content"
    tmpl.schema_version = "1.0.0"
    return tmpl


def _make_execute_result(value: object | None = None) -> MagicMock:
    """Create a mock SQLAlchemy Result with configured scalar_one_or_none."""
    result = MagicMock(spec=Result)
    result.scalar_one_or_none.return_value = value
    return result


@pytest.fixture
def mock_session() -> AsyncMock:
    """AsyncSession mock with execute returning configurable results."""
    return AsyncMock(spec=AsyncSession)


# ---------------------------------------------------------------------------
# Insert new templates
# ---------------------------------------------------------------------------


class TestSeedInsertNew:
    """When no global entry exists, a new one is inserted."""

    @patch("narrare.setup.seed_templates.parse_template")
    @patch("narrare.setup.seed_templates.load_default_template")
    @patch("narrare.setup.seed_templates.list_default_templates")
    async def test_inserts_when_no_existing(
        self,
        mock_list: MagicMock,
        mock_load: MagicMock,
        mock_parse: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """No existing global entry → insert and return 1."""
        mock_list.return_value = ["character"]
        mock_load.return_value = "---\ntemplate_type: character\n---\nBody"
        mock_parse.return_value = _make_template("2.0.0")

        # execute returns a result whose scalar_one_or_none() is None
        mock_session.execute.return_value = _make_execute_result(None)

        count = await seed_templates(mock_session)

        assert count == 1
        mock_session.add.assert_called_once()
        added: KBTemplate = mock_session.add.call_args[0][0]
        assert added.entity_type == "character"
        assert added.scope == TemplateScope.GLOBAL
        assert added.based_on_version == "2.0.0"


# ---------------------------------------------------------------------------
# Update existing templates
# ---------------------------------------------------------------------------


class TestSeedUpdateExisting:
    """When a global entry exists with an older version, update it."""

    @patch("narrare.setup.seed_templates.parse_template")
    @patch("narrare.setup.seed_templates.load_default_template")
    @patch("narrare.setup.seed_templates.list_default_templates")
    async def test_updates_when_bundled_newer(
        self,
        mock_list: MagicMock,
        mock_load: MagicMock,
        mock_parse: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """Existing v1.0.0, bundled v2.1.0 → update content and version."""
        mock_list.return_value = ["character"]
        mock_load.return_value = "---\ntemplate_type: character\n---\nNew body"
        mock_parse.return_value = _make_template("2.1.0", schema_version="2.0.0")

        existing = _make_existing(based_on_version="1.0.0")
        mock_session.execute.return_value = _make_execute_result(existing)

        count = await seed_templates(mock_session)

        assert count == 1
        assert existing.based_on_version == "2.1.0"
        assert existing.content == "---\ntemplate_type: character\n---\nNew body"
        assert existing.schema_version == "2.0.0"
        mock_session.add.assert_not_called()

    @patch("narrare.setup.seed_templates.parse_template")
    @patch("narrare.setup.seed_templates.load_default_template")
    @patch("narrare.setup.seed_templates.list_default_templates")
    async def test_updates_when_existing_version_none(
        self,
        mock_list: MagicMock,
        mock_load: MagicMock,
        mock_parse: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """Existing with based_on_version=None treated as 0.0.0 → update."""
        mock_list.return_value = ["character"]
        mock_load.return_value = "content"
        mock_parse.return_value = _make_template("1.0.0")

        existing = _make_existing(based_on_version=None)
        mock_session.execute.return_value = _make_execute_result(existing)

        count = await seed_templates(mock_session)

        assert count == 1
        assert existing.based_on_version == "1.0.0"


# ---------------------------------------------------------------------------
# Skip existing templates
# ---------------------------------------------------------------------------


class TestSeedSkipExisting:
    """When a global entry exists with same or newer version, skip."""

    @patch("narrare.setup.seed_templates.parse_template")
    @patch("narrare.setup.seed_templates.load_default_template")
    @patch("narrare.setup.seed_templates.list_default_templates")
    async def test_skips_when_versions_match(
        self,
        mock_list: MagicMock,
        mock_load: MagicMock,
        mock_parse: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """Existing v2.0.0, bundled v2.0.0 → skip, return 0."""
        mock_list.return_value = ["character"]
        mock_load.return_value = "content"
        mock_parse.return_value = _make_template("2.0.0")

        existing = _make_existing(based_on_version="2.0.0")
        mock_session.execute.return_value = _make_execute_result(existing)

        count = await seed_templates(mock_session)

        assert count == 0
        mock_session.add.assert_not_called()

    @patch("narrare.setup.seed_templates.parse_template")
    @patch("narrare.setup.seed_templates.load_default_template")
    @patch("narrare.setup.seed_templates.list_default_templates")
    async def test_skips_when_stored_newer(
        self,
        mock_list: MagicMock,
        mock_load: MagicMock,
        mock_parse: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """Existing v3.0.0, bundled v2.0.0 → skip, return 0."""
        mock_list.return_value = ["character"]
        mock_load.return_value = "content"
        mock_parse.return_value = _make_template("2.0.0")

        existing = _make_existing(based_on_version="3.0.0")
        mock_session.execute.return_value = _make_execute_result(existing)

        count = await seed_templates(mock_session)

        assert count == 0


# ---------------------------------------------------------------------------
# Missing bundled template
# ---------------------------------------------------------------------------


class TestSeedMissingBundled:
    """When bundled template is missing, skip with warning."""

    @patch("narrare.setup.seed_templates.load_default_template")
    @patch("narrare.setup.seed_templates.list_default_templates")
    async def test_skips_when_load_returns_none(
        self,
        mock_list: MagicMock,
        mock_load: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """load_default_template returns None → skip, return 0."""
        mock_list.return_value = ["character"]
        mock_load.return_value = None

        count = await seed_templates(mock_session)

        assert count == 0
        mock_session.add.assert_not_called()
        mock_session.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Count of inserts + updates
# ---------------------------------------------------------------------------


class TestSeedCount:
    """Return value counts both inserts and updates."""

    @patch("narrare.setup.seed_templates.parse_template")
    @patch("narrare.setup.seed_templates.load_default_template")
    @patch("narrare.setup.seed_templates.list_default_templates")
    async def test_returns_sum_of_inserts_and_updates(
        self,
        mock_list: MagicMock,
        mock_load: MagicMock,
        mock_parse: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """1 insert + 1 update + 1 skip → return 2."""
        mock_list.return_value = [
            "character",  # no existing → insert
            "location",  # existing v1.0.0, bundled v2.0.0 → update
            "faction",  # existing v2.0.0, bundled v2.0.0 → skip
        ]
        mock_load.return_value = "content"
        mock_parse.return_value = _make_template("2.0.0")

        # First call: no existing; second: old version; third: same version
        existing_old = _make_existing("location", "1.0.0")
        existing_same = _make_existing("faction", "2.0.0")

        results = [None, existing_old, existing_same]
        call_idx = 0

        def fake_execute(stmt: object) -> MagicMock:
            nonlocal call_idx
            result = _make_execute_result(results[call_idx])
            call_idx += 1
            return result

        mock_session.execute.side_effect = fake_execute

        count = await seed_templates(mock_session)

        assert count == 2  # 1 insert + 1 update
