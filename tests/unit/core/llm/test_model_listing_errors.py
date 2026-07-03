"""Tests for core/llm/model_listing.py — error handling.

Split per RULE-04 (file size limits).  See also:
- ``test_model_listing.py`` — schema, protocol, and provider tests
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from narrare_core.llm.model_listing import (
    ModelCatalogClient,
    ModelCatalogError,
)

from ._model_listing_helpers import FakeAsyncClient, make_mock_response

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def catalog() -> ModelCatalogClient:
    return ModelCatalogClient()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
class TestErrorHandling:
    """Network errors and HTTP status errors are wrapped in ModelCatalogError.

    ``filterwarnings("ignore::RuntimeWarning")`` suppresses unawaited
    coroutine warnings from ``FakeAsyncClient.__aexit__`` when an
    exception interrupts the async context manager in Python 3.14.
    """

    @pytest.mark.asyncio
    async def test_http_status_error(self, catalog: ModelCatalogClient) -> None:
        mock_response = httpx.Response(
            status_code=401,
            request=httpx.Request("GET", "https://example.com"),
            text="Unauthorized",
        )

        def _raise_http(*args: object, **kwargs: object) -> None:
            raise httpx.HTTPStatusError(
                "401",
                request=httpx.Request("GET", "https://example.com"),
                response=mock_response,
            )

        fake = FakeAsyncClient(_raise_http)
        with (
            patch(
                "narrare_core.llm.model_listing.httpx.AsyncClient",
                return_value=fake,
            ),
            pytest.raises(ModelCatalogError, match="HTTP 401") as exc_info,
        ):
            await catalog.list_models("openai", api_key="bad-key")

        assert "HTTP 401" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_network_error(self, catalog: ModelCatalogClient) -> None:
        def _raise_connect(*args: object, **kwargs: object) -> None:
            raise httpx.ConnectError("Connection refused")

        fake = FakeAsyncClient(_raise_connect)
        with (
            patch(
                "narrare_core.llm.model_listing.httpx.AsyncClient",
                return_value=fake,
            ),
            pytest.raises(ModelCatalogError, match="Network error") as exc_info,
        ):
            await catalog.list_models("anthropic", api_key="test")

        assert "Network error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_timeout_error(self, catalog: ModelCatalogClient) -> None:
        def _raise_timeout(*args: object, **kwargs: object) -> None:
            raise httpx.TimeoutException("Read timeout")

        fake = FakeAsyncClient(_raise_timeout)
        with (
            patch(
                "narrare_core.llm.model_listing.httpx.AsyncClient",
                return_value=fake,
            ),
            pytest.raises(ModelCatalogError, match="Network error") as exc_info,
        ):
            await catalog.list_models("openai", api_key="test")

        assert "Network error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_unexpected_error(self, catalog: ModelCatalogClient) -> None:
        def _raise_value(*args: object, **kwargs: object) -> None:
            raise ValueError("bad JSON")

        fake = FakeAsyncClient(_raise_value)
        with (
            patch(
                "narrare_core.llm.model_listing.httpx.AsyncClient",
                return_value=fake,
            ),
            pytest.raises(ModelCatalogError, match="Unexpected error") as exc_info,
        ):
            await catalog.list_models("openai", api_key="test")

        assert "Unexpected error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_error_preserves_provider(
        self,
        catalog: ModelCatalogClient,
    ) -> None:
        def _raise_connect(*args: object, **kwargs: object) -> None:
            raise httpx.ConnectError("Connection refused")

        fake = FakeAsyncClient(_raise_connect)
        with (
            patch(
                "narrare_core.llm.model_listing.httpx.AsyncClient",
                return_value=fake,
            ),
            pytest.raises(ModelCatalogError, match="Network error") as exc_info,
        ):
            await catalog.list_models("groq", api_key="test")

        assert exc_info.value.provider == "groq"

    @pytest.mark.asyncio
    async def test_empty_data_returns_empty_list(
        self,
        catalog: ModelCatalogClient,
    ) -> None:
        resp = make_mock_response({"data": []})
        from ._model_listing_helpers import patch_httpx_client

        async with patch_httpx_client(resp):
            models = await catalog.list_models("openai", api_key="test")

        assert models == []
