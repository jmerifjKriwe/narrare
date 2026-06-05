"""Integration tests for template CRUD API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest_asyncio

from narrare.templates.schemas import (
    DiffResponse,
    TemplateDetailResponse,
    TemplateInfoResponse,
    UpdateInfoResponse,
)

if TYPE_CHECKING:
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_ENTITY_TYPE = "character"


async def _create_novel(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    """Create a novel and return its ID.

    Raises:
        AssertionError: If the API returns a non-201 status, with diagnostic
            info (status, body) to help debug fixture-failure flakiness.
    """
    resp = await client.post(
        "/api/v1/novels",
        json={"title": "Templates Test Novel", "language": "en"},
        headers=auth_headers,
    )
    if resp.status_code != 201:
        body = resp.text[:500] if resp.text else "(empty)"
        raise AssertionError(f"Novel creation failed: status={resp.status_code}, body={body}")
    return resp.json()["id"]


def _template_url(novel_id: str, *parts: str) -> str:
    """Build a template endpoint URL."""
    base = f"/api/v1/novels/{novel_id}/kb/templates"
    return "/".join([base, *parts]) if parts else base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def novel_id(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    """Create a test novel and return its ID."""
    return await _create_novel(client, auth_headers)


# ---------------------------------------------------------------------------
# TestListTemplates
# ---------------------------------------------------------------------------


class TestListTemplates:
    async def test_list_templates_returns_200(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.get(_template_url(novel_id), headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            TemplateInfoResponse.model_validate(data[0])

    async def test_list_templates_returns_401_without_auth(
        self, client: AsyncClient, novel_id: str
    ) -> None:
        response = await client.get(_template_url(novel_id))
        assert response.status_code == 401

    async def test_list_templates_with_entity_type_filter(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.get(
            _template_url(novel_id),
            params={"entity_type": _VALID_ENTITY_TYPE},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for item in data:
            assert item["entity_type"] == _VALID_ENTITY_TYPE


# ---------------------------------------------------------------------------
# TestGetTemplate
# ---------------------------------------------------------------------------


class TestGetTemplate:
    async def test_get_template_returns_200_for_known_type(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.get(
            _template_url(novel_id, _VALID_ENTITY_TYPE),
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        validated = TemplateDetailResponse.model_validate(data)
        assert validated.entity_type == _VALID_ENTITY_TYPE
        assert isinstance(validated.content, str)
        assert len(validated.content) > 0

    async def test_get_template_returns_404_for_unknown_type(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.get(
            _template_url(novel_id, "nonexistent_type"),
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_get_template_returns_401_without_auth(
        self, client: AsyncClient, novel_id: str
    ) -> None:
        response = await client.get(_template_url(novel_id, _VALID_ENTITY_TYPE))
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# TestSaveOverride
# ---------------------------------------------------------------------------


class TestSaveOverride:
    async def test_save_override_returns_201(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        override_content = "---\ntemplate_type: character\n---\nCustom template content"
        response = await client.post(
            _template_url(novel_id, _VALID_ENTITY_TYPE),
            json={"content": override_content},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        validated = TemplateDetailResponse.model_validate(data)
        assert validated.entity_type == _VALID_ENTITY_TYPE
        assert validated.is_overridden is True
        assert validated.content == override_content

    async def test_save_override_returns_401_without_auth(
        self, client: AsyncClient, novel_id: str
    ) -> None:
        response = await client.post(
            _template_url(novel_id, _VALID_ENTITY_TYPE),
            json={"content": "some content"},
        )
        assert response.status_code == 401

    async def test_save_override_with_empty_content_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.post(
            _template_url(novel_id, _VALID_ENTITY_TYPE),
            json={"content": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# TestResetOverride
# ---------------------------------------------------------------------------


class TestResetOverride:
    async def test_reset_override_returns_200(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        # First save an override so we have something to reset
        await client.post(
            _template_url(novel_id, _VALID_ENTITY_TYPE),
            json={"content": "Override to delete"},
            headers=auth_headers,
        )

        response = await client.delete(
            _template_url(novel_id, _VALID_ENTITY_TYPE),
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json() is True

        # Verify override is gone — template should still exist as bundled
        get_resp = await client.get(
            _template_url(novel_id, _VALID_ENTITY_TYPE),
            headers=auth_headers,
        )
        assert get_resp.status_code == 200
        detail = TemplateDetailResponse.model_validate(get_resp.json())
        assert detail.is_overridden is False

    async def test_reset_override_returns_401_without_auth(
        self, client: AsyncClient, novel_id: str
    ) -> None:
        response = await client.delete(_template_url(novel_id, _VALID_ENTITY_TYPE))
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# TestDetectUpdates
# ---------------------------------------------------------------------------


class TestDetectUpdates:
    async def test_detect_updates_returns_200(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.get(
            _template_url(novel_id, "updates"),
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for item in data:
            UpdateInfoResponse.model_validate(item)


# ---------------------------------------------------------------------------
# TestGetDiff
# ---------------------------------------------------------------------------


class TestGetDiff:
    async def test_get_diff_returns_404_without_override(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.get(
            _template_url(novel_id, _VALID_ENTITY_TYPE, "diff"),
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_get_diff_returns_200_with_override(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        # Save an override first so diff has both sides to compare
        override_content = "---\ntemplate_type: character\n---\nCustom content"
        await client.post(
            _template_url(novel_id, _VALID_ENTITY_TYPE),
            json={"content": override_content},
            headers=auth_headers,
        )

        response = await client.get(
            _template_url(novel_id, _VALID_ENTITY_TYPE, "diff"),
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        validated = DiffResponse.model_validate(data)
        assert validated.entity_type == _VALID_ENTITY_TYPE
        assert validated.override_content == override_content
        assert isinstance(validated.bundled_content, str)
