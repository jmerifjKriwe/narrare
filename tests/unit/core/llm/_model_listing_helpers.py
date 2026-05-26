"""Shared test helpers for model_listing tests.

Extracted per RULE-04 (file size limits).  This module is prefixed with
``_`` so pytest does not collect it as a test file.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

import httpx


class FakeAsyncClient:
    """Minimal httpx.AsyncClient fake for catalog tests.

    Implements the async context manager protocol so ``async with FakeAsyncClient() as c:``
    works without any real HTTP calls.  The ``get`` method is configurable
    via *get_fn* — pass a sync or async callable that returns (or raises)
    whatever the test needs.
    """

    def __init__(self, get_fn: Any) -> None:
        self._get_fn = get_fn

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get(self, *args: object, **kwargs: object) -> Any:
        """Delegate to the injected get_fn.

        Supports both sync and async callables — if ``get_fn`` returns a
        coroutine, it is awaited.
        """
        result = self._get_fn(*args, **kwargs)
        if hasattr(result, "__await__"):
            result = await result
        return result


def make_mock_response(json_data: dict[str, Any]) -> AsyncMock:
    """Create a mock httpx.Response with given JSON data."""
    response = AsyncMock(spec=httpx.Response)
    response.json.return_value = json_data
    response.raise_for_status = lambda: None
    return response


@asynccontextmanager
async def patch_httpx_client(get_response: AsyncMock) -> AsyncGenerator[None]:
    """Patch ``httpx.AsyncClient`` in model_listing with a fake.

    Usage::

        resp = make_mock_response({"data": [...]})
        async with patch_httpx_client(resp):
            models = await catalog.list_models("openai", api_key="...")
    """
    from unittest.mock import patch

    def _static_get(*args: object, **kwargs: object) -> AsyncMock:
        return get_response

    fake = FakeAsyncClient(_static_get)

    with patch(
        "narrare_core.llm.model_listing.httpx.AsyncClient",
        return_value=fake,
    ):
        yield
