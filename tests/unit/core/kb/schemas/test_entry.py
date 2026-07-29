"""Unit tests for KBEntry Single-Table-Inheritance (STI) types.

Schema 2A+STI: one physical ``kb_entries`` table, two discriminated Pydantic
types at the Core layer.

    scope="series" → SeriesKBEntry  (novel_id IS NULL — Canon for the series)
    scope="novel"  → NovelKBEntry   (novel_id IS NOT NULL — Overlay in one novel)

The DB invariant is mirrored physically by ``ck_kb_entries_scope_invariant``
(Alembic 0037). These tests pin the *Core-layer* typing invariants.

Runtime-validation cases (invalid Literal values, extra fields, None-typed
field rejection) are exercised via ``model_validate`` + ``cast("Any", ...)``
per the project convention — see ``tests/unit/core/kb/test_kb_metadata.py``
and ``tests/unit/core/series/test_schemas.py``. This keeps the pyright-tests
gate clean (no typed kwargs that would be flagged statically).
"""

from __future__ import annotations

from typing import Any, TypedDict, cast
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from narrare_core.kb.schemas import (
    KBEntry,
    KBEntryBase,
    NovelKBEntry,
    SeriesKBEntry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _CommonFields(TypedDict):
    """Minimal required common fields for any KBEntry variant.

    TypedDict (not ``dict[str, object]``) so ``**_common_fields()`` carries
    per-key types — pyright then maps each key to the matching constructor
    parameter instead of seeing every value as ``object``.
    """

    id: UUID
    entity_type: str
    name: str
    slug: str


def _common_fields() -> _CommonFields:
    return {
        "id": uuid4(),
        "entity_type": "character",
        "name": "Ela the Flame",
        "slug": "ela-the-flame",
    }


# ---------------------------------------------------------------------------
# SeriesKBEntry
# ---------------------------------------------------------------------------


class TestSeriesKBEntry:
    """Series-Canon KB entry — shared across all novels in the series."""

    def test_minimal_valid(self) -> None:
        entry = SeriesKBEntry(**_common_fields(), series_id=uuid4())
        assert entry.scope == "series"
        assert entry.series_id is not None
        # Canon invariant: novel_id and base_entry_id must be None.
        assert entry.novel_id is None
        assert entry.base_entry_id is None

    def test_scope_defaults_to_series(self) -> None:
        """scope is implicit for SeriesKBEntry (no need to pass it)."""
        entry = SeriesKBEntry(**_common_fields(), series_id=uuid4())
        assert entry.scope == "series"

    def test_status_defaults_to_draft(self) -> None:
        entry = SeriesKBEntry(**_common_fields(), series_id=uuid4())
        assert entry.status == "draft"

    def test_requires_series_id(self) -> None:
        """A Canon entry without series_id is invalid."""
        with pytest.raises(ValidationError, match="series_id"):
            SeriesKBEntry.model_validate(_common_fields())

    def test_rejects_novel_id(self) -> None:
        """Canon invariant: novel_id must be None; a value is rejected."""
        with pytest.raises(ValidationError, match="novel_id"):
            cast(
                "Any",
                SeriesKBEntry.model_validate(
                    {**_common_fields(), "series_id": uuid4(), "novel_id": uuid4()},
                ),
            )

    def test_rejects_base_entry_id(self) -> None:
        """Canon invariant: base_entry_id must be None; a value is rejected."""
        with pytest.raises(ValidationError, match="base_entry_id"):
            cast(
                "Any",
                SeriesKBEntry.model_validate(
                    {**_common_fields(), "series_id": uuid4(), "base_entry_id": uuid4()},
                ),
            )

    def test_rejects_wrong_scope(self) -> None:
        """scope is locked to 'series' for this type."""
        with pytest.raises(ValidationError, match="scope"):
            cast(
                "Any",
                SeriesKBEntry.model_validate(
                    {**_common_fields(), "series_id": uuid4(), "scope": "novel"},
                ),
            )


# ---------------------------------------------------------------------------
# NovelKBEntry
# ---------------------------------------------------------------------------


class TestNovelKBEntry:
    """Novel-Overlay KB entry — valid in one specific novel."""

    def test_minimal_valid(self) -> None:
        entry = NovelKBEntry(**_common_fields(), novel_id=uuid4())
        assert entry.scope == "novel"
        assert entry.novel_id is not None
        # Overlay may or may not link back to a series / base entry.
        assert entry.series_id is None
        assert entry.base_entry_id is None

    def test_scope_defaults_to_novel(self) -> None:
        entry = NovelKBEntry(**_common_fields(), novel_id=uuid4())
        assert entry.scope == "novel"

    def test_requires_novel_id(self) -> None:
        """An Overlay entry without novel_id is invalid."""
        with pytest.raises(ValidationError, match="novel_id"):
            NovelKBEntry.model_validate(_common_fields())

    def test_optional_series_and_base_link(self) -> None:
        """An Overlay can optionally link to its series and base Canon entry."""
        series_id = uuid4()
        base_entry_id = uuid4()
        entry = NovelKBEntry(
            **_common_fields(),
            novel_id=uuid4(),
            series_id=series_id,
            base_entry_id=base_entry_id,
        )
        assert entry.series_id == series_id
        assert entry.base_entry_id == base_entry_id

    def test_rejects_wrong_scope(self) -> None:
        """scope is locked to 'novel' for this type."""
        with pytest.raises(ValidationError, match="scope"):
            cast(
                "Any",
                NovelKBEntry.model_validate(
                    {**_common_fields(), "novel_id": uuid4(), "scope": "series"},
                ),
            )


# ---------------------------------------------------------------------------
# Discriminated union (KBEntry)
# ---------------------------------------------------------------------------


class TestKBEntryDiscriminatedUnion:
    """The ``scope`` field dispatches parsing to the concrete type."""

    def test_dispatch_series(self) -> None:
        adapter = TypeAdapter(KBEntry)
        entry = adapter.validate_python(
            {**_common_fields(), "scope": "series", "series_id": uuid4()},
        )
        assert isinstance(entry, SeriesKBEntry)
        assert entry.scope == "series"

    def test_dispatch_novel(self) -> None:
        adapter = TypeAdapter(KBEntry)
        entry = adapter.validate_python(
            {**_common_fields(), "scope": "novel", "novel_id": uuid4()},
        )
        assert isinstance(entry, NovelKBEntry)
        assert entry.scope == "novel"

    def test_dispatch_unknown_scope_rejected(self) -> None:
        """An unrecognised scope value is a validation error, not a fallback."""
        adapter = TypeAdapter(KBEntry)
        with pytest.raises(ValidationError, match="scope"):
            cast(
                "Any",
                adapter.validate_python(
                    {**_common_fields(), "scope": "global", "series_id": uuid4()},
                ),
            )

    def test_dispatch_missing_scope_rejected(self) -> None:
        """Without a discriminator, the union cannot resolve."""
        adapter = TypeAdapter(KBEntry)
        with pytest.raises(ValidationError, match="scope"):
            adapter.validate_python({**_common_fields(), "series_id": uuid4()})


# ---------------------------------------------------------------------------
# Forward-compat & public API
# ---------------------------------------------------------------------------


class TestEntryForwardCompatAndAPI:
    """extra='allow' and public re-exports."""

    def test_extra_fields_preserved(self) -> None:
        """Unknown fields survive validation (forward-compatibility)."""
        entry = cast(
            "Any",
            SeriesKBEntry.model_validate(
                {
                    **_common_fields(),
                    "series_id": uuid4(),
                    "future_field": "ok",
                    "numeric_extra": 42,
                },
            ),
        )
        assert entry.future_field == "ok"
        assert entry.numeric_extra == 42
        dumped = entry.model_dump()
        assert dumped["future_field"] == "ok"

    def test_model_config_extra_allow(self) -> None:
        assert SeriesKBEntry.model_config.get("extra") == "allow"
        assert NovelKBEntry.model_config.get("extra") == "allow"
        assert KBEntryBase.model_config.get("extra") == "allow"

    def test_subclasses_share_base(self) -> None:
        assert issubclass(SeriesKBEntry, KBEntryBase)
        assert issubclass(NovelKBEntry, KBEntryBase)

    def test_importable_from_schemas_package(self) -> None:
        """Backward/forward-compat: all four symbols re-exported."""
        from narrare_core.kb import schemas as kb_schemas

        assert kb_schemas.KBEntryBase is KBEntryBase
        assert kb_schemas.SeriesKBEntry is SeriesKBEntry
        assert kb_schemas.NovelKBEntry is NovelKBEntry
        assert kb_schemas.KBEntry is KBEntry
