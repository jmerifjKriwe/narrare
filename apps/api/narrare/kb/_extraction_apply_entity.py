"""Entity application for the extraction apply flow (KB-007).

Applies ``new_entity`` and ``update_entity`` extraction items: creates a
KB entry via ``KBService``, or resolves an update target via
:mod:`narrare.kb._extraction_resolution` and updates the entry
(downgrade-guarded rename, merge-not-clobber metadata). Split from
``extraction_apply_service.py`` for RULE-04 compliance when per-item
SAVEPOINT wiring (benchmark run 5 batch-robustness fix) pushed the apply
service over the 300-line limit — mirroring the existing
``_extraction_apply_relationship`` split.

Unapplied items return a stable machine-readable skip reason that the
service reports in ``ApplyExtractionResponse.skipped`` — unapplied items
are never silently dropped.

See:
    :class:`narrare.kb.extraction_apply_service.ExtractionApplyService`
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeIs, cast

import structlog

from narrare.kb._extraction_resolution import (
    ResolutionDecision,
    resolve_update_target,
    strip_reserved_keys,
)
from narrare.kb.schemas import (
    KBEntryCreate,
    KBEntryUpdate,
)
from narrare.kb.schemas_extraction import ApplyExtractionEntryResult

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.schemas_extraction import ApplyExtractionItem
    from narrare.kb.service import KBService

logger = structlog.get_logger(__name__)


async def apply_new_entity_item(
    novel_id: UUID,
    user_id: UUID,
    item: ApplyExtractionItem,
    kb_service: KBService,
    created_entries: list[ApplyExtractionEntryResult],
    chapter_position: int | None = None,
) -> None:
    """Create a new KB entry from a ``new_entity`` extraction item.

    The item's ``proposed_content`` is stripped of platform-reserved keys
    (forge guard, ADR-085 §5) before storage. When a resolved chapter
    position is supplied, the reserved ``metadata["provenance"]`` block is
    stamped with it — the apply flow is its only writer.

    Args:
        novel_id: Novel scope.
        user_id: Requesting user.
        item: The extraction item.
        kb_service: KB service (entry creation).
        created_entries: Accumulator for results.
        chapter_position: Chapter's position in the novel's chapter
            ordering, or ``None`` when the request carries no chapter
            (then no provenance is stamped — zero behavior change).
    """
    metadata = strip_reserved_keys(item.proposed_content)
    if chapter_position is not None:
        metadata = _with_initial_provenance(metadata, chapter_position, item.name)
    data = KBEntryCreate(
        entity_type=item.entity_type or "unknown",
        name=item.name,
        metadata=metadata,
        body=item.source_text,
        status="draft",
        source="auto_extraction",
        review_status="pending",
    )
    entry = await kb_service.create(
        novel_id=novel_id,
        user_id=user_id,
        data=data,
    )
    created_entries.append(
        ApplyExtractionEntryResult(
            id=str(entry.id),
            name=entry.name,
            entity_type=entry.entity_type,
        ),
    )
    logger.info(
        "apply_new_entity_created",
        entry_id=str(entry.id),
        name=item.name,
        entity_type=item.entity_type,
    )


async def apply_update_entity_item(
    novel_id: UUID,
    user_id: UUID,
    item: ApplyExtractionItem,
    kb_repo: KBRepositoryProtocol,
    kb_service: KBService,
    updated_entries: list[ApplyExtractionEntryResult],
    chapter_position: int | None = None,
) -> str | None:
    """Update an existing KB entry from an ``update_entity`` item.

    Target resolution, the downgrade-guarded rename decision, and the
    merge-not-clobber metadata composition live in
    :mod:`narrare.kb._extraction_resolution`; unresolvable items are a
    reported skip (RULE-11). After composition, the reserved
    ``metadata["provenance"]`` block is advanced with the resolved chapter
    position (dedupe + sorted append, ``last_seen`` = applied position,
    new names appended to ``name_variants``) — the apply flow is its only
    writer. Without a chapter position, stored provenance is left
    untouched.

    Args:
        novel_id: Novel scope.
        user_id: Requesting user.
        item: The extraction item.
        kb_repo: KB repository (update-target resolution).
        kb_service: KB service (entry update).
        updated_entries: Accumulator for results.
        chapter_position: Chapter's position in the novel's chapter
            ordering, or ``None`` when the request carries no chapter.

    Returns:
        Skip reason, or ``None`` when the entry was updated. The precise
        failure cause is in the logs; the response carries the stable
        ``target_not_resolved`` identifier.
    """
    decision = await resolve_update_target(item, kb_repo, novel_id)
    if decision is None:
        return "target_not_resolved"

    metadata = _with_advanced_provenance(decision, chapter_position, item.name)
    data = KBEntryUpdate(
        metadata=metadata,
        name=decision.rename_to,
    )
    entry = await kb_service.update(
        novel_id=novel_id,
        entry_id=decision.target_id,
        user_id=user_id,
        data=data,
    )
    updated_entries.append(
        ApplyExtractionEntryResult(
            id=str(entry.id),
            name=entry.name,
            entity_type=entry.entity_type,
        ),
    )
    logger.info(
        "apply_update_entity_updated",
        entry_id=str(entry.id),
        name=item.name,
        renamed_to=decision.rename_to,
    )
    return None


def _with_initial_provenance(
    metadata: dict[str, object] | None,
    chapter_position: int,
    name: str,
) -> dict[str, object]:
    """Stamp the initial ``provenance`` block onto a create-path metadata.

    Pure; returns a new dict — the stripped proposal is never mutated.

    Args:
        metadata: The stripped proposed metadata (may be ``None``).
        chapter_position: Resolved chapter position for this apply.
        name: The entity name observed in this extraction item.

    Returns:
        A metadata dict containing exactly the initial provenance block:
        ``chapters=[position]``, first/last seen = position, and the name
        as sole ``name_variants`` entry.
    """
    result: dict[str, object] = dict(metadata or {})
    result["provenance"] = {
        "chapters": [chapter_position],
        "first_seen_chapter": chapter_position,
        "last_seen_chapter": chapter_position,
        "name_variants": [name],
    }
    return result


def _with_advanced_provenance(
    decision: ResolutionDecision,
    chapter_position: int | None,
    name: str,
) -> dict[str, object] | None:
    """Advance provenance on the update path after merge-not-clobber.

    Without a chapter position the merged metadata passes through
    unchanged (zero behavior change — stored provenance is never removed
    or altered). With one, the provenance block is recomputed from the
    entry's pre-merge storage: chapter appended (dedupe, sorted),
    ``last_seen_chapter`` = applied position, new names appended to
    ``name_variants`` (dedupe, keep order). The base is the merged
    metadata when the item proposed content, else a copy of the stored
    metadata — rebuilding from storage avoids clobbering existing keys.

    Args:
        decision: The resolved update target (merged + stored metadata).
        chapter_position: Resolved position, or ``None`` to pass through.
        name: The entity name observed in this extraction item.

    Returns:
        The metadata to persist, or ``None`` to leave storage untouched.
    """
    if chapter_position is None:
        return decision.merged_metadata
    base = (
        dict(decision.merged_metadata)
        if decision.merged_metadata is not None
        else dict(decision.existing_metadata or {})
    )
    base["provenance"] = _advance_provenance(
        decision.existing_metadata,
        chapter_position,
        name,
    )
    return base


def _is_int(value: object) -> TypeIs[int]:
    """Strictly ``int`` (bools are ints in Python — exclude them)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _advance_provenance(
    existing_metadata: dict[str, object] | None,
    chapter_position: int,
    name: str,
) -> dict[str, object]:
    """Compute the next ``provenance`` block from the stored metadata.

    Pure; tolerant of missing or malformed prior blocks (a non-dict
    ``provenance`` or non-int chapters degrade to a fresh block instead
    of crashing the apply). Provenance is apply-flow-owned: whatever a
    proposal contained was already stripped before composition.

    Args:
        existing_metadata: The entry's stored metadata (may be ``None``).
        chapter_position: Resolved chapter position for this apply.
        name: The entity name observed in this extraction item.

    Returns:
        The advanced provenance block.
    """
    existing = existing_metadata or {}
    raw = existing.get("provenance")
    previous = cast("dict[str, object]", raw) if isinstance(raw, dict) else {}

    chapters: set[int] = set()
    raw_chapters = previous.get("chapters")
    if isinstance(raw_chapters, list):
        for value in cast("list[object]", raw_chapters):
            if _is_int(value):
                chapters.add(value)
    chapters.add(chapter_position)

    variants: list[str] = []
    raw_variants = previous.get("name_variants")
    if isinstance(raw_variants, list):
        variants = [v for v in cast("list[object]", raw_variants) if isinstance(v, str)]
    if name not in variants:
        variants.append(name)

    raw_first = previous.get("first_seen_chapter")
    first_seen = raw_first if _is_int(raw_first) else min(chapters)

    return {
        "chapters": sorted(chapters),
        "first_seen_chapter": first_seen,
        "last_seen_chapter": chapter_position,
        "name_variants": variants,
    }
