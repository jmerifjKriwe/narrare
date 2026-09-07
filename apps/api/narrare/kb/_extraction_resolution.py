"""Entity resolution for the extraction apply flow (KB-007).

Pure decision helpers used by ``ExtractionApplyService``:

- ``resolve_update_target``: resolve an ``update_entity`` item to a target
  KB entry (validated ``target_entity_id`` → novel-scope check → exact-name
  fallback) and decide whether the item's ``name`` constitutes a rename
  worth persisting.
- ``merge_metadata``: compose an ``update_entity`` item's
  ``proposed_content`` over the entry's existing metadata (merge-not-clobber:
  proposed keys overwrite, keys the item omits survive).

Relationship endpoint resolution (``resolve_relationship_endpoints``,
including in-batch creation lookup) lives in
:mod:`narrare.kb._extraction_endpoint_resolution` — split for RULE-04
compliance when in-batch resolution (benchmark run 5) grew this file
past its size limit.

Extracted from ``extraction_apply_service.py`` for RULE-04 compliance (the
apply service sits at the 300-line limit). All guards are blocking-only:
they may skip an item, never synthesize a merge — wrong-name unification
(e.g. "Anna Meyer" vs "Anna Meier") is prevented semantically by the
extraction prompt's distractor guard, not by lexical heuristics here.

See:
    :class:`narrare.kb.extraction_apply_service.ExtractionApplyService`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy.exc import MultipleResultsFound

if TYPE_CHECKING:
    import uuid

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.models import KBEntry
    from narrare.kb.schemas_extraction import ApplyExtractionItem

logger = structlog.get_logger(__name__)

RESERVED_METADATA_KEYS: frozenset[str] = frozenset({"provenance", "resolution"})
"""Metadata keys owned by the platform, never by LLM proposals.

``provenance`` is maintained exclusively by the apply flow (ADR-085 §5);
``resolution`` is reserved for the merge executor (ADR-085 §6). Both are
stripped from ``proposed_content`` before any composition so proposals
can never forge or clobber them.
"""


@dataclass(frozen=True)
class ResolutionDecision:
    """Outcome of resolving an ``update_entity`` item to a KB entry."""

    target_id: uuid.UUID
    """Validated ID of the KB entry to update."""

    rename_to: str | None
    """New name to persist, or ``None`` when the item does not rename."""

    merged_metadata: dict[str, object] | None
    """Existing entry metadata composed with the item's ``proposed_content``
    (merge-not-clobber), or ``None`` when the item proposes no metadata
    (leave the stored metadata untouched)."""

    existing_metadata: dict[str, object] | None = None
    """Copy of the target entry's stored metadata before composition.

    The apply flow needs the pre-merge state to advance the reserved
    ``provenance`` block even when the item proposes no metadata —
    rebuilding from storage avoids clobbering existing keys.
    """


async def resolve_update_target(
    item: ApplyExtractionItem,
    kb_repo: KBRepositoryProtocol,
    novel_id: uuid.UUID,
) -> ResolutionDecision | None:
    """Resolve an ``update_entity`` item to a target entry + rename decision.

    Resolution order: the validated ``target_entity_id`` (must exist and
    belong to the novel), else an exact-name lookup within the novel.
    Every failure mode logs a distinct warning and yields ``None`` — the
    caller skips the item (RULE-11 per-item isolation, never a crash).

    Guards (blocking-only): entity-type mismatch between item and entry,
    ambiguous names (multiple matches), and out-of-novel targets all
    resolve to ``None``.

    Args:
        item: The endorsed extraction item.
        kb_repo: KB repository (novel-scoped lookups).
        novel_id: Novel whose KB is the resolution scope.

    Returns:
        A :class:`ResolutionDecision`, or ``None`` when the item cannot be
        resolved unambiguously.
    """
    entry = await _find_candidate(item, kb_repo, novel_id)
    if entry is None:
        return None
    return ResolutionDecision(
        target_id=entry.id,
        rename_to=decide_rename(current_name=entry.name, proposed_name=item.name),
        merged_metadata=merge_metadata(
            entry.metadata_,
            strip_reserved_keys(item.proposed_content),
        ),
        existing_metadata=dict(entry.metadata_) if entry.metadata_ else None,
    )


def strip_reserved_keys(
    proposed: dict[str, object] | None,
) -> dict[str, object] | None:
    """Drop platform-reserved metadata keys from an LLM proposal.

    Every ``proposed_content`` consumption site (merge composition AND the
    create path) must route through this guard: proposals are model output
    and can never own ``provenance``/``resolution`` (ADR-085 §5). Returns a
    shallow copy — the caller's dict is never mutated. ``None``/empty
    proposals pass through unchanged.

    Args:
        proposed: The item's ``proposed_content`` (may be ``None``/empty).

    Returns:
        A copy without reserved keys, or the input when ``None``/empty.
    """
    if not proposed:
        return proposed
    return {key: value for key, value in proposed.items() if key not in RESERVED_METADATA_KEYS}


async def _find_candidate(
    item: ApplyExtractionItem,
    kb_repo: KBRepositoryProtocol,
    novel_id: uuid.UUID,
) -> KBEntry | None:
    """Find the candidate entry: by validated ID, else by exact name."""
    if item.target_entity_id:
        return await _candidate_by_id(item, kb_repo, novel_id)
    return await _candidate_by_name(item, kb_repo, novel_id)


async def _candidate_by_id(
    item: ApplyExtractionItem,
    kb_repo: KBRepositoryProtocol,
    novel_id: uuid.UUID,
) -> KBEntry | None:
    """Resolve the target via ``target_entity_id`` with hard validation."""
    assert item.target_entity_id is not None
    try:
        entry_id = UUID(item.target_entity_id)
    except ValueError:
        logger.warning(
            "update_entity_invalid_target_id",
            name=item.name,
            target_entity_id=item.target_entity_id,
        )
        return None

    entry = await kb_repo.get_by_id(entry_id)
    if entry is None:
        logger.warning(
            "update_entity_target_not_found",
            name=item.name,
            target_entity_id=item.target_entity_id,
        )
        return None
    if entry.novel_id != novel_id:
        logger.warning(
            "update_entity_target_out_of_novel_scope",
            name=item.name,
            entry_id=str(entry.id),
            novel_id=str(novel_id),
        )
        return None
    if not _types_match(item.entity_type, entry.entity_type):
        logger.warning(
            "update_entity_type_mismatch",
            name=item.name,
            item_type=item.entity_type,
            entry_type=entry.entity_type,
            entry_id=str(entry.id),
        )
        return None
    return entry


async def _candidate_by_name(
    item: ApplyExtractionItem,
    kb_repo: KBRepositoryProtocol,
    novel_id: uuid.UUID,
) -> KBEntry | None:
    """Resolve the target via exact-name lookup (repair path, no ID).

    The lookup is novel-scoped inside the repository. Ambiguous names
    (several matches) are treated as unresolvable — never a silent pick.
    """
    try:
        entry = await kb_repo.get_by_name(novel_id, item.name)
    except MultipleResultsFound:
        logger.warning("update_entity_ambiguous_name", name=item.name)
        return None
    except Exception as exc:
        logger.warning(
            "update_entity_name_lookup_failed",
            name=item.name,
            error=str(exc),
        )
        return None

    if entry is None:
        logger.warning(
            "update_entity_name_not_found",
            name=item.name,
            novel_id=str(novel_id),
        )
        return None
    if not _types_match(item.entity_type, entry.entity_type):
        logger.warning(
            "update_entity_type_mismatch",
            name=item.name,
            item_type=item.entity_type,
            entry_type=entry.entity_type,
            entry_id=str(entry.id),
        )
        return None
    return entry


def _types_match(item_type: str | None, entry_type: str) -> bool:
    """An item without a type claim matches; diverging types never match."""
    return item_type is None or item_type == entry_type


def decide_rename(current_name: str, proposed_name: str) -> str | None:
    """Decide whether a proposed name is a rename worth persisting.

    Returns ``None`` (keep the current name) when the proposal is empty,
    only differs in case/whitespace, or is a strict substring of the
    current name — the downgrade guard keeps the fuller canonical name
    ("Anna" ⊂ "Anna Meyer" → keep "Anna Meyer"). A guard that only blocks
    renames cannot cause a wrong merge. Otherwise the proposed name is
    returned for persistence via ``KBEntryUpdate.name``.
    """
    current = (current_name or "").strip()
    proposed = (proposed_name or "").strip()
    if not proposed or not current:
        return None
    if proposed.casefold() == current.casefold():
        return None
    current_cf = current.casefold()
    proposed_cf = proposed.casefold()
    if len(proposed_cf) < len(current_cf) and proposed_cf in current_cf:
        logger.info(
            "update_entity_rename_downgrade_blocked",
            current=current,
            proposed=proposed,
        )
        return None
    return proposed


def merge_metadata(
    existing: dict[str, object] | None,
    proposed: dict[str, object] | None,
) -> dict[str, object] | None:
    """Compose ``proposed_content`` over existing metadata (no clobber).

    Extraction updates are partial observations: a later chapter reports
    only what it saw, so replacing the stored metadata would erase earlier
    chapters' keys (the diagnosed clobber bug). Proposed keys overwrite;
    keys the item does not mention survive. A ``None``/empty proposal
    yields ``None`` so the caller leaves the stored metadata untouched
    (PATCH semantics — an unset field is not an overwrite).

    Mirrors the merge semantics already used by the KB improve path
    (:mod:`narrare.kb.improve_service`). Validation of the merged dict
    against the entity type stays with ``build_entry_updates`` (single
    responsibility).

    Args:
        existing: The entry's stored metadata (may be ``None``).
        proposed: The item's ``proposed_content`` (may be ``None``/empty).

    Returns:
        The merged metadata dict, or ``None`` when there is nothing to
        persist.
    """
    if not proposed:
        return None
    merged: dict[str, object] = dict(existing or {})
    merged.update(proposed)
    return merged
