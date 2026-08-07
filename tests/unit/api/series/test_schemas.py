"""Tests for Series API Pydantic schemas (Task 3.2).

Covers CRUD schemas: SeriesCreateRequest, SeriesUpdateRequest,
SeriesResponse, SeriesSummary, SeriesSettings*. Join Flow types
(JoinEntryTreatment, JoinPreview, JoinResult) live in
test_join_schemas.py — split per RULE-04 (file-size limit 200 lines).
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from narrare.series.schemas import (
    SeriesCreateRequest,
    SeriesResponse,
    SeriesSettingsResponse,
    SeriesSettingsUpdateRequest,
    SeriesSummary,
    SeriesUpdateRequest,
)


class TestSeriesCreateRequest:
    def test_minimal_valid_defaults_none(self):
        r = SeriesCreateRequest(title="The Expanse")
        assert r.title == "The Expanse"
        assert r.subtitle is None
        assert r.description is None
        assert r.genre is None
        assert r.writing_language is None
        assert r.planned_novel_count is None
        assert r.status is None  # service defaults to draft

    def test_status_valid_accepted(self):
        for status in ("draft", "active", "completed"):
            assert SeriesCreateRequest(title="X", status=status).status == status

    def test_status_invalid_rejected(self):
        with pytest.raises(ValueError):
            SeriesCreateRequest(title="X", status="invalid")  # type: ignore[arg-type]

    def test_planned_novel_count_accepted(self):
        r = SeriesCreateRequest(title="X", planned_novel_count=9)
        assert r.planned_novel_count == 9


class TestSeriesUpdateRequest:
    def test_all_fields_optional(self):
        r = SeriesUpdateRequest()
        assert r.title is None
        assert r.subtitle is None
        assert r.description is None
        assert r.genre is None
        assert r.writing_language is None
        assert r.status is None
        assert r.planned_novel_count is None

    def test_partial_update(self):
        r = SeriesUpdateRequest(title="New Title")
        assert r.title == "New Title"
        assert r.status is None

    def test_status_invalid_rejected(self):
        with pytest.raises(ValueError):
            SeriesUpdateRequest(status="bogus")  # type: ignore[arg-type]


class TestSeriesResponse:
    def test_structure(self):
        r = SeriesResponse(
            id=uuid4(),
            user_id=uuid4(),
            title="The Expanse",
            subtitle=None,
            description=None,
            genre=None,
            writing_language=None,
            status="draft",
            planned_novel_count=None,
            novel_count=0,
        )
        assert r.novel_count == 0
        assert r.status == "draft"

    def test_from_attributes(self):
        """ORM compatibility: model_validate from an attribute-bearing object."""
        orm = SimpleNamespace(
            id=uuid4(),
            user_id=uuid4(),
            title="T",
            subtitle=None,
            description=None,
            genre=None,
            writing_language=None,
            status="active",
            planned_novel_count=3,
        )
        r = SeriesResponse.model_validate(orm)
        assert r.title == "T"
        assert r.status == "active"
        assert r.novel_count == 0  # default


class TestSeriesSummary:
    def test_structure(self):
        s = SeriesSummary(id=uuid4(), title="T", subtitle=None, status="draft", novel_count=2)
        assert s.novel_count == 2

    def test_from_attributes(self):
        orm = SimpleNamespace(id=uuid4(), title="T", subtitle=None, status="completed")
        s = SeriesSummary.model_validate(orm)
        assert s.status == "completed"
        assert s.novel_count == 0


class TestSeriesSettings:
    def test_response_and_update_defaults(self):
        r = SeriesSettingsResponse(series_id=uuid4(), author_voice=None)
        assert r.author_voice is None
        assert SeriesSettingsUpdateRequest().author_voice is None


class TestSeriesSettingsContextWindow:
    """Spec 2: context_window_size exposed + validated in settings schemas."""

    def test_response_defaults_to_three(self):
        r = SeriesSettingsResponse(series_id=uuid4(), author_voice=None)
        assert r.context_window_size == 3

    def test_response_carries_value_from_attributes(self):
        """ORM compatibility: the column value flows through model_validate."""
        orm = SimpleNamespace(
            series_id=uuid4(),
            author_voice=None,
            context_window_size=7,
        )
        r = SeriesSettingsResponse.model_validate(orm)
        assert r.context_window_size == 7

    def test_update_request_field_is_optional_unset(self):
        assert SeriesSettingsUpdateRequest().context_window_size is None

    def test_update_request_accepts_valid_value(self):
        assert SeriesSettingsUpdateRequest(context_window_size=5).context_window_size == 5

    def test_update_request_rejects_zero(self):
        with pytest.raises(ValueError):
            SeriesSettingsUpdateRequest(context_window_size=0)  # type: ignore[arg-type]

    def test_update_request_rejects_negative(self):
        with pytest.raises(ValueError):
            SeriesSettingsUpdateRequest(context_window_size=-1)  # type: ignore[arg-type]

    def test_update_request_rejects_above_max(self):
        with pytest.raises(ValueError):
            SeriesSettingsUpdateRequest(context_window_size=51)  # type: ignore[arg-type]
