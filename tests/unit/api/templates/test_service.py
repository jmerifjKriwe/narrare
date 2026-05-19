"""Unit tests for TemplateApiService — mocked repository.

Core service tests: CRUD, resolve, list, get, save, reset.
Info service tests live in test_service_info.py.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.templates.repository import TemplateRepository
from narrare.templates.schemas import SaveOverrideRequest
from narrare.templates.service import TemplateApiService
from narrare_core.templates import Template, TemplateMeta

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_template(
    entity_type: str = "character",
    language: str = "en",
    raw: str = "---\ntemplate_type: character\ntemplate_version: 1.0.0\n---\n# Body",
) -> Template:
    """Create a minimal template for testing."""
    return Template(
        meta=TemplateMeta(
            template_type=entity_type,
            template_language=language,
            template_version="1.0.0",
            schema_version="2.0.0",
        ),
        fields=[],
        body="# Template body",
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo() -> MagicMock:
    repo = MagicMock(spec=TemplateRepository)
    repo.get_override = AsyncMock()
    repo.list_overrides = AsyncMock(return_value=[])
    repo.save_override = AsyncMock()
    repo.delete_override = AsyncMock(return_value=False)
    repo.detect_updates = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def service(mock_repo: MagicMock) -> TemplateApiService:
    return TemplateApiService(repository=mock_repo)


# ---------------------------------------------------------------------------
# list_templates
# ---------------------------------------------------------------------------


class TestListTemplates:
    async def test_list_returns_templates_with_defaults(
        self, service: TemplateApiService, mock_repo: MagicMock
    ) -> None:
        """list_templates returns bundled templates even without overrides."""
        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "narrare.templates.service.list_default_templates",
                lambda: [("character", "en")],
            )
            m.setattr(
                "narrare.templates.service.load_default_template",
                lambda _t, _l: (
                    "---\ntemplate_type: character\ntemplate_version: 1.0.0\n---\n# Body"
                ),
            )
            m.setattr(
                "narrare.templates.service.parse_template",
                lambda _r: _make_template(),
            )

            result = await service.list_templates(scope="user", scope_id=uuid.uuid4())

        assert len(result) >= 1
        char_result = [r for r in result if r.entity_type == "character"]
        assert len(char_result) == 1
        assert char_result[0].has_override is False

    async def test_list_shows_override_status(
        self, service: TemplateApiService, mock_repo: MagicMock
    ) -> None:
        """list_templates marks templates with overrides."""
        tpl = _make_template()
        mock_repo.list_overrides.return_value = [tpl]

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "narrare.templates.service.list_default_templates",
                lambda: [("character", "en")],
            )
            m.setattr(
                "narrare.templates.service.load_default_template",
                lambda _t, _l: (
                    "---\ntemplate_type: character\ntemplate_version: 1.0.0\n---\n# Body"
                ),
            )
            m.setattr(
                "narrare.templates.service.parse_template",
                lambda _r: _make_template(),
            )

            result = await service.list_templates(scope="user", scope_id=uuid.uuid4())

        char_results = [r for r in result if r.entity_type == "character"]
        assert len(char_results) == 1
        assert char_results[0].has_override is True


# ---------------------------------------------------------------------------
# get_template
# ---------------------------------------------------------------------------


class TestGetTemplate:
    async def test_get_template_returns_detail_without_override(
        self, service: TemplateApiService, mock_repo: MagicMock
    ) -> None:
        """get_template returns bundled template when no override exists."""
        mock_repo.get_override.return_value = None

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "narrare.templates.service.load_default_template",
                lambda _t, _l: (
                    "---\ntemplate_type: character\ntemplate_version: 1.0.0\n---\n# Body"
                ),
            )
            m.setattr(
                "narrare.templates.service.parse_template",
                lambda _r: _make_template(),
            )

            result = await service.get_template(
                "character", "en", scope="user", scope_id=uuid.uuid4()
            )

        assert result is not None
        assert result.entity_type == "character"
        assert result.is_overridden is False
        assert (
            result.content == "---\ntemplate_type: character\ntemplate_version: 1.0.0\n---\n# Body"
        )

    async def test_get_template_shows_override_content(
        self, service: TemplateApiService, mock_repo: MagicMock
    ) -> None:
        """get_template returns override content when override exists."""
        override = _make_template(
            raw="---\ntemplate_type: character\n---\n# Overridden body",
        )
        mock_repo.get_override.return_value = override

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "narrare.templates.service.load_default_template",
                lambda _t, _l: (
                    "---\ntemplate_type: character\ntemplate_version: 1.0.0\n---\n# Body"
                ),
            )
            m.setattr(
                "narrare.templates.service.parse_template",
                lambda _r: _make_template(),
            )

            result = await service.get_template(
                "character", "en", scope="user", scope_id=uuid.uuid4()
            )

        assert result is not None
        assert result.content == "---\ntemplate_type: character\n---\n# Overridden body"
        assert result.is_overridden is True

    async def test_get_template_returns_none_when_not_found(
        self, service: TemplateApiService, mock_repo: MagicMock
    ) -> None:
        """get_template returns None when bundled template doesn't exist."""
        mock_repo.get_override.return_value = None

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "narrare.templates.service.load_default_template",
                lambda _t, _l: None,
            )

        result = await service.get_template(
            "nonexistent", "en", scope="user", scope_id=uuid.uuid4()
        )
        assert result is None


# ---------------------------------------------------------------------------
# save_override
# ---------------------------------------------------------------------------


class TestSaveOverride:
    async def test_save_override_returns_detail(
        self, service: TemplateApiService, mock_repo: MagicMock
    ) -> None:
        """save_override returns TemplateDetailResponse."""
        mock_repo.save_override.return_value = _make_template(
            raw="---\ntemplate_type: character\n---\n# Saved",
        )

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "narrare.templates.service.load_default_template",
                lambda _t, _l: (
                    "---\ntemplate_type: character\ntemplate_version: 1.0.0\n---\n# Body"
                ),
            )

            request = SaveOverrideRequest(
                content="---\ntemplate_type: character\n---\n# Saved",
                based_on_version="1.0.0",
            )
            result = await service.save_override(
                "character",
                "en",
                request,
                scope="user",
                scope_id=uuid.uuid4(),
            )

        assert result is not None
        assert result.is_overridden is True
        assert result.content == "---\ntemplate_type: character\n---\n# Saved"


# ---------------------------------------------------------------------------
# reset_override
# ---------------------------------------------------------------------------


class TestResetOverride:
    async def test_reset_override_returns_true_when_deleted(
        self, service: TemplateApiService, mock_repo: MagicMock
    ) -> None:
        """reset_override returns True when an override was deleted."""
        mock_repo.delete_override.return_value = True
        result = await service.reset_override(
            "character", "en", scope="user", scope_id=uuid.uuid4()
        )
        assert result is True

    async def test_reset_override_returns_false_when_none(
        self, service: TemplateApiService, mock_repo: MagicMock
    ) -> None:
        """reset_override returns False when no override existed."""
        mock_repo.delete_override.return_value = False
        result = await service.reset_override(
            "character", "en", scope="user", scope_id=uuid.uuid4()
        )
        assert result is False
