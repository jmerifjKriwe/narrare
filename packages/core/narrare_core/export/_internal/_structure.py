"""Assemble per-chapter metadata in position order.

The normalizer is Pure Core (RULE-05: no DB access), so it cannot derive
chapter metadata itself. Per-chapter DB data (UUIDs, position, volume) is
handed in via ``ManuscriptMetadata.chapters`` by the Backend (RULE-22
read-only fetch). This module only enforces the contract's "in position order"
output guarantee — a defensive, stable sort on ``ChapterMeta.position``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.export.contracts import ChapterMeta


def order_chapters(chapters: list[ChapterMeta]) -> list[ChapterMeta]:
    """Return chapters sorted by ``position``.

    Python's ``sorted`` is stable, so chapters sharing a position preserve
    their input order. This is a pure, deterministic defensive sort — the
    Backend already supplies chapters ordered by position, but sorting here
    makes the output guarantee self-enforcing regardless of caller.
    """
    return sorted(chapters, key=lambda chapter: chapter.position)
