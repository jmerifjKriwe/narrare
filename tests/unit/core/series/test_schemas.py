from typing import Any, cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from narrare_core.series.schemas import Series, SeriesSettings


class TestSeriesSchema:
    def test_series_minimal_valid(self):
        s = Series(id=uuid4(), user_id=uuid4(), title="The Expanse", status="draft")
        assert s.subtitle is None
        assert s.genre is None
        assert s.writing_language is None
        assert s.planned_novel_count is None

    def test_series_status_invalid_rejected(self):
        # Built via model_validate (dict) so the out-of-Literal value is not
        # flagged statically; Pydantic still rejects it at runtime. Mirrors the
        # project convention in tests/unit/core/kb/test_kb_metadata.py.
        with pytest.raises(ValidationError, match="status"):
            Series.model_validate(
                {"id": uuid4(), "user_id": uuid4(), "title": "X", "status": "invalid"}
            )

    def test_series_status_values(self):
        for status in ("draft", "active", "completed"):
            s = Series(id=uuid4(), user_id=uuid4(), title="X", status=status)
            assert s.status == status

    def test_series_extra_allowed(self):
        # Extra-field behaviour exercised via model_validate + cast("Any", ...)
        # — the project convention for extra="allow" models (see test_kb_metadata).
        s = cast(
            "Any",
            Series.model_validate(
                {
                    "id": uuid4(),
                    "user_id": uuid4(),
                    "title": "X",
                    "status": "draft",
                    "future_field": "ok",
                }
            ),
        )
        assert s.future_field == "ok"


class TestSeriesSettingsSchema:
    def test_settings_minimal_valid(self):
        ss = SeriesSettings(series_id=uuid4())
        assert ss.author_voice is None  # empty in Spec 1

    def test_settings_author_voice_optional_dict(self):
        ss = SeriesSettings(series_id=uuid4(), author_voice={"foo": "bar"})
        assert ss.author_voice == {"foo": "bar"}
