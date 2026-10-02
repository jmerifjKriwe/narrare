"""Integration tests for POST /api/v1/import/preview (multipart)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestPreviewEndpoint:
    async def test_preview_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/import/preview", files=[])
        assert response.status_code == 401

    async def test_preview_returns_items(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/import/preview",
            headers=auth_headers,
            files=[
                ("files", ("ch-01.md", b"# The Thorn Wall\nbody words here", "text/markdown")),
                ("files", ("ch-02.txt", b"Chapter 2\nmore words", "text/plain")),
            ],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["file_count"] == 2
        assert body["chapter_count"] == 2
        assert body["items"][0]["suggested_title"] == "The Thorn Wall"
        assert body["items"][1]["source_file"] == "ch-02.txt"
        assert body["items"][1]["index"] == 1

    async def test_preview_rejects_docx_with_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/import/preview",
            headers=auth_headers,
            files=[("files", ("manuscript.docx", b"PK\x03\x04", "application/octet-stream"))],
        )
        assert response.status_code == 422
        assert "manuscript.docx" in response.json()["detail"]

    async def test_preview_zero_chapters_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/import/preview",
            headers=auth_headers,
            files=[("files", ("empty.md", b"   \n", "text/markdown"))],
        )
        assert response.status_code == 422
