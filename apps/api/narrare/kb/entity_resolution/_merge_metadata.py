"""Pure two-sided metadata merge for the KB entity resolution executor
(ADR-085 P4, spec §6.2).

Merge-not-clobber composition of the loser's metadata into the survivor's:
dicts recurse (loser sub-keys are added, survivor sub-keys are never
clobbered), lists union preserving the survivor's order, equal values
confirm, and unequal scalars are a conflict — the survivor value wins AND
the pair is recorded via :class:`MergeConflict`, so nothing is silently
lost. Also decides which loser keys count as incorporated
(``merged_fact_keys``) and skips the loser-side reserved keys
(``provenance`` — apply-flow-owned per spec §5 — and ``resolution`` — the
merge audit block itself).

Pure functions, no I/O — split from ``merge_executor.py`` per RULE-04.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

import structlog

from narrare.kb.entity_resolution.schemas_resolution import MergeConflict

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

logger = structlog.get_logger(__name__)

#: Reserved metadata keys owned by dedicated flows — never merged from the
#: loser side (``provenance`` is apply-flow-owned, spec §5; ``resolution``
#: is the merge audit block written by the executor).
RESERVED_META_KEYS: Final[frozenset[str]] = frozenset({"provenance", "resolution"})


def _as_dict(value: object) -> dict[str, object] | None:
    """Typed view of a JSONB dict value (``None`` for anything else)."""
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def _as_list(value: object) -> list[object] | None:
    """Typed view of a JSONB list value (``None`` for anything else)."""
    return cast("list[object]", value) if isinstance(value, list) else None


def merge_values(
    survivor_value: object,
    loser_value: object,
    path: str,
    conflicts: list[MergeConflict],
) -> tuple[object, bool]:
    """Two-sided merge of one metadata value (§6.2).

    Args:
        survivor_value: The survivor's stored value at ``path``.
        loser_value: The loser's stored value at ``path``.
        path: Dotted metadata path (conflict records name it, e.g.
            ``address.city``).
        conflicts: Accumulator for scalar conflicts (survivor wins, §6.2).

    Returns:
        ``(merged_value, contributed)`` where ``contributed`` is True when
        the loser side added or confirmed content (a conflict-free outcome).
    """
    survivor_dict = _as_dict(survivor_value)
    loser_dict = _as_dict(loser_value)
    if survivor_dict is not None and loser_dict is not None:
        merged: dict[str, object] = dict(survivor_dict)
        contributed = False
        for key in sorted(loser_dict):
            child_path = f"{path}.{key}"
            if key not in merged:
                merged[key] = loser_dict[key]
                contributed = True
                continue
            merged[key], child_contributed = merge_values(
                merged[key], loser_dict[key], child_path, conflicts
            )
            contributed = contributed or child_contributed
        return merged, contributed
    survivor_list = _as_list(survivor_value)
    loser_list = _as_list(loser_value)
    if survivor_list is not None and loser_list is not None:
        extras = [item for item in loser_list if item not in survivor_list]
        unioned: list[object] = [*survivor_list, *extras]
        return unioned, bool(extras)
    if survivor_value == loser_value:
        return survivor_value, True
    conflicts.append(
        MergeConflict(key=path, survivor_value=survivor_value, loser_value=loser_value)
    )
    return survivor_value, False


def merge_metadata(
    survivor_meta: Mapping[str, object] | None,
    loser_meta: Mapping[str, object] | None,
) -> tuple[dict[str, object], list[MergeConflict], list[str]]:
    """Merge the loser's metadata into the survivor's (§6.2, no clobber).

    Loser-side reserved keys (``provenance``/``resolution``) are skipped and
    logged (RULE-11): provenance stays apply-flow-owned (spec §5) and the
    loser's stale audit block must not leak into the survivor. Nothing is
    lost — the deprecated loser row keeps its full metadata.

    Args:
        survivor_meta: The survivor's stored metadata (may be ``None``).
        loser_meta: The loser's stored metadata (may be ``None``).

    Returns:
        ``(merged, conflicts, merged_fact_keys)`` where ``merged_fact_keys``
        are the sorted top-level loser keys incorporated without conflict
        (added, recursively merged, list-unioned, or already equal).
    """
    merged: dict[str, object] = dict(survivor_meta or {})
    conflicts: list[MergeConflict] = []
    contributed: set[str] = set()
    loser_source: Mapping[str, object] = loser_meta or {}
    for key in sorted(loser_source):
        if key in RESERVED_META_KEYS:
            logger.info("merge_reserved_key_skipped", key=key)
            continue
        loser_value = loser_source[key]
        if key not in merged:
            merged[key] = loser_value
            contributed.add(key)
            continue
        merged[key], key_contributed = merge_values(merged[key], loser_value, key, conflicts)
        if key_contributed:
            contributed.add(key)
    return merged, conflicts, sorted(contributed)


def read_resolution_block(metadata: Mapping[str, object] | None) -> dict[str, object]:
    """Tolerant read of a stored ``metadata["resolution"]`` block.

    Returns:
        The stored block, or ``{}`` when absent or malformed (never raises
        — corrupted JSONB must not crash a merge).
    """
    raw = (metadata or {}).get("resolution")
    return cast("dict[str, object]", raw) if isinstance(raw, dict) else {}


def resolution_block(
    prior: Mapping[str, object] | None,
    conflicts: Sequence[MergeConflict],
    *,
    survivor_id: str,
    merged_at: str,
    suggestion_id: str,
    confidence: float | None,
) -> dict[str, object]:
    """Build the survivor's ``metadata["resolution"]`` block (§6.2/§6.4).

    Chained merges accumulate: prior ``conflicts`` are preserved and the
    new ones appended (no silent loss — fix round 1), while
    ``merged_into``/``merged_at``/``suggestion_id``/``confidence`` always
    reflect the LATEST merge. Unknown prior fields pass through untouched.

    Args:
        prior: The survivor's previous ``resolution`` block (may be ``{}``).
        conflicts: This merge's conflicts, serialized and appended.
        survivor_id: Survivor id string (``merged_into`` of the latest merge).
        merged_at: ISO-8601 timestamp of the latest merge.
        suggestion_id: Suggestion identity of the latest merge.
        confidence: Re-scored confidence of the latest merge.

    Returns:
        The merged audit block to store on the survivor.
    """
    block: dict[str, object] = dict(prior or {})
    raw_conflicts = block.get("conflicts")
    prior_conflicts: list[object] = (
        cast("list[object]", raw_conflicts) if isinstance(raw_conflicts, list) else []
    )
    block["conflicts"] = [*prior_conflicts, *(c.model_dump() for c in conflicts)]
    block["merged_into"] = survivor_id
    block["merged_at"] = merged_at
    block["suggestion_id"] = suggestion_id
    block["confidence"] = confidence
    return block


def persisted_int(block: Mapping[str, object], key: str) -> int:
    """Strictly-int field of a stored block (bools excluded); ``0`` when absent/malformed."""
    value = block.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def persisted_str_list(block: Mapping[str, object], key: str) -> list[str]:
    """String-list field of a stored block; ``[]`` when absent/malformed."""
    value = block.get(key)
    if isinstance(value, list):
        return [item for item in cast("list[object]", value) if isinstance(item, str)]
    return []
