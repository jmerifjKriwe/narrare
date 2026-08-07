"""Unit tests for the BandSummary SQLAlchemy model (Spec 2, Task 1).

``BandSummary`` is a 1:1 companion to ``Novel`` — ``novel_id`` is both the
primary key and the unique key, so there can be at most one summary row per
novel. These tests pin that invariant plus the column shape that the
generation pipeline (Tasks 3/6) and the migration 0038 rely on.
"""

from __future__ import annotations

from narrare.series.band_summary_models import BandSummary


def test_band_summary_tablename_is_band_summaries() -> None:
    # Break caught: renaming the table without updating migration 0038 / queries.
    assert BandSummary.__tablename__ == "band_summaries"


def test_band_summary_has_expected_columns() -> None:
    # Break caught: dropping/renaming a column the generation pipeline reads.
    cols = {c.name for c in BandSummary.__table__.columns}
    expected = {"novel_id", "full_summary", "short_summary", "override", "generated_at"}
    assert expected.issubset(cols)


def test_band_summary_novel_id_is_primary_key() -> None:
    # Break caught: losing the 1:1 PK invariant → multiple summaries per novel.
    cols = {c.name: c for c in BandSummary.__table__.columns}
    assert cols["novel_id"].primary_key is True


def test_band_summary_novel_id_is_unique() -> None:
    # Break caught: losing the 1:1 uniqueness guarantee.
    cols = {c.name: c for c in BandSummary.__table__.columns}
    assert cols["novel_id"].unique is True


def test_band_summary_novel_id_fk_targets_novels_with_cascade() -> None:
    # Break caught: pointing at the wrong table or dropping CASCADE → orphaned
    # summary rows when a novel is deleted.
    novel_id_col = {c.name: c for c in BandSummary.__table__.columns}["novel_id"]
    fks = list(novel_id_col.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.target_fullname == "novels.id"
    assert fk.ondelete == "CASCADE"


def test_band_summary_generated_at_has_server_default() -> None:
    # Break caught: removing the server_default → INSERT without a timestamp
    # would fail at the DB level for non-ORM writes.
    cols = {c.name: c for c in BandSummary.__table__.columns}
    assert cols["generated_at"].server_default is not None
