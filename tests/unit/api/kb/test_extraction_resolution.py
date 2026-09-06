"""Unit tests for entity resolution in the extraction apply flow (KB-007).

Covers the target resolution + rename decision used by
``ExtractionApplyService._apply_update_entity`` (implemented in
``narrare.kb._extraction_resolution``):

Scenarios (RULE-20):
- decide_rename (pure): canonical upgrade allowed; downgrade (strict
  substring) blocked; case-only difference is a no-op; disjoint rename
  allowed; empty proposal → None
- resolve_update_target: validated-ID path (novel-scoped, type-guarded),
  exact-name fallback path, and all blocking guards (invalid UUID,
  unknown ID, cross-novel target, type mismatch, ambiguous name,
  name not found)
- merge_metadata (pure): proposed keys overwrite, unmentioned keys
  survive; empty/None proposal → None; existing dict never mutated
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import MultipleResultsFound

from narrare.kb._extraction_resolution import (
    decide_rename,
    merge_metadata,
    resolve_update_target,
)
from narrare.kb.schemas_extraction import ApplyExtractionItem

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol


# ---------------------------------------------------------------------------
# Fakes (RULE-TEST-01 — real fakes, no behaviorless MagicMock)
# ---------------------------------------------------------------------------


class _FakeEntry:
    """Minimal fake KB entry with the attributes resolution reads."""

    def __init__(
        self,
        name: str,
        entity_type: str = "character",
        novel_id: UUID | None = None,
        entry_id: UUID | None = None,
        metadata_: dict[str, object] | None = None,
    ) -> None:
        self.id = entry_id or uuid4()
        self.name = name
        self.entity_type = entity_type
        self.novel_id = novel_id
        self.metadata_ = metadata_


class _ResolutionKBRepo:
    """Fake KBRepositoryProtocol — ID + name lookups over a seeded list."""

    def __init__(self) -> None:
        self.entries: list[_FakeEntry] = []
        self.get_by_name_error: Exception | None = None

    def seed(self, entry: _FakeEntry) -> _FakeEntry:
        self.entries.append(entry)
        return entry

    async def get_by_id(self, entry_id: UUID) -> _FakeEntry | None:
        return next((e for e in self.entries if e.id == entry_id), None)

    async def get_by_name(self, novel_id: UUID, name: str) -> _FakeEntry | None:
        if self.get_by_name_error is not None:
            raise self.get_by_name_error
        return next(
            (e for e in self.entries if e.name.casefold() == name.casefold()),
            None,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item(
    name: str = "Anna Meyer",
    entity_type: str | None = "character",
    target_entity_id: str | None = None,
    proposed_content: dict[str, object] | None = None,
) -> ApplyExtractionItem:
    return ApplyExtractionItem(
        item_type="update_entity",
        name=name,
        entity_type=entity_type,
        target_entity_id=target_entity_id,
        proposed_content=proposed_content,
        source_text="test source",
    )


# ---------------------------------------------------------------------------
# decide_rename — pure downgrade-guarded rename decision
# ---------------------------------------------------------------------------


def test_decide_rename_allows_canonical_upgrade() -> None:
    """A fuller name (current ⊂ proposed) is persisted as rename."""
    assert decide_rename("Anna", "Anna Meyer") == "Anna Meyer"


def test_decide_rename_blocks_downgrade_substring() -> None:
    """A strict substring of the current name is blocked (downgrade guard)."""
    assert decide_rename("Anna Meyer", "Anna") is None


def test_decide_rename_ignores_case_only_difference() -> None:
    """A case-only difference is a no-op, not a rename."""
    assert decide_rename("Anna", "anna") is None


def test_decide_rename_strips_whitespace_before_compare() -> None:
    """Surrounding whitespace is stripped on both sides before comparing."""
    assert decide_rename("  Anna ", "  Anna Meyer ") == "Anna Meyer"


def test_decide_rename_allows_disjoint_rename() -> None:
    """A disjoint (non-substring) new name is persisted as rename."""
    assert decide_rename("Anna", "Anna-Lena") == "Anna-Lena"


def test_decide_rename_returns_none_for_empty_proposed() -> None:
    """An empty/whitespace proposal never renames."""
    assert decide_rename("Anna", "") is None
    assert decide_rename("Anna", "   ") is None


def test_decide_rename_returns_none_for_empty_current() -> None:
    """An empty current name never renames."""
    assert decide_rename("", "Anna Meyer") is None


# ---------------------------------------------------------------------------
# resolve_update_target — validated-ID path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_by_valid_id_returns_target_and_rename() -> None:
    """A valid in-novel target ID resolves; a fuller name becomes a rename."""
    novel_id = uuid4()
    repo = _ResolutionKBRepo()
    entry = repo.seed(_FakeEntry(name="Anna", novel_id=novel_id))
    decision = await resolve_update_target(
        _item(name="Anna Meyer", target_entity_id=str(entry.id)),
        cast("KBRepositoryProtocol", repo),
        novel_id,
    )
    assert decision is not None
    assert decision.target_id == entry.id
    assert decision.rename_to == "Anna Meyer"


@pytest.mark.asyncio
async def test_resolve_by_valid_id_without_rename() -> None:
    """A matching name resolves the target without proposing a rename."""
    novel_id = uuid4()
    repo = _ResolutionKBRepo()
    entry = repo.seed(_FakeEntry(name="Anna Meyer", novel_id=novel_id))
    decision = await resolve_update_target(
        _item(name="Anna Meyer", target_entity_id=str(entry.id)),
        cast("KBRepositoryProtocol", repo),
        novel_id,
    )
    assert decision is not None
    assert decision.target_id == entry.id
    assert decision.rename_to is None


@pytest.mark.asyncio
async def test_resolve_rejects_invalid_target_uuid() -> None:
    """A non-UUID target_entity_id resolves to None (logged skip)."""
    repo = _ResolutionKBRepo()
    decision = await resolve_update_target(
        _item(name="Anna", target_entity_id="not-a-uuid"),
        cast("KBRepositoryProtocol", repo),
        uuid4(),
    )
    assert decision is None


@pytest.mark.asyncio
async def test_resolve_rejects_unknown_target_id() -> None:
    """A well-formed ID that does not exist resolves to None."""
    repo = _ResolutionKBRepo()
    decision = await resolve_update_target(
        _item(name="Anna", target_entity_id=str(uuid4())),
        cast("KBRepositoryProtocol", repo),
        uuid4(),
    )
    assert decision is None


@pytest.mark.asyncio
async def test_resolve_rejects_cross_novel_target_id() -> None:
    """An ID belonging to a different novel is rejected (scope guard)."""
    repo = _ResolutionKBRepo()
    entry = repo.seed(_FakeEntry(name="Anna", novel_id=uuid4()))
    decision = await resolve_update_target(
        _item(name="Anna Meyer", target_entity_id=str(entry.id)),
        cast("KBRepositoryProtocol", repo),
        uuid4(),
    )
    assert decision is None


@pytest.mark.asyncio
async def test_resolve_rejects_type_mismatch_on_id_path() -> None:
    """Item entity_type ≠ entry entity_type blocks the ID path."""
    novel_id = uuid4()
    repo = _ResolutionKBRepo()
    entry = repo.seed(_FakeEntry(name="Anna", entity_type="character", novel_id=novel_id))
    decision = await resolve_update_target(
        _item(name="Anna Meyer", entity_type="location", target_entity_id=str(entry.id)),
        cast("KBRepositoryProtocol", repo),
        novel_id,
    )
    assert decision is None


# ---------------------------------------------------------------------------
# resolve_update_target — exact-name fallback path (no target ID)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_falls_back_to_exact_name() -> None:
    """Without target ID, an exact (case-insensitive) name match resolves."""
    novel_id = uuid4()
    repo = _ResolutionKBRepo()
    entry = repo.seed(_FakeEntry(name="Anna", novel_id=novel_id))
    decision = await resolve_update_target(
        _item(name="anna", target_entity_id=None),
        cast("KBRepositoryProtocol", repo),
        novel_id,
    )
    assert decision is not None
    assert decision.target_id == entry.id
    assert decision.rename_to is None  # name matches → no rename


@pytest.mark.asyncio
async def test_resolve_fallback_rejects_type_mismatch() -> None:
    """Item entity_type ≠ entry entity_type blocks the fallback path too."""
    novel_id = uuid4()
    repo = _ResolutionKBRepo()
    repo.seed(_FakeEntry(name="Anna", entity_type="location", novel_id=novel_id))
    decision = await resolve_update_target(
        _item(name="Anna", entity_type="character", target_entity_id=None),
        cast("KBRepositoryProtocol", repo),
        novel_id,
    )
    assert decision is None


@pytest.mark.asyncio
async def test_resolve_fallback_name_not_found_returns_none() -> None:
    """A name with no KB match resolves to None (distractor names skip)."""
    novel_id = uuid4()
    repo = _ResolutionKBRepo()
    repo.seed(_FakeEntry(name="Anna", novel_id=novel_id))
    decision = await resolve_update_target(
        _item(name="Anna Meier", target_entity_id=None),
        cast("KBRepositoryProtocol", repo),
        novel_id,
    )
    assert decision is None


@pytest.mark.asyncio
async def test_resolve_fallback_ambiguous_name_returns_none() -> None:
    """Multiple name matches (MultipleResultsFound) resolve to None."""
    novel_id = uuid4()
    repo = _ResolutionKBRepo()
    repo.get_by_name_error = MultipleResultsFound("multiple rows matched")
    decision = await resolve_update_target(
        _item(name="Anna", target_entity_id=None),
        cast("KBRepositoryProtocol", repo),
        novel_id,
    )
    assert decision is None


@pytest.mark.asyncio
async def test_resolve_fallback_lookup_failure_returns_none() -> None:
    """A repository failure on the fallback path is a logged skip, not a crash."""
    novel_id = uuid4()
    repo = _ResolutionKBRepo()
    repo.get_by_name_error = RuntimeError("DB connection lost")
    decision = await resolve_update_target(
        _item(name="Anna", target_entity_id=None),
        cast("KBRepositoryProtocol", repo),
        novel_id,
    )
    assert decision is None


# ---------------------------------------------------------------------------
# merge_metadata — pure merge-not-clobber composition
# ---------------------------------------------------------------------------


def test_merge_metadata_overwrites_proposed_and_preserves_rest() -> None:
    """Proposed keys overwrite; keys the item omits survive."""
    existing: dict[str, object] = {"age": "24", "profession": "student"}
    assert merge_metadata(existing, {"profession": "architect"}) == {
        "age": "24",
        "profession": "architect",
    }


def test_merge_metadata_without_proposal_returns_none() -> None:
    """A None/empty proposal yields None (leave stored metadata untouched)."""
    assert merge_metadata({"age": "24"}, None) is None
    assert merge_metadata({"age": "24"}, {}) is None


def test_merge_metadata_with_empty_existing_copies_proposal() -> None:
    """An entry without stored metadata adopts the proposal as-is."""
    assert merge_metadata(None, {"role": "protagonist"}) == {"role": "protagonist"}


def test_merge_metadata_does_not_mutate_existing() -> None:
    """The existing metadata dict is copied, never mutated in place."""
    existing: dict[str, object] = {"age": "24"}
    merged = merge_metadata(existing, {"profession": "architect"})
    assert merged == {"age": "24", "profession": "architect"}
    assert existing == {"age": "24"}


@pytest.mark.asyncio
async def test_resolve_decision_carries_merged_metadata() -> None:
    """The decision composes proposed_content over the entry's metadata."""
    novel_id = uuid4()
    repo = _ResolutionKBRepo()
    entry = repo.seed(
        _FakeEntry(
            name="Anna",
            novel_id=novel_id,
            metadata_={"age": "24", "profession": "student"},
        )
    )
    decision = await resolve_update_target(
        _item(
            name="Anna",
            target_entity_id=str(entry.id),
            proposed_content={"profession": "architect"},
        ),
        cast("KBRepositoryProtocol", repo),
        novel_id,
    )
    assert decision is not None
    assert decision.merged_metadata == {"age": "24", "profession": "architect"}
