"""Tests for Series Join Flow schemas (Task 3.2).

Split from test_schemas.py per RULE-04 (file-size limit 200 lines).
Mirrors the ``# --- Join Flow types ---`` separator in the source
schemas.py: JoinEntryTreatment, JoinPreview, JoinResult.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.series.schemas import (
    JoinEntryTreatment,
    JoinPreview,
    JoinResult,
)


class TestJoinEntryTreatment:
    def test_structure(self):
        t = JoinEntryTreatment(
            entry_id=uuid4(),
            slug="magic",
            entity_type="system",
            current_scope="novel",
            target_scope="series",
            reason_code="entity_default_canon",
            reason="Entity type 'system' defaults to Canon",
        )
        assert t.current_scope == "novel"
        assert t.target_scope == "series"

    def test_current_scope_invalid_rejected(self):
        with pytest.raises(ValueError):
            JoinEntryTreatment(
                entry_id=uuid4(),
                slug="x",
                entity_type="system",
                current_scope="series",  # type: ignore[arg-type]
                target_scope="series",
                reason_code="entity_default_canon",
                reason="r",
            )

    def test_target_scope_invalid_rejected(self):
        with pytest.raises(ValueError):
            JoinEntryTreatment(
                entry_id=uuid4(),
                slug="x",
                entity_type="system",
                current_scope="novel",
                target_scope="canon",  # type: ignore[arg-type]
                reason_code="entity_default_canon",
                reason="r",
            )


class TestJoinPreview:
    def test_structure(self):
        treatment = JoinEntryTreatment(
            entry_id=uuid4(),
            slug="magic",
            entity_type="system",
            current_scope="novel",
            target_scope="series",
            reason_code="entity_default_canon",
            reason="Entity type 'system' defaults to Canon",
        )
        p = JoinPreview(
            series_id=uuid4(), novel_id=uuid4(), canon_empty=True, treatments=[treatment]
        )
        assert p.canon_empty is True
        assert len(p.treatments) == 1

    def test_empty_treatments_allowed(self):
        p = JoinPreview(series_id=uuid4(), novel_id=uuid4(), canon_empty=False, treatments=[])
        assert p.treatments == []


class TestJoinResult:
    def test_structure(self):
        r = JoinResult(
            series_id=uuid4(),
            novel_id=uuid4(),
            position=2,
            promoted_to_canon=5,
            kept_as_overlay=12,
        )
        assert r.promoted_to_canon == 5
        assert r.kept_as_overlay == 12
        assert r.position == 2

    def test_zero_promotions_when_canon_nonempty(self):
        r = JoinResult(
            series_id=uuid4(),
            novel_id=uuid4(),
            position=1,
            promoted_to_canon=0,
            kept_as_overlay=3,
        )
        assert r.promoted_to_canon == 0
