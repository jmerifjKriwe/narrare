"""Unit tests for template cascade resolver."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from narrare.templates.cascade_resolver import CascadeResolver
from narrare.templates.contracts import TemplateRepositoryProtocol
from narrare_core.templates import Template, TemplateMeta


def _make_template(
    entity_type: str = "character",
) -> Template:
    """Create a minimal template for testing."""
    return Template(
        meta=TemplateMeta(
            template_type=entity_type,
            template_version="1.0.0",
        ),
        fields=[],
        body="# Template body",
        raw="---\ntemplate_type: character\n---\n# Body",
    )


class TestCascadeResolver:
    @patch("narrare.templates.cascade_resolver.load_default_template")
    @patch("narrare.templates.cascade_resolver.parse_template")
    async def test_resolves_bundled_default(
        self, mock_parse: MagicMock, mock_load: MagicMock
    ) -> None:
        """When no overrides exist, resolves bundled default."""
        template = _make_template()
        mock_load.return_value = "---\ntemplate_type: character\n---\n"
        mock_parse.return_value = template

        resolver = CascadeResolver()
        result = await resolver.resolve("character")

        mock_load.assert_called_once_with("character")
        assert result is template

    @patch("narrare.templates.cascade_resolver.load_default_template")
    async def test_returns_none_for_unknown_type(self, mock_load: MagicMock) -> None:
        """Returns None when no template exists for the entity type."""
        mock_load.return_value = None

        resolver = CascadeResolver()
        result = await resolver.resolve("nonexistent_type")

        assert result is None

    @patch("narrare.templates.cascade_resolver.load_default_template")
    @patch("narrare.templates.cascade_resolver.parse_template")
    async def test_resolve_with_repository_checks_user_override(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
    ) -> None:
        """With repository, checks user override before bundled default."""
        mock_repo = MagicMock(spec=TemplateRepositoryProtocol)
        mock_repo.get_override = AsyncMock()
        mock_repo.get_override.return_value = None  # No user override

        mock_load.return_value = "---\ntemplate_type: character\n---\n"
        mock_parse.return_value = _make_template()

        resolver = CascadeResolver(repository=mock_repo)
        result = await resolver.resolve("character", user_id=uuid.uuid4())

        mock_repo.get_override.assert_called_once()
        assert result is not None
        assert result.meta.template_type == "character"

    @patch("narrare.templates.cascade_resolver.load_default_template")
    @patch("narrare.templates.cascade_resolver.parse_template")
    async def test_resolve_returns_user_override_when_exists(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
    ) -> None:
        """User override is returned when it exists."""
        mock_repo = MagicMock(spec=TemplateRepositoryProtocol)
        user_tpl = _make_template()
        mock_repo.get_override = AsyncMock(return_value=user_tpl)

        resolver = CascadeResolver(repository=mock_repo)
        user_id = uuid.uuid4()
        result = await resolver.resolve("character", user_id=user_id)

        mock_repo.get_override.assert_called_once_with("character", "user", user_id)
        assert result is user_tpl
        mock_load.assert_not_called()

    @patch("narrare.templates.cascade_resolver.load_default_template")
    @patch("narrare.templates.cascade_resolver.parse_template")
    async def test_resolve_checks_project_after_user(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
    ) -> None:
        """After user override not found, checks project override."""
        mock_repo = MagicMock(spec=TemplateRepositoryProtocol)

        async def fake_get_override(et: str, scope: str, sid: uuid.UUID | None) -> Template | None:
            if scope == "user":
                return None
            if scope == "project":
                return _make_template()
            return None

        mock_repo.get_override = AsyncMock(side_effect=fake_get_override)

        resolver = CascadeResolver(repository=mock_repo)
        result = await resolver.resolve(
            "character",
            user_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )

        assert result is not None
        assert result.meta.template_version == "1.0.0"
        mock_load.assert_not_called()

    def test_resolve_sync_returns_bundled(self) -> None:
        """resolve_sync returns bundled default."""
        with (
            patch(
                "narrare.templates.cascade_resolver.load_default_template",
                return_value="---\ntemplate_type: character\n---\n",
            ),
            patch(
                "narrare.templates.cascade_resolver.parse_template",
                return_value=_make_template(),
            ),
        ):
            resolver = CascadeResolver()
            result = resolver.resolve_sync("character")
            assert result is not None
            assert result.meta.template_type == "character"

    @patch("narrare.templates.cascade_resolver.load_default_template")
    @patch("narrare.templates.cascade_resolver.parse_template")
    def test_list_available_returns_metadata(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
    ) -> None:
        """list_available returns TemplateMeta for all bundled templates."""
        template = _make_template()
        mock_load.return_value = "---\ntemplate_type: character\n---\n"
        mock_parse.return_value = template

        with patch(
            "narrare.templates.cascade_resolver.list_default_templates",
            return_value=["character", "location"],
        ):
            resolver = CascadeResolver()
            results = resolver.list_available()

        assert len(results) == 2
        assert all(isinstance(m, TemplateMeta) for m in results)
