"""Tests for shared/pagination.py — PaginationParams and PaginatedResponse.

Covers:
1. PaginationParams defaults, offset/limit properties, validation
2. PaginatedResponse.create factory method
3. Edge cases: single page, empty results, page bounds
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.shared.pagination import PaginatedResponse, PaginationParams

# ---------------------------------------------------------------------------
# PaginationParams
# ---------------------------------------------------------------------------


class TestPaginationParamsDefaults:
    """PaginationParams has correct defaults."""

    def test_default_page(self) -> None:
        params = PaginationParams()
        assert params.page == 1

    def test_default_page_size(self) -> None:
        params = PaginationParams()
        assert params.page_size == 20


class TestPaginationParamsOffsetLimit:
    """PaginationParams offset and limit properties."""

    def test_offset_first_page(self) -> None:
        params = PaginationParams(page=1, page_size=20)
        assert params.offset == 0

    def test_offset_second_page(self) -> None:
        params = PaginationParams(page=2, page_size=20)
        assert params.offset == 20

    def test_offset_third_page(self) -> None:
        params = PaginationParams(page=3, page_size=10)
        assert params.offset == 20

    def test_limit_equals_page_size(self) -> None:
        params = PaginationParams(page_size=50)
        assert params.limit == 50


class TestPaginationParamsValidation:
    """PaginationParams rejects invalid values."""

    def test_rejects_page_zero(self) -> None:
        with pytest.raises(ValidationError):
            PaginationParams(page=0)

    def test_rejects_negative_page(self) -> None:
        with pytest.raises(ValidationError):
            PaginationParams(page=-1)

    def test_rejects_page_size_zero(self) -> None:
        with pytest.raises(ValidationError):
            PaginationParams(page_size=0)

    def test_rejects_page_size_over_100(self) -> None:
        with pytest.raises(ValidationError):
            PaginationParams(page_size=101)

    def test_accepts_page_size_100(self) -> None:
        params = PaginationParams(page_size=100)
        assert params.page_size == 100

    def test_accepts_page_size_1(self) -> None:
        params = PaginationParams(page_size=1)
        assert params.page_size == 1


# ---------------------------------------------------------------------------
# PaginatedResponse
# ---------------------------------------------------------------------------


class TestPaginatedResponseCreate:
    """PaginatedResponse.create factory method."""

    def test_single_page(self) -> None:
        params = PaginationParams(page=1, page_size=10)
        items = ["a", "b", "c"]
        response = PaginatedResponse[str].create(items=items, total=3, params=params)
        assert response.items == items
        assert response.total == 3
        assert response.page == 1
        assert response.page_size == 10
        assert response.pages == 1

    def test_multiple_pages(self) -> None:
        params = PaginationParams(page=2, page_size=10)
        items = [f"item-{i}" for i in range(10, 20)]
        response = PaginatedResponse[str].create(items=items, total=25, params=params)
        assert response.total == 25
        assert response.pages == 3
        assert response.page == 2

    def test_empty_results(self) -> None:
        params = PaginationParams(page=1, page_size=10)
        response = PaginatedResponse[str].create(items=[], total=0, params=params)
        assert response.items == []
        assert response.total == 0
        assert response.pages == 1  # min 1 page

    def test_exact_boundary(self) -> None:
        """20 items with page_size=10 → 2 pages."""
        params = PaginationParams(page=1, page_size=10)
        response = PaginatedResponse[str].create(items=["x"] * 10, total=20, params=params)
        assert response.pages == 2

    def test_pages_calculation_ceil_division(self) -> None:
        """21 items with page_size=10 → 3 pages."""
        params = PaginationParams(page=1, page_size=10)
        response = PaginatedResponse[str].create(items=["x"] * 10, total=21, params=params)
        assert response.pages == 3
