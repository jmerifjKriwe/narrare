"""Detection signals S2-S5 for KB entity resolution (ADR-085).

Pure, deterministic functions over :class:`EntitySnapshot` pairs, semantics
per spec §4 signal table:

- **S2 temporal** — handoff ``+1.0`` (disjoint provenance ranges, gap
  ``<= HANDOFF_MAX_GAP``, shorter-name variant earlier); co-existence veto
  ``-1.0`` (overlapping/interleaving ranges at ``s1_tier < 1.0``); same-name
  overlap ``+1.0`` (``s1_tier == 1.0``, double extraction); ``0.0`` unknown
  provenance or gap above the maximum.
- **S3 attributes** — continuity ``+1.0`` (>= 1 shared semantic family with
  compatible values, no contradiction); contradiction veto ``-1.0``
  (incompatible values in a shared family: different gender strings, age
  keys implying different birth years); ``0.0`` no shared families.  The age
  family is compared across keys via ``(year, value)`` pairs: equal years
  must match exactly, different years tolerate ``<= 1`` drift ("progression")
  or must imply the same birth year.
- **S4 neighborhood** — ``+1.0`` Jaccard over ``neighbor_ids`` at/above
  ``NEIGHBOR_JACCARD``; ``-0.5`` disjoint when both sides have ``>= 2``
  relationships (never a veto); ``0.0`` sparse/unknown.
- **S5 embedding** — ``+1.0`` cosine at/above ``EMBEDDING_COS`` over
  same-length non-None embeddings; ``0.0`` otherwise.  Never negative:
  semantically similar *different* people exist.

The S1 name tier is NOT re-derived here — callers pass the already-computed
tier value into :func:`temporal_signal`.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Final

from narrare_core.kb.resolution.models import EntitySnapshot, EntryProvenance, SignalResult
from narrare_core.kb.resolution.name_tiers import normalize_name

if TYPE_CHECKING:
    from collections.abc import Mapping

# Calibration constants (spec §4) — ADR-085-referenced defaults, not runtime
# configuration; recalibration is a spec edit with benchmark evidence.
HANDOFF_MAX_GAP: Final[int] = 2
NEIGHBOR_JACCARD: Final[float] = 0.3
EMBEDDING_COS: Final[float] = 0.82

# S3 semantic key families (spec §4 S3): a metadata key belongs to a family
# when its normalized form starts with the family name (shared-prefix).
ATTRIBUTE_FAMILIES: Final[tuple[str, ...]] = (
    "age",
    "profession",
    "gender",
    "birth",
    "residence",
)

# First isolated 4-digit number in an age-family key = its validity year
# (e.g. "age (2017)" / "age_2017" both normalize to "age 2017").
_YEAR_IN_KEY: Final[re.Pattern[str]] = re.compile(r"(?<!\d)(\d{4})(?!\d)")


def temporal_signal(a: EntitySnapshot, b: EntitySnapshot, s1_tier: float) -> SignalResult:
    """Signal S2: chapter-range handoff vs co-existence (distractor veto)."""
    range_a = _chapter_range(a.provenance)
    range_b = _chapter_range(b.provenance)
    if range_a is None or range_b is None:
        return SignalResult("temporal", 0.0, detail="unknown provenance")

    first_a, last_a = range_a
    first_b, last_b = range_b

    later_start = max(first_a, first_b)
    earlier_end = min(last_a, last_b)
    if later_start <= earlier_end:
        # Overlapping or interleaving (containment included) chapter ranges.
        if s1_tier < 1.0:
            return SignalResult(
                "temporal",
                -1.0,
                veto=True,
                detail=(
                    f"co-existence veto: chapter ranges {first_a}-{last_a} and "
                    f"{first_b}-{last_b} overlap at name tier {s1_tier:g}"
                ),
            )
        return SignalResult(
            "temporal",
            1.0,
            detail=(
                f"double extraction: identical names overlap in chapter "
                f"ranges {first_a}-{last_a} and {first_b}-{last_b}"
            ),
        )

    gap = later_start - earlier_end
    if gap > HANDOFF_MAX_GAP:
        return SignalResult(
            "temporal", 0.0, detail=f"no handoff: gap {gap} exceeds maximum {HANDOFF_MAX_GAP}"
        )

    early, late = (a, b) if first_a < first_b else (b, a)
    if len(normalize_name(early.name)) > len(normalize_name(late.name)):
        return SignalResult(
            "temporal", 0.0, detail="no handoff: longer-name variant appears earlier"
        )

    early_range = range_a if first_a < first_b else range_b
    late_range = range_b if first_a < first_b else range_a
    return SignalResult(
        "temporal",
        1.0,
        detail=(
            f"handoff: chapters {early_range[0]}-{early_range[1]} then "
            f"{late_range[0]}-{late_range[1]} (gap {gap})"
        ),
    )


def attributes_signal(a: EntitySnapshot, b: EntitySnapshot) -> SignalResult:
    """Signal S3: shared semantic metadata families, continuity vs veto."""
    grouped_a = _grouped_by_family(a.metadata)
    grouped_b = _grouped_by_family(b.metadata)
    shared_families = [f for f in ATTRIBUTE_FAMILIES if f in grouped_a and f in grouped_b]
    if not shared_families:
        return SignalResult("attributes", 0.0, detail="no shared attribute families")

    compatible: list[str] = []
    contradiction: str | None = None
    for family in shared_families:
        if family == "age":
            family_ok, family_contra = _compare_ages(grouped_a[family], grouped_b[family])
        else:
            family_ok, family_contra = _compare_plain(grouped_a[family], grouped_b[family])
        if family_ok:
            compatible.append(family)
        if family_contra is not None and contradiction is None:
            contradiction = family_contra

    if contradiction is not None:
        return SignalResult("attributes", -1.0, veto=True, detail=contradiction)
    if compatible:
        return SignalResult(
            "attributes",
            1.0,
            detail=f"compatible shared attributes: {', '.join(sorted(compatible))}",
        )
    return SignalResult(
        "attributes", 0.0, detail="shared attribute families without comparable values"
    )


def neighborhood_signal(a: EntitySnapshot, b: EntitySnapshot) -> SignalResult:
    """Signal S4: relationship-adjacency overlap (weak corroborator)."""
    union = a.neighbor_ids | b.neighbor_ids
    if not union:
        return SignalResult("neighborhood", 0.0, detail="neighborhood unknown (no relationships)")

    shared = a.neighbor_ids & b.neighbor_ids
    jaccard = len(shared) / len(union)
    if jaccard >= NEIGHBOR_JACCARD:
        return SignalResult(
            "neighborhood",
            1.0,
            detail=(
                f"{len(shared)} shared neighbors (jaccard {jaccard:.2f} >= {NEIGHBOR_JACCARD})"
            ),
        )
    if not shared and len(a.neighbor_ids) >= 2 and len(b.neighbor_ids) >= 2:
        return SignalResult(
            "neighborhood",
            -0.5,
            detail=(
                f"disjoint neighborhoods ({len(a.neighbor_ids)} vs {len(b.neighbor_ids)} neighbors)"
            ),
        )
    return SignalResult(
        "neighborhood", 0.0, detail=f"weak neighborhood overlap (jaccard {jaccard:.2f})"
    )


def embedding_signal(a: EntitySnapshot, b: EntitySnapshot) -> SignalResult:
    """Signal S5: embedding cosine similarity (never negative by design)."""
    embedding_a = a.embedding
    embedding_b = b.embedding
    if (
        embedding_a is None
        or embedding_b is None
        or len(embedding_a) == 0
        or len(embedding_a) != len(embedding_b)
    ):
        return SignalResult(
            "embedding", 0.0, detail="embedding unknown (missing or length mismatch)"
        )

    dot = sum(x * y for x, y in zip(embedding_a, embedding_b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in embedding_a))
    norm_b = math.sqrt(sum(y * y for y in embedding_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return SignalResult("embedding", 0.0, detail="embedding degenerate (zero vector)")

    cosine = dot / (norm_a * norm_b)
    if cosine >= EMBEDDING_COS:
        return SignalResult("embedding", 1.0, detail=f"cosine {cosine:.3f} >= {EMBEDDING_COS}")
    return SignalResult("embedding", 0.0, detail=f"cosine {cosine:.3f} below {EMBEDDING_COS}")


# --- Internal helpers ---------------------------------------------------------


def _chapter_range(provenance: EntryProvenance | None) -> tuple[int, int] | None:
    """Resolve a provenance into a closed chapter range, or None if unknown."""
    if provenance is None:
        return None
    if provenance.first_seen_chapter is None or provenance.last_seen_chapter is None:
        return None
    return provenance.first_seen_chapter, provenance.last_seen_chapter


def _grouped_by_family(metadata: Mapping[str, object]) -> dict[str, list[tuple[str, object]]]:
    """Group metadata items into semantic families by normalized key prefix."""
    grouped: dict[str, list[tuple[str, object]]] = {}
    for key, value in metadata.items():
        normalized_key = normalize_name(key)
        for family in ATTRIBUTE_FAMILIES:
            if normalized_key.startswith(family):
                grouped.setdefault(family, []).append((normalized_key, value))
                break
    return grouped


def _normalized_value(value: object) -> str:
    """Normalize a metadata scalar for equality comparison."""
    return normalize_name(str(value))


def _as_float(value: object) -> float | None:
    """Parse a metadata scalar as a number; None when not numeric."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _age_pairs(items: list[tuple[str, object]]) -> list[tuple[int | None, float, str]]:
    """Extract ``(year, age, key)`` triples from age-family items."""
    pairs: list[tuple[int | None, float, str]] = []
    for normalized_key, value in items:
        age = _as_float(value)
        if age is None:
            continue
        match = _YEAR_IN_KEY.search(normalized_key)
        year = int(match.group(1)) if match else None
        pairs.append((year, age, normalized_key))
    return pairs


def _compare_plain(
    items_a: list[tuple[str, object]], items_b: list[tuple[str, object]]
) -> tuple[bool, str | None]:
    """Compare same-key scalar values: equality corroborates, mismatch vetoes."""
    by_key_b = dict(items_b)
    compatible = False
    contradiction: str | None = None
    for key_a, value_a in items_a:
        if key_a not in by_key_b:
            continue
        norm_a = _normalized_value(value_a)
        norm_b = _normalized_value(by_key_b[key_a])
        if norm_a == norm_b:
            compatible = True
        elif contradiction is None:
            contradiction = f"attribute contradiction: '{key_a}' {norm_a!r} vs {norm_b!r}"
    return compatible, contradiction


def _compare_ages(
    items_a: list[tuple[str, object]], items_b: list[tuple[str, object]]
) -> tuple[bool, str | None]:
    """Cross-compare ``(year, value)`` age pairs for progression vs veto.

    Equal years must match exactly.  Different years corroborate when the
    implied birth years match or the values drift by <= 1 ("progression");
    otherwise the pairs imply different birth years -> contradiction.
    Year-less keys carry no validity anchor: equal values corroborate,
    differing values stay neutral (unknown validity, never negative).
    """
    compatible = False
    contradiction: str | None = None
    for year_a, age_a, key_a in _age_pairs(items_a):
        for year_b, age_b, key_b in _age_pairs(items_b):
            if year_a is None or year_b is None:
                if year_a == year_b and age_a == age_b:
                    compatible = True
                continue
            if year_a == year_b:
                if age_a == age_b:
                    compatible = True
                elif contradiction is None:
                    contradiction = (
                        f"age contradiction: {age_a:g} vs {age_b:g} both stated "
                        f"for {year_a} ('{key_a}' / '{key_b}')"
                    )
            elif year_a - age_a == year_b - age_b:
                compatible = True  # same implied birth year
            elif abs(age_a - age_b) <= 1.0:
                compatible = True  # progression drift
            elif contradiction is None:
                contradiction = (
                    f"age contradiction: {age_a:g}@{year_a} vs {age_b:g}@{year_b} "
                    f"imply birth years {year_a - age_a:g} and {year_b - age_b:g}"
                )
    return compatible, contradiction


__all__ = [
    "ATTRIBUTE_FAMILIES",
    "EMBEDDING_COS",
    "HANDOFF_MAX_GAP",
    "NEIGHBOR_JACCARD",
    "attributes_signal",
    "embedding_signal",
    "neighborhood_signal",
    "temporal_signal",
]
