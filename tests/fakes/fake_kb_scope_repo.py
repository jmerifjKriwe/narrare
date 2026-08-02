"""In-memory fake for the KB scope surface with REAL Canon-integrity (D4) logic.

Companion to :class:`~tests.fakes.fake_kb_join_repo.FakeJoinKBRepo`, which
fakes only the three ``SeriesJoinService`` methods. The D4 regression
(:mod:`tests.unit.api.kb.test_scope_demote_d4_regression`) needs a fake that
actually evaluates the Canon-integrity guard — a stubbed ``ConflictError``
would only prove the service propagates the error, not that the contract is
triggered by the right state.

The D4 rule (mirroring :meth:`KBScopeRepository._count_relying_novels`):

    A novel "relies on" the Canon entry when it is a member of the series
    but has NO own Overlay with the same slug. Demoting to ``target_novel_id``
    would silently drop the Canon entry from such a novel's merged view.

This fake expresses that in pure Python (sets over the seeded state) so the
behaviour is obviously correct and a deviation in the real repository's SQL
cannot silently agree with a wrong fake.

Stores entries internally as mutable ``_EntryRecord``s and exposes the
``KBScopeMutationProtocol`` surface (``promote_to_canon`` /
``demote_to_overlay``) plus the ``find_canon_for_series`` /
``find_overlay_for_novel`` readers so tests can seed and assert directly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry
from narrare_core.shared.errors import ConflictError
from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass
class _EntryRecord:
    """Mutable internal KB row — mirrors the columns the D4 logic needs.

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


@dataclass
class FakeScopeKBRepo:
    """Real in-memory fake for ``KBScopeMutationProtocol`` with D4 enforcement.

    The Canon-integrity guard is computed from seeded ``_EntryRecord`` state
    plus the seeded series membership (``seed_series_members``) — the same two
    facts the real SQL query joins over.
    """

    _entries: dict[uuid.UUID, _EntryRecord] = field(default_factory=dict)
    _series_members: dict[uuid.UUID, set[uuid.UUID]] = field(default_factory=dict)
    calls: list[CallRecord] = field(default_factory=list)
    # Per-method call logs (mirrors ``_scope_service_helpers.FakeKBRepo``'s
    # convention) so tests can assert delegation without filtering ``calls``.
    promote_calls: list[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=list)
    demote_calls: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = field(default_factory=list)

    # -- seeders --------------------------------------------------------

    def seed_entry(
        self,
        *,
        slug: str,
        entity_type: str = "system",
        name: str = "Test Entry",
        entry_id: uuid.UUID | None = None,
        novel_id: uuid.UUID | None = None,
        series_id: uuid.UUID | None = None,
    ) -> _EntryRecord:
        """Seed one KB row. Canon if ``novel_id`` is None + ``series_id`` set."""
        record = _EntryRecord(
            id=entry_id or uuid.uuid4(),
            slug=slug,
            entity_type=entity_type,
            name=name,
            novel_id=novel_id,
            series_id=series_id,
        )
        self._entries[record.id] = record
        return record

    def seed_series_members(self, series_id: uuid.UUID, novel_ids: Iterable[uuid.UUID]) -> None:
        """Declare which novels are members of a series (D4 input)."""
        self._series_members[series_id] = set(novel_ids)

    # -- readers --------------------------------------------------------

    async def find_canon_for_series(self, series_id: uuid.UUID) -> list[SeriesKBEntry]:
        self.calls.append(CallRecord("find_canon_for_series", kwargs={"series_id": series_id}))
        return [
            self._to_series_entry(r)
            for r in self._entries.values()
            if r.is_canon and r.series_id == series_id
        ]

    async def find_overlay_for_novel(self, novel_id: uuid.UUID) -> list[NovelKBEntry]:
        self.calls.append(CallRecord("find_overlay_for_novel", kwargs={"novel_id": novel_id}))
        return [
            self._to_novel_entry(r)
            for r in self._entries.values()
            if r.is_overlay and r.novel_id == novel_id
        ]

    # -- KBScopeMutationProtocol surface --------------------------------

    async def promote_to_canon(self, novel_id: uuid.UUID, entry_id: uuid.UUID) -> SeriesKBEntry:
        """Move an overlay entry to Canon (its novel's series)."""
        self.calls.append(
            CallRecord("promote_to_canon", kwargs={"novel_id": novel_id, "entry_id": entry_id})
        )
        self.promote_calls.append((novel_id, entry_id))
        record = self._entries.get(entry_id)
        if record is None or not record.is_overlay:
            raise ConflictError(f"Entry {entry_id} is not an overlay of novel {novel_id}")
        # Look up the novel's series from the seeded membership (reverse map).
        series_id = next(
            (sid for sid, members in self._series_members.items() if novel_id in members),
            None,
        )
        if series_id is None:
            raise ConflictError(f"Novel {novel_id} is not in a series")
        record.novel_id = None
        record.series_id = series_id
        return self._to_series_entry(record)

    async def demote_to_overlay(
        self,
        series_id: uuid.UUID,
        entry_id: uuid.UUID,
        target_novel_id: uuid.UUID,
    ) -> NovelKBEntry:
        """Demote Canon to Overlay for ``target_novel_id`` (with the D4 guard).

        Raises:
            ConflictError: entry is missing / not canon of ``series_id``
                (scope invariant), OR another member novel relies on this
                Canon entry (D4 Canon-integrity guard, HTTP 409).
        """
        self.calls.append(
            CallRecord(
                "demote_to_overlay",
                kwargs={
                    "series_id": series_id,
                    "entry_id": entry_id,
                    "target_novel_id": target_novel_id,
                },
            )
        )
        self.demote_calls.append((series_id, entry_id, target_novel_id))
        record = self._entries.get(entry_id)
        if record is None or record.series_id != series_id or not record.is_canon:
            raise ConflictError(f"Entry {entry_id} is not a Canon entry of series {series_id}")

        relying = self._count_relying_novels(series_id, record.slug, target_novel_id)
        if relying > 0:
            raise ConflictError(
                f"Cannot demote Canon entry '{record.slug}': {relying} other member "
                f"novel(s) rely on it and would lose it from their merged view"
            )

        record.series_id = None  # D6: overlays never persist series_id.
        record.novel_id = target_novel_id
        return self._to_novel_entry(record)

    # -- D4 logic (pure-Python mirror of the SQL) -----------------------

    def _count_relying_novels(
        self, series_id: uuid.UUID, slug: str, target_novel_id: uuid.UUID
    ) -> int:
        """Count member novels of ``series_id`` that rely on a Canon ``slug``.

        A novel "relies on" the Canon when it is a member of the series but
        has NO own Overlay with the same slug. The target novel (which
        receives the demoted entry) is excluded. Mirrors
        :meth:`KBScopeRepository._count_relying_novels` line for line.
        """
        members = self._series_members.get(series_id, set())
        members_excluding_target = members - {target_novel_id}
        covered = {
            r.novel_id
            for r in self._entries.values()
            if r.is_overlay and r.slug == slug and r.novel_id in members
        }
        relying = members_excluding_target - covered
        return len(relying)

    # -- Core type converters ------------------------------------------

    @staticmethod
    def _to_series_entry(record: _EntryRecord) -> SeriesKBEntry:
        assert record.series_id is not None  # Canon invariant.
        return SeriesKBEntry(
            id=record.id,
            entity_type=record.entity_type,
            name=record.name,
            slug=record.slug,
            series_id=record.series_id,
        )

    @staticmethod
    def _to_novel_entry(record: _EntryRecord) -> NovelKBEntry:
        assert record.novel_id is not None  # Overlay invariant.
        return NovelKBEntry(
            id=record.id,
            entity_type=record.entity_type,
            name=record.name,
            slug=record.slug,
            novel_id=record.novel_id,
        )
