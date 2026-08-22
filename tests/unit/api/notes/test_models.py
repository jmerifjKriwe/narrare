"""Unit tests for the Note SQLAlchemy model and migration 0041 (NOTES-001).

Model tests mirror ``tests/unit/api/series/test_models.py``: table-level
metadata assertions only, no database. Migration tests inspect the 0041
module source (the ``tests/unit/api/templates/test_migration_0012.py``
pattern) so the RULE-14 pairing of model + migration is pinned in the unit
tier; executing the SQL is the integration tier's job (``alembic upgrade
head`` via the session conftest).
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import CheckConstraint, DefaultClause

from narrare._app.database import Base
from narrare.notes.models import Note

if TYPE_CHECKING:
    from types import ModuleType

# Pyright-typed table handle: ``Note.__table__`` is declared as FromClause
# (constraints/indexes unknown there), while ``MetaData.tables`` maps to
# Table — no cast, no type: ignore (RULE-23).
_TABLE = Base.metadata.tables["notes"]

# The five indexes migration 0041 owns — asserted for BOTH the model
# metadata and the migration source so the RULE-14 pair cannot drift.
_ALL_NOTES_INDEXES = (
    "ix_notes_user_id",
    "ix_notes_novel_id",
    "ix_notes_series_id",
    "ix_notes_tags",
    "ix_notes_user_updated",
)


def _load_migration_0041() -> ModuleType:
    """Load the 0041_notes migration module directly from the versions dir.

    Deliberately no skip-on-missing (unlike the 0012 loader): a missing 0041
    file means the model landed without its migration — a RULE-14 violation
    that must fail loudly instead of skipping.
    """
    migration_file = (
        Path(__file__).resolve().parents[4]
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "0041_notes.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0041_notes", migration_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot build import spec for {migration_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_note_model_tablename() -> None:
    assert Note.__tablename__ == "notes"


def test_note_model_has_exactly_the_spec_columns() -> None:
    # Spec §4 column set — exact equality pins scope (no accidental columns).
    cols = {c.name for c in _TABLE.columns}
    expected = {
        "id",
        "user_id",
        "title",
        "content",
        "note_type",
        "tags",
        "novel_id",
        "series_id",
        "created_at",
        "updated_at",
    }
    assert cols == expected


def test_note_model_scope_invariant_constraint() -> None:
    # Spec §4: a note links to ONE novel OR ONE series, never both.
    # Both NULL = global note (the normal case) — inverted semantics vs.
    # ck_kb_entries_scope_invariant (0037).
    scope = [
        c
        for c in _TABLE.constraints
        if isinstance(c, CheckConstraint) and c.name == "ck_notes_scope_invariant"
    ]
    assert len(scope) == 1
    # Full literal incl. the leading NOT ( — the uninverted substring alone
    # would also match inverted/stricter scope semantics (e.g. a CHECK that
    # requires a link on every row), silently blessing the wrong invariant.
    assert "NOT (novel_id IS NOT NULL AND series_id IS NOT NULL)" in str(scope[0].sqltext)


def test_note_model_note_type_constraint() -> None:
    # Language-neutral type keys — localized labels live in the frontend.
    type_check = [
        c
        for c in _TABLE.constraints
        if isinstance(c, CheckConstraint) and c.name == "ck_notes_note_type"
    ]
    assert len(type_check) == 1
    assert "note_type IN ('idea', 'concept', 'question', 'other')" in str(type_check[0].sqltext)


def test_note_model_tags_index_is_gin() -> None:
    # GIN supports tag autocomplete prefix filters + containment lookups.
    tags = [i for i in _TABLE.indexes if i.name == "ix_notes_tags"]
    assert len(tags) == 1
    assert tags[0].dialect_options["postgresql"]["using"] == "gin"


def test_note_model_user_updated_composite_index() -> None:
    user_updated = [i for i in _TABLE.indexes if i.name == "ix_notes_user_updated"]
    assert len(user_updated) == 1
    assert [c.name for c in user_updated[0].columns] == ["user_id", "updated_at"]


def test_note_model_scope_links_are_optional_and_set_null() -> None:
    # Links are optional and ON DELETE SET NULL — the note outlives the
    # linked entity (spec §4).
    fks = {fk.parent.name: fk for fk in _TABLE.foreign_keys}
    assert set(fks) == {"novel_id", "series_id"}
    assert fks["novel_id"].target_fullname == "novels.id"
    assert fks["novel_id"].ondelete == "SET NULL"
    assert fks["series_id"].target_fullname == "series.id"
    assert fks["series_id"].ondelete == "SET NULL"
    cols = {c.name: c for c in _TABLE.columns}
    assert cols["novel_id"].nullable is True
    assert cols["series_id"].nullable is True


def test_note_model_server_defaults_cover_non_orm_inserts() -> None:
    # Mirrors the 0038/0039 backfill convention: server_defaults keep
    # non-ORM inserts valid without knowing the Python-side defaults.
    cols = {c.name: c for c in _TABLE.columns}
    assert cols["user_id"].nullable is False
    assert cols["title"].nullable is True
    assert cols["content"].nullable is False
    assert cols["note_type"].nullable is False
    assert cols["tags"].nullable is False
    for name in ("content", "note_type", "tags", "created_at", "updated_at"):
        assert cols[name].server_default is not None
    # Exact default values — isinstance narrows DefaultClause so .arg is
    # typed (FetchedValue has no .arg; RULE-23: narrow instead of ignore).
    expected_defaults = {"content": "''", "note_type": "'idea'", "tags": "'{}'"}
    for name, expected in expected_defaults.items():
        server_default = cols[name].server_default
        assert isinstance(server_default, DefaultClause)
        assert str(server_default.arg) == expected


def test_note_model_single_column_indexes_present() -> None:
    # user_id follows the Series ownership pattern (plain UUID, indexed, no
    # FK); the FK columns are indexed for scope-filtered lookups.
    names = {i.name for i in _TABLE.indexes}
    assert {"ix_notes_user_id", "ix_notes_novel_id", "ix_notes_series_id"} <= names


@pytest.mark.mutation_inert
class TestMigration0041Metadata:
    """Revision metadata pins the chain head and the RULE-14 pairing."""

    def test_revision_chain_extends_0040_head(self) -> None:
        mod = _load_migration_0041()
        assert mod.revision == "0041_notes"
        assert mod.down_revision == "0040_series_drift_results"

    def test_upgrade_and_downgrade_are_callable(self) -> None:
        mod = _load_migration_0041()
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)


@pytest.mark.mutation_inert
class TestMigration0041Upgrade:
    """Upgrade source pins table shape, FK semantics, and indexes."""

    def test_creates_notes_table_with_both_check_constraints(self) -> None:
        source = inspect.getsource(_load_migration_0041().upgrade)
        assert 'op.create_table(\n        "notes"' in source
        assert "ck_notes_scope_invariant" in source
        assert "ck_notes_note_type" in source
        # Full literal incl. the leading NOT ( — the uninverted substring alone
        # cannot distinguish notes semantics (both NULL = global, allowed)
        # from KB-style semantics (0037: both NULL forbidden).
        assert "NOT (novel_id IS NOT NULL AND series_id IS NOT NULL)" in source

    def test_fk_links_use_on_delete_set_null(self) -> None:
        source = inspect.getsource(_load_migration_0041().upgrade)
        assert 'sa.ForeignKey("novels.id", ondelete="SET NULL")' in source
        assert 'sa.ForeignKey("series.id", ondelete="SET NULL")' in source

    def test_creates_all_five_indexes_with_gin_tags(self) -> None:
        source = inspect.getsource(_load_migration_0041().upgrade)
        for name in _ALL_NOTES_INDEXES:
            assert f'op.create_index("{name}", "notes"' in source
        # gin is bound to the tags index line itself — a bare
        # postgresql_using="gin" check could pass with gin attached to any
        # other create_index call.
        assert (
            'op.create_index("ix_notes_tags", "notes", ["tags"], postgresql_using="gin")' in source
        )


@pytest.mark.mutation_inert
class TestMigration0041Downgrade:
    """Downgrade is the exact reverse of upgrade (atomic pair, RULE-14)."""

    def test_drops_all_indexes_then_table(self) -> None:
        source = inspect.getsource(_load_migration_0041().downgrade)
        for name in _ALL_NOTES_INDEXES:
            assert f'op.drop_index("{name}", table_name="notes")' in source
        # Indexes drop BEFORE the table — the explicit reverse order keeps
        # the pair symmetric by construction (drop_table alone would also
        # remove them implicitly).
        assert source.index('op.drop_table("notes")') > source.rindex("op.drop_index")
