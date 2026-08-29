"""Integration tests for embedding admin API endpoints.

Tests all three admin endpoints:
- GET /api/v1/admin/embeddings/status/{novel_id}
- POST /api/v1/admin/embeddings/reprocess/{novel_id}
- GET /api/v1/admin/embeddings/model

Since the IDOR remediation (plan §S13, PO decision D3:a) the two
novel-scoped admin routes are ownership-gated: the happy-path tests
must address a novel the caller actually owns (created via the API);
an unknown or foreign novel id surfaces as 404.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create_owned_novel(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> str:
    """Create a novel owned by the authenticated caller (IDOR S13)."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Embedding Admin Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    return novel_resp.json()["id"]


class TestEmbeddingStatusEndpoint:
    """GET /api/v1/admin/embeddings/status/{novel_id}"""

    async def test_status_with_no_embeddings(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Status endpoint should return zeros for a novel with no embeddings."""
        novel_id = await _create_owned_novel(client, auth_headers)
        response = await client.get(
            f"/api/v1/admin/embeddings/status/{novel_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["embedded"] == 0
        assert data["pending"] == 0
        assert data["failed"] == 0
        assert data["coverage_percentage"] == 0.0

    async def test_status_for_unknown_novel_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Ownership gate (IDOR S13): unknown ≡ foreign novel → 404."""
        response = await client.get(
            f"/api/v1/admin/embeddings/status/{uuid.uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_status_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """Status endpoint should return 401 without auth."""
        novel_id = uuid.uuid4()
        response = await client.get(
            f"/api/v1/admin/embeddings/status/{novel_id}",
        )

        assert response.status_code == 401


class TestEmbeddingReprocessEndpoint:
    """POST /api/v1/admin/embeddings/reprocess/{novel_id}"""

    async def test_reprocess_returns_zero_for_empty_novel(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Reprocess should return queued=0 for a novel with no entries."""
        novel_id = await _create_owned_novel(client, auth_headers)
        response = await client.post(
            f"/api/v1/admin/embeddings/reprocess/{novel_id}",
            headers=auth_headers,
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["queued"] == 0
        assert "message" in data

    async def test_reprocess_with_model_override(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Reprocess should accept a model parameter."""
        novel_id = await _create_owned_novel(client, auth_headers)
        response = await client.post(
            f"/api/v1/admin/embeddings/reprocess/{novel_id}",
            headers=auth_headers,
            json={"model": "text-embedding-3-large"},
        )

        assert response.status_code == 200

    async def test_reprocess_for_unknown_novel_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Ownership gate (IDOR S13): unknown ≡ foreign novel → 404."""
        response = await client.post(
            f"/api/v1/admin/embeddings/reprocess/{uuid.uuid4()}",
            headers=auth_headers,
            json={},
        )

        assert response.status_code == 404

    async def test_reprocess_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """Reprocess endpoint should return 401 without auth."""
        novel_id = uuid.uuid4()
        response = await client.post(
            f"/api/v1/admin/embeddings/reprocess/{novel_id}",
            json={},
        )

        assert response.status_code == 401


class TestEmbeddingModelEndpoint:
    """GET /api/v1/admin/embeddings/model"""

    async def test_model_info_returns_current_config(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Model info endpoint should return current embedding config."""
        response = await client.get(
            "/api/v1/admin/embeddings/model",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "text-embedding-3-small"
        assert data["dimension"] == 1536
        assert data["provider"] == "openai"

    async def test_model_info_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """Model info endpoint should return 401 without auth."""
        response = await client.get(
            "/api/v1/admin/embeddings/model",
        )

        assert response.status_code == 401
