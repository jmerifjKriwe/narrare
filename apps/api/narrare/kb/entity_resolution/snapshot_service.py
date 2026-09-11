"""Snapshot builder for the KB entity resolution layer (ADR-085 P3).

Maps one novel's KB entries and relationship adjacency into pure
:class:`EntitySnapshot` tuples for the deterministic resolution engine.
Dependency direction follows spec §2: this service consumes
``KBRepositoryProtocol`` and ``RelationshipRepositoryProtocol`` only —
no SQLAlchemy, no HTTP.

Scope decisions (spec §1/§3, review findings):

- Series-Canon rows (``novel_id IS NULL``) never enter the snapshot set:
  the novel-scoped ``find_overlay_for_novel`` fetch excludes them
  structurally.
- ``status='deprecated'`` entries are excluded here, in the builder —
  the engine never sees them (spec §3 model contract).
- Entries whose name is empty/whitespace are skipped (logged, RULE-11):
  an empty name normalizes to an exact S1 = 1.0 match against any other
  empty name and could poison the engine with a false EXACT tier.
- ``metadata["provenance"]`` is parsed tolerantly; malformed blocks
  degrade to ``provenance=None`` (= unknown — never negative). Chapter
  ranges are derived from the sorted ``chapters`` tuple, NOT from the
  stored first/last pair, which out-of-order endorsements can leave
  inconsistent (first > last).
- ``embedding`` is ``None`` in v1 — S5 stays 0 until the pgvector
  wiring lands; the engine tolerates unknown embeddings.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, TypeIs, cast
from uuid import UUID

import structlog

from narrare_core.kb.resolution.models import EntitySnapshot, EntryProvenance

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare_core.kb.schemas.entry import NovelKBEntry

logger = structlog.get_logger(__name__)


def _is_int(value: object) -> TypeIs[int]:
    """Strictly ``int`` (bools are ints in Python — exclude them)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_provenance(metadata: Mapping[str, object] | None) -> EntryProvenance | None:
    """Parse the reserved ``metadata["provenance"]`` block tolerantly.

    Any malformed shape degrades to ``None`` (= unknown): non-dict
    metadata, missing/non-dict ``provenance`` key, or a ``chapters``
    value that is absent, empty, not a list, or carries any non-int
    member (bool-excluded) — half-corrupted chapters must not yield
    half-trusted ranges (S2 is never computed from unknown provenance).
    ``first_seen_chapter``/``last_seen_chapter`` are derived from the
    deduplicated, sorted ``chapters`` tuple — the stored pair is ignored
    (out-of-order endorsements can leave first > last).

    ``name_variants`` is cosmetic: non-list or non-string members are
    dropped, but they never invalidate otherwise-known provenance.

    Args:
        metadata: The entry's stored metadata (may be ``None``).

    Returns:
        The parsed provenance, or ``None`` when unknown/invalid.
    """
    if not isinstance(metadata, Mapping):
        return None
    raw = metadata.get("provenance")
    if not isinstance(raw, dict):
        return None
    block = cast("dict[str, object]", raw)

    raw_chapters = block.get("chapters")
    if not isinstance(raw_chapters, list) or not all(
        _is_int(v) for v in cast("list[object]", raw_chapters)
    ):
        return None
    chapters = tuple(sorted({v for v in cast("list[object]", raw_chapters) if _is_int(v)}))
    if not chapters:
        return None

    raw_variants = block.get("name_variants")
    variants: tuple[str, ...] = ()
    if isinstance(raw_variants, list):
        variants = tuple(v for v in cast("list[object]", raw_variants) if isinstance(v, str))

    return EntryProvenance(
        chapters=chapters,
        first_seen_chapter=chapters[0],
        last_seen_chapter=chapters[-1],
        name_variants=variants,
    )


class SnapshotBuilder:
    """Builds ``EntitySnapshot`` tuples for one novel scope (P3).

    Implements :class:`~narrare.kb.entity_resolution.contracts.SnapshotBuilderProtocol`.
    Dependencies are injected (RULE-19): the KB entry repository
    (novel-wide overlay fetch) and the relationship repository (adjacency
    map with both edge directions merged).
    """

    def __init__(
        self,
        kb_repo: KBRepositoryProtocol,
        relationship_repo: RelationshipRepositoryProtocol,
    ) -> None:
        self._kb_repo = kb_repo
        self._relationship_repo = relationship_repo

    async def build(self, novel_id: UUID) -> tuple[EntitySnapshot, ...]:
        """Fetch entries + adjacency for ``novel_id`` and map to snapshots.

        Snapshots are ordered by ``entry_id`` so downstream consumers
        (analysis cache hashing, benchmark drivers) see a deterministic
        sequence regardless of DB result order.

        Args:
            novel_id: The novel scope to snapshot.

        Returns:
            An (possibly empty) immutable tuple of entity snapshots.
        """
        entries = await self._kb_repo.find_overlay_for_novel(novel_id)
        adjacency = await self._relationship_repo.get_adjacency_map(novel_id)

        snapshots: list[EntitySnapshot] = []
        for entry in entries:
            if entry.status == "deprecated":
                logger.debug(
                    "snapshot_builder_excluded_deprecated",
                    entry_id=str(entry.id),
                    novel_id=str(novel_id),
                )
                continue
            if not entry.name.strip():
                logger.warning(
                    "snapshot_builder_skipped_empty_name",
                    entry_id=str(entry.id),
                    novel_id=str(novel_id),
                )
                continue
            snapshots.append(self._to_snapshot(entry, adjacency))
        return tuple(sorted(snapshots, key=lambda s: s.entry_id))

    def _to_snapshot(
        self,
        entry: NovelKBEntry,
        adjacency: Mapping[str, set[str]],
    ) -> EntitySnapshot:
        """Map one novel-scoped entry to its pure snapshot."""
        neighbors = adjacency.get(str(entry.id), set())
        return EntitySnapshot(
            entry_id=entry.id,
            name=entry.name,
            entity_type=entry.entity_type,
            status=entry.status,
            metadata=dict(entry.metadata_ or {}),
            provenance=_parse_provenance(entry.metadata_),
            neighbor_ids=frozenset(UUID(n) for n in neighbors),
            embedding=None,  # v1: pgvector wiring lands later; S5 stays 0
        )
