"""Unit tests for style variants router — style variant regeneration SSE endpoint.

Tests the thin delegation layer (RULE-06) ensuring routes delegate to
StyleVariantService and map errors correctly.

StyleVariantRegenerateRequest schema requires:
  - source_text (min 50)
   - style_variant (enum: leaner, more_lyrical, more_tense,
     more_intimate, more_dialogue, more_sensory)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare._app.rate_limits import AI_WRITE_LIMITER

TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create test app with overridden dependencies for unit testing."""
    application = create_app()

    async def _mock_session():
        mock = AsyncMock()
        mock.execute = AsyncMock()
        yield mock

    async def _mock_auth() -> str:
        return TEST_USER_ID

    application.dependency_overrides[get_async_session] = _mock_session
    application.dependency_overrides[get_current_user_id] = _mock_auth
    application.dependency_overrides[AI_WRITE_LIMITER] = lambda: None
    return application


@pytest.fixture
async def client(app):
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Origin": "http://localhost:3000"}
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def chapter_id() -> UUID:
    return uuid4()


@pytest.fixture
def novel_id() -> UUID:
    return uuid4()


def _mock_style_variant_service() -> AsyncMock:
    """Create a mock StyleVariantService with pre-configured methods."""
    from narrare.writing.style_variant_service import StyleVariantService

    service = AsyncMock()
    service.validate_variant = AsyncMock()
    service.stream_variant = MagicMock(spec=StyleVariantService)
    return service


# ---------------------------------------------------------------------------
# Style Variants (SSE)
# ---------------------------------------------------------------------------


class TestStyleVariants:
    """Tests for POST /api/v1/writing/chapters/{chapter_id}/style-variants/regenerate (SSE)."""

    async def test_style_variants_returns_200_with_valid_input(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Happy path: valid style variant request returns 200 with SSE stream."""

        async def _stream():
            chunk = MagicMock(spec=["text", "is_final", "context_meta", "usage"])
            chunk.text = '\\boxed{"variant text"}'
            chunk.is_final = True
            chunk.context_meta = None
            chunk.usage = None
            yield chunk

        mock_service = _mock_style_variant_service()
        mock_service.validate_variant = AsyncMock()
        mock_service.stream_variant.return_value = _stream()

        with patch(
            "narrare.writing.router_style_variants.get_style_variant_service",
            return_value=mock_service,
        ):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
                params={"novel_id": str(novel_id)},
                json={
                    "source_text": "x" * 50,
                    "style_variant": "more_lyrical",
                },
            )

        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers.get("content-type", "")

        content = await response.aread()
        assert b"variant text" in content
        assert b"[DONE]" in content

    async def test_style_variants_returns_422_with_missing_source_text(
        self,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Validation: missing source_text returns 422."""
        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"style_variant": "more_lyrical"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_style_variants_returns_422_with_short_source_text(
        self,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Validation: source_text under 50 chars returns 422."""
        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"source_text": "too short", "style_variant": "more_lyrical"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_style_variants_returns_422_with_missing_style_variant(
        self,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Validation: missing style_variant returns 422."""
        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"source_text": "x" * 50},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_style_variants_returns_422_with_invalid_style_variant(
        self,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Validation: invalid style_variant value returns 422."""
        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"source_text": "x" * 50, "style_variant": "invalid_variant"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_style_variants_returns_422_with_invalid_uuid(
        self,
        client: AsyncClient,
        novel_id: UUID,
    ) -> None:
        """Validation: non-UUID chapter_id returns 422."""
        response = await client.post(
            "/api/v1/writing/chapters/not-a-uuid/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"source_text": "x" * 50, "style_variant": "more_lyrical"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_style_variants_returns_404_when_validation_fails(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Error: non-existent chapter/novel returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = _mock_style_variant_service()
        mock_service.validate_variant.side_effect = NotFoundError(
            "Chapter",
            identifier=str(chapter_id),
        )

        with patch(
            "narrare.writing.router_style_variants.get_style_variant_service",
            return_value=mock_service,
        ):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
                params={"novel_id": str(novel_id)},
                json={"source_text": "x" * 50, "style_variant": "more_lyrical"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_style_variants_context_meta_event(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """SSE: first event can be context_meta (CR-07 pattern)."""

        async def _stream_with_meta():
            meta_chunk = MagicMock(spec=["text", "is_final", "context_meta", "usage"])
            meta_chunk.text = ""
            meta_chunk.is_final = False
            meta_chunk.context_meta = {"kb_characters_count": 3}
            meta_chunk.usage = None
            yield meta_chunk

            text_chunk = MagicMock(spec=["text", "is_final", "context_meta", "usage"])
            text_chunk.text = '\\boxed{"variant text"}'
            text_chunk.is_final = True
            text_chunk.context_meta = None
            text_chunk.usage = None
            yield text_chunk

        mock_service = _mock_style_variant_service()
        mock_service.validate_variant = AsyncMock()
        mock_service.stream_variant.return_value = _stream_with_meta()

        with patch(
            "narrare.writing.router_style_variants.get_style_variant_service",
            return_value=mock_service,
        ):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
                params={"novel_id": str(novel_id)},
                json={"source_text": "x" * 50, "style_variant": "more_lyrical"},
            )

        assert response.status_code == status.HTTP_200_OK

        content = await response.aread()
        assert b"context_meta" in content
        assert b"kb_characters_count" in content
        assert b"variant text" in content
