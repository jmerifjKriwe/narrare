"""Unit tests for template cascade resolver."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from narrare.templates.cascade_resolver import CascadeResolver
from narrare_core.templates import Template, TemplateMeta


def _make_template(
    entity_type: str = "character",
    language: str = "en",
) -> Template:
    """Create a minimal template for testing."""
    return Template(
        meta=TemplateMeta(
            template_type=entity_type,
            template_language=language,
        ),
        fields=[],
        body="# Template body",
        raw="---\ntemplate_type: character\n---\n# Body",
    )


class TestCascadeResolver:
    @patch("narrare.templates.cascade_resolver.load_default_template")
    @patch("narrare.templates.cascade_resolver.parse_template")
    def test_resolves_bundled_default(self, mock_parse: MagicMock, mock_load: MagicMock) -> None:
        """When no overrides exist, resolves bundled default."""
        template = _make_template()
        mock_load.return_value = "---\ntemplate_type: character\n---\n"
        mock_parse.return_value = template

        resolver = CascadeResolver()
        result = resolver.resolve("character", "en")

        mock_load.assert_called_once_with("character", "en")
        assert result is template

    @patch("narrare.templates.cascade_resolver.load_default_template")
    def test_returns_none_for_unknown_type(self, mock_load: MagicMock) -> None:
        """Returns None when no template exists for the entity type."""
        mock_load.return_value = None

        resolver = CascadeResolver()
        result = resolver.resolve("nonexistent_type", "en")

        assert result is None

    @patch("narrare.templates.cascade_resolver.load_default_template")
    def test_returns_none_when_no_template_at_all(self, mock_load: MagicMock) -> None:
        """Returns None when no template exists in any language.

        Language fallback is handled by core load_default_template().
        The resolver just calls it once and returns None if not found.
        """
        mock_load.return_value = None

        resolver = CascadeResolver()
        result = resolver.resolve("character", "xx")

        mock_load.assert_called_once_with("character", "xx")
        assert result is None

    @patch("narrare.templates.cascade_resolver.load_default_template")
    @patch("narrare.templates.cascade_resolver.parse_template")
    def test_list_available_returns_metadata(
        self, mock_parse: MagicMock, mock_load: MagicMock
    ) -> None:
        """list_available returns TemplateMeta for all bundled templates."""
        template = _make_template()
        mock_load.return_value = "---\ntemplate_type: character\n---\n"
        mock_parse.return_value = template

        with patch(
            "narrare.templates.cascade_resolver.list_default_templates",
            return_value=[("character", "en"), ("location", "en")],
        ):
            resolver = CascadeResolver()
            results = resolver.list_available()

        assert len(results) == 2
        assert all(isinstance(m, TemplateMeta) for m in results)
