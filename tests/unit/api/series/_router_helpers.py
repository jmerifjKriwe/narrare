"""Helper functions for the Series router unit tests.

Mock-service builders and small factories shared by ``test_router.py`` and
``test_router_novels.py``. The ``app``/``client`` fixtures live in
``conftest.py``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from narrare.novels.schemas import NovelSummaryResponse
from narrare.series.schemas import SeriesResponse

from .conftest import TEST_USER_ID

if TYPE_CHECKING:
    from fastapi import FastAPI


def uid() -> uuid.UUID:
    """Random UUID (short alias for readability in test bodies)."""
    return uuid.uuid4()


def series_response(*, title: str = "The Expanse") -> SeriesResponse:
    """A minimal valid SeriesResponse."""
    return SeriesResponse(
        id=uid(),
        user_id=uuid.UUID(TEST_USER_ID),
        title=title,
        subtitle=None,
        description=None,
        genre=None,
        writing_language=None,
        status="draft",
        planned_novel_count=None,
        novel_count=0,
    )


def mock_series_service() -> AsyncMock:
    """A mock SeriesService exposing the router-facing surface."""
    service = AsyncMock()
    for method in (
        "create_series",
        "get_series",
        "list_series",
        "update_series",
        "delete_series",
        "list_novels",
        "reorder_novels",
        "get_settings",
        "update_settings",
    ):
        setattr(service, method, AsyncMock())
    return service


def mock_join_service() -> AsyncMock:
    """A mock SeriesJoinService exposing the router-facing surface."""
    service = AsyncMock()
    for method in ("preview_join", "apply_join", "remove_novel"):
        setattr(service, method, AsyncMock())
    return service


def use_series_service(app: FastAPI, service: AsyncMock) -> None:
    from narrare.series.dependencies import get_series_service

    app.dependency_overrides[get_series_service] = lambda: service


def use_join_service(app: FastAPI, service: AsyncMock) -> None:
    from narrare.series.dependencies import get_series_join_service

    app.dependency_overrides[get_series_join_service] = lambda: service


def mock_band_summary_service() -> AsyncMock:
    """A mock BandSummaryService exposing the router-facing surface."""
    service = AsyncMock()
    for method in ("generate", "get", "get_or_generate", "update_override"):
        setattr(service, method, AsyncMock())
    return service


def use_band_summary_service(app: FastAPI, service: AsyncMock) -> None:
    """Override ``get_band_summary_service`` with a mock."""
    from narrare.series.dependencies import get_band_summary_service

    app.dependency_overrides[get_band_summary_service] = lambda: service


def bypass_novel_ownership(app: FastAPI) -> None:
    """Override ``verify_novel_in_owned_series`` with a no-op (happy-path tests)."""
    from narrare.series.dependencies import verify_novel_in_owned_series

    app.dependency_overrides[verify_novel_in_owned_series] = lambda: None


def deny_novel_ownership(app: FastAPI) -> None:
    """Override ``verify_novel_in_owned_series`` to raise ForbiddenError (403)."""
    from narrare_core.shared.errors import ForbiddenError

    async def _deny() -> None:
        raise ForbiddenError("You do not have access to this series")

    from narrare.series.dependencies import verify_novel_in_owned_series

    app.dependency_overrides[verify_novel_in_owned_series] = _deny


__all__ = [
    "NovelSummaryResponse",
    "bypass_novel_ownership",
    "deny_novel_ownership",
    "mock_band_summary_service",
    "mock_join_service",
    "mock_series_service",
    "series_response",
    "uid",
    "use_band_summary_service",
    "use_join_service",
    "use_series_service",
]
