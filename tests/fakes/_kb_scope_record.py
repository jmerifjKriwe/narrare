"""Internal storage + ORM→Core mapping for FakeScopeKBRepo (RULE-04 split).

Extracted from :mod:`tests.fakes.fake_kb_scope_repo` to keep that file under
the RULE-04 250-line ``*_repo.py`` limit once the partial-index enforcement
helpers landed. Holds the mutable :class:`EntryRecord` (the columns the D4 /
collision logic needs) and the two pure record→Core converters, which are
independent of the fake's protocol surface.

These names are the module's public test API (no leading underscore on the
class) so cross-module imports don't trip pyright's ``reportPrivateUsage``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry

if TYPE_CHECKING:
    import uuid


@dataclass
class EntryRecord:
    """Mutable internal KB row — mirrors the columns the D4 / collision logic needs.

    The full ``KBEntry`` ORM has ~20 columns; only the scope-discriminating
    ones (``novel_id`` / ``series_id`` / ``slug`` / ``entity_type``) and
    ``name`` (returned on the Core types) participate in the D4 contract.
    """

    id: uuid.UUID
    slug: str
    entity_type: str
    name: str
    novel_id: uuid.UUID | None = None
    series_id: uuid.UUID | None = None

    @property
    def is_canon(self) -> bool:
        return self.novel_id is None and self.series_id is not None

    @property
    def is_overlay(self) -> bool:
        return self.novel_id is not None


def to_series_entry(record: EntryRecord) -> SeriesKBEntry:
    """Map an internal Canon record to the Core ``SeriesKBEntry`` value object."""
    assert record.series_id is not None  # Canon invariant.
    return SeriesKBEntry(
        id=record.id,
        entity_type=record.entity_type,
        name=record.name,
        slug=record.slug,
        series_id=record.series_id,
    )


def to_novel_entry(record: EntryRecord) -> NovelKBEntry:
    """Map an internal Overlay record to the Core ``NovelKBEntry`` value object."""
    assert record.novel_id is not None  # Overlay invariant.
    return NovelKBEntry(
        id=record.id,
        entity_type=record.entity_type,
        name=record.name,
        slug=record.slug,
        novel_id=record.novel_id,
    )
