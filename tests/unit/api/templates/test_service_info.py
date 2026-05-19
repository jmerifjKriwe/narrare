"""Unit tests for TemplateInfoService — mocked repository.

Split from test_service.py to respect RULE-04 file-size limits.
Covers: detect_updates, get_diff, cascade_info.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.templates.repository import TemplateRepository
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


# ---------------------------------------------------------------------------
# detect_updates (via TemplateInfoService)
# ---------------------------------------------------------------------------


class TestDetectUpdates:
    async def test_detect_updates_returns_list(self, mock_repo: MagicMock) -> None:
        """detect_updates returns list of UpdateInfoResponse."""
        from narrare.templates.detection_repository import TemplateDetectionRepository
        from narrare.templates.info_service import TemplateInfoService

        detection_repo = MagicMock(spec=TemplateDetectionRepository)
        detection_repo.detect_updates = AsyncMock(
            return_value=[
                {
                    "entity_type": "character",
                    "language": "en",
                    "override_version": "1.0.0",
                    "current_bundled_version": "2.0.0",
                },
            ],
        )

        info_service = TemplateInfoService(
            repository=mock_repo,
            session=MagicMock(spec=AsyncSession),
        )
        from narrare.templates.schemas import UpdateInfoResponse

        info_service.detect_updates = AsyncMock(
            return_value=[
                UpdateInfoResponse(
                    entity_type="character",
                    language="en",
                    override_version="1.0.0",
                    current_bundled_version="2.0.0",
                ),
            ],
        )

        result = await info_service.detect_updates(scope="user", scope_id=uuid.uuid4())
        assert len(result) == 1
        assert result[0].entity_type == "character"
        assert result[0].override_version == "1.0.0"
        assert result[0].current_bundled_version == "2.0.0"


# ---------------------------------------------------------------------------
# get_diff (via TemplateInfoService)
# ---------------------------------------------------------------------------


class TestGetDiff:
    async def test_get_diff_returns_diff_when_override_exists(self, mock_repo: MagicMock) -> None:
        """get_diff returns DiffResponse when override exists."""
        from narrare.templates.info_service import TemplateInfoService

        mock_repo.get_override.return_value = _make_template(
            raw="---\ntemplate_type: character\n---\n# Override",
        )

        info_service = TemplateInfoService(
            repository=mock_repo,
            session=MagicMock(spec=AsyncSession),
        )

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "narrare.templates.info_service.load_default_template",
                lambda _t, _l: "---\ntemplate_type: character\n---\n# Bundled",
            )

            result = await info_service.get_diff(
                "character", "en", scope="user", scope_id=uuid.uuid4()
            )

        assert result is not None
        assert result.override_content == "---\ntemplate_type: character\n---\n# Override"
        assert result.bundled_content == "---\ntemplate_type: character\n---\n# Bundled"

    async def test_get_diff_returns_none_when_no_override(self, mock_repo: MagicMock) -> None:
        """get_diff returns None when no override exists."""
        from narrare.templates.info_service import TemplateInfoService

        mock_repo.get_override.return_value = None

        info_service = TemplateInfoService(
            repository=mock_repo,
            session=MagicMock(spec=AsyncSession),
        )
        result = await info_service.get_diff("character", "en", scope="user", scope_id=uuid.uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# cascade_info (via TemplateInfoService)
# ---------------------------------------------------------------------------


class TestCascadeInfo:
    async def test_cascade_info_returns_paths(self, mock_repo: MagicMock) -> None:
        """cascade_info returns cascade paths for user, project, bundled."""
        from narrare.templates.info_service import TemplateInfoService

        mock_repo.get_override.return_value = None

        info_service = TemplateInfoService(
            repository=mock_repo,
            session=MagicMock(spec=AsyncSession),
        )

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "narrare.templates.info_service.load_default_template",
                lambda _t, _l: "---\ntemplate_type: character\n---\n# Body",
            )

            user_id = uuid.uuid4()
            project_id = uuid.uuid4()
            result = await info_service.cascade_info(
                "character",
                "en",
                user_id=user_id,
                project_id=project_id,
            )

        assert len(result) == 3
        assert result[0]["level"] == "user"
        assert result[1]["level"] == "project"
        assert result[2]["level"] == "bundled"
