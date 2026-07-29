"""KBEntry Single-Table-Inheritance (STI) types.

Schema 2A+STI: a single physical ``kb_entries`` table with discriminated
Pydantic types at the Core layer.

    scope="series" → SeriesKBEntry  (novel_id IS NULL — Canon for the series)
    scope="novel"  → NovelKBEntry   (novel_id IS NOT NULL — Overlay in one novel)

The physical scope invariant lives in the ``ck_kb_entries_scope_invariant``
CHECK constraint (Alembic 0037):

    (novel_id IS NULL AND series_id IS NOT NULL AND base_entry_id IS NULL)
    OR (novel_id IS NOT NULL)

These Pydantic types mirror that invariant at the type level so callers get
compile-time safety: a Series-Canon entry cannot carry a ``novel_id`` or
``base_entry_id``, and a Novel-Overlay entry must carry a ``novel_id``.

``scope`` is a *virtual* Core-layer discriminator — there is no physical
``scope`` column. A future mapper (Slice 2) derives ``scope`` from
``novel_id IS NULL`` when hydrating ORM rows into these types.

This module contains Pydantic types only (RULE-06: one responsibility per file).
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — needed at runtime for Pydantic
from typing import Annotated, Literal
from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic

from pydantic import BaseModel, ConfigDict, Field


class KBEntryBase(BaseModel):
    """Common fields for all KB entries (Series-Canon + Novel-Overlay).

    Holds the shared physical ``kb_entries`` columns. The three scope columns
    (``series_id`` / ``novel_id`` / ``base_entry_id``) are constrained per
    subclass to mirror the ``ck_kb_entries_scope_invariant`` DB CHECK.

    The ``scope`` discriminator is intentionally NOT declared here: pyright
    rejects narrowing a mutable base field (variance), and the codebase's
    established discriminated-union pattern (see ``writing/requests.py``'
    ``ReattachOutcome``) keeps the discriminator on each concrete leaf only.
    Each subclass pins ``scope`` to a single Literal value, which is what the
    ``KBEntry`` union dispatches on.
    """

    model_config = ConfigDict(extra="allow")

    id: UUID
    entity_type: str
    name: str
    slug: str
    status: str = "draft"
    body: str | None = None
    metadata_: dict[str, object] | None = None
    tags: list[str] | None = None
    template_version: str | None = None
    source: str = "manual"
    review_status: str = "approved"
    embeddings_dirty: bool = False
    last_referenced_at: datetime | None = None
    usage_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SeriesKBEntry(KBEntryBase):
    """Series-Canon KB entry — shared across all novels in the series.

    DB invariant (ck_kb_entries_scope_invariant):
        novel_id IS NULL, series_id IS NOT NULL, base_entry_id IS NULL.
    """

    scope: Literal["series"] = "series"
    series_id: UUID
    novel_id: None = None
    base_entry_id: None = None


class NovelKBEntry(KBEntryBase):
    """Novel-Overlay KB entry — valid in one specific novel.

    DB invariant (ck_kb_entries_scope_invariant):
        novel_id IS NOT NULL. series_id / base_entry_id are optional links
        back to the series and the Canon entry this overlay modifies.
    """

    scope: Literal["novel"] = "novel"
    novel_id: UUID
    series_id: UUID | None = None
    base_entry_id: UUID | None = None


# Discriminated union: ``scope`` selects the concrete type at parse time.
KBEntry = Annotated[SeriesKBEntry | NovelKBEntry, Field(discriminator="scope")]
