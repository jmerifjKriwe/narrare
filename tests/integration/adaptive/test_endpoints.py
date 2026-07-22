"""Integration tests for the adaptive REST endpoints.

Covers the 200 / 401 / 422 paths per RULE-10. Uses the real DB session
(real Alembic migration, not create_all) and real service DI chain.

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create_project(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> str:
    """Create a novel + project_settings row; return the project_id."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Adaptive Test Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    return novel_resp.json()["id"]


class TestGetContext:
    """GET /adaptive/{project_id}/context."""

    @pytest.mark.asyncio
    async def test_returns_defaults_when_no_settings(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """No prior settings row → defaults (enabled=True, weights=spec)."""
        project_id = await _create_project(client, auth_headers)
        response = await client.get(
            f"/api/v1/adaptive/{project_id}/context",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["weights"]["preference"] == 0.7
        assert body["weights"]["voice_fidelity"] == 0.9
        assert body["has_any_signal"] is False
        assert body["sources"]["preference_text"] == ""

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.get(f"/api/v1/adaptive/{uuid4()}/context")
        assert response.status_code == 401


class TestToggle:
    """POST /adaptive/{project_id}/toggle."""

    @pytest.mark.asyncio
    async def test_toggle_off_then_on(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        project_id = await _create_project(client, auth_headers)

        # Toggle off:
        off = await client.post(
            f"/api/v1/adaptive/{project_id}/toggle",
            json={"enabled": False},
            headers=auth_headers,
        )
        assert off.status_code == 200
        assert off.json()["enabled"] is False

        # Verify persisted (GET reflects the toggle):
        ctx = await client.get(
            f"/api/v1/adaptive/{project_id}/context",
            headers=auth_headers,
        )
        assert ctx.json()["enabled"] is False

        # Toggle back on:
        on = await client.post(
            f"/api/v1/adaptive/{project_id}/toggle",
            json={"enabled": True},
            headers=auth_headers,
        )
        assert on.status_code == 200
        assert on.json()["enabled"] is True

    @pytest.mark.asyncio
    async def test_422_when_body_missing(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        project_id = await _create_project(client, auth_headers)
        response = await client.post(
            f"/api/v1/adaptive/{project_id}/toggle",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            f"/api/v1/adaptive/{uuid4()}/toggle",
            json={"enabled": True},
        )
        assert response.status_code == 401


class TestSetWeights:
    """POST /adaptive/{project_id}/weights."""

    @pytest.mark.asyncio
    async def test_clamps_out_of_range(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        project_id = await _create_project(client, auth_headers)
        response = await client.post(
            f"/api/v1/adaptive/{project_id}/weights",
            json={
                "preference": -0.5,
                "voice_fidelity": 2.0,
                "style_constraints": 0.5,
                "avoidance": 0.5,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["weights"]["preference"] == 0.0
        assert body["weights"]["voice_fidelity"] == 1.0
        assert body["weights"]["style_constraints"] == 0.5

        # Persisted:
        ctx = await client.get(
            f"/api/v1/adaptive/{project_id}/context",
            headers=auth_headers,
        )
        assert ctx.json()["weights"]["preference"] == 0.0

    @pytest.mark.asyncio
    async def test_preserves_enabled_flag(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Updating weights MUST NOT silently reset the enabled flag."""
        project_id = await _create_project(client, auth_headers)

        # Toggle off first:
        await client.post(
            f"/api/v1/adaptive/{project_id}/toggle",
            json={"enabled": False},
            headers=auth_headers,
        )

        # Update weights:
        response = await client.post(
            f"/api/v1/adaptive/{project_id}/weights",
            json={"preference": 0.3},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is False  # preserved
        assert response.json()["weights"]["preference"] == 0.3

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            f"/api/v1/adaptive/{uuid4()}/weights",
            json={"preference": 0.5},
        )
        assert response.status_code == 401
