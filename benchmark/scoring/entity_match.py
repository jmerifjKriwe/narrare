"""Entity matching: reference entities vs actual KB entries (Task 11).

Matching rule (the documented contract consumed by the scorer):

1. ``normalize_text`` is applied to BOTH sides: the reference ``name``
   and each ``aliases`` entry vs the actual entry ``name`` AND ``slug``
   (slugs are separator-joined names; normalization folds them onto the
   same space as whitespace).
2. Candidate order per reference entity: the name first, then the
   aliases in reference order. For each candidate the entry-name index
   is consulted before the entry-slug index. First hit wins.
3. Each entry is claimed AT MOST once; expected entities are processed
   in reference order, so on normalized-name collisions the earlier
   reference entity claims the entry (deterministic).
4. ``matched_via`` records the rule that produced the hit — ``"name"``,
   ``"slug"``, or ``"alias:<alias>"`` — for per-item traceability.
5. ``entity_type`` is deliberately NOT a match precondition: the
   reference vocabulary (person/place/object) and the KB vocabulary
   (character/location/organisation/...) are different domains with no
   lossless mapping; type divergence stays visible in the itemizations
   instead of silently dropping matches.

Unmatched expected entities are ``missing``; unclaimed actual entries
are ``spurious`` — unless a documented alias rule claims them (rule 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from benchmark.scoring.normalize import normalize_text

if TYPE_CHECKING:
    from benchmark.corpus_views import Entity
    from benchmark.drivers.out_records import EntrySummary


@dataclass(frozen=True)
class EntityMatch:
    """One reference entity claimed by one actual entry."""

    ref: Entity
    entry: EntrySummary
    via: str


@dataclass(frozen=True)
class EntityMatchResult:
    """Full bipartite outcome: claims, misses, and unclaimed entries."""

    matches: tuple[EntityMatch, ...]
    missing: tuple[Entity, ...]
    spurious: tuple[EntrySummary, ...]


def match_entities(
    expected: tuple[Entity, ...], entries: tuple[EntrySummary, ...]
) -> EntityMatchResult:
    """Match reference entities onto KB entries per the module contract."""
    by_name: dict[str, EntrySummary] = {}
    by_slug: dict[str, EntrySummary] = {}
    for entry in entries:
        by_name.setdefault(normalize_text(entry.name), entry)
        by_slug.setdefault(normalize_text(entry.slug), entry)

    claimed: set[str] = set()
    matches: list[EntityMatch] = []
    missing: list[Entity] = []
    for ref in expected:
        match = _claim(ref, by_name, by_slug, claimed)
        if match is None:
            missing.append(ref)
        else:
            claimed.add(match.entry.id)
            matches.append(match)

    spurious = tuple(entry for entry in entries if entry.id not in claimed)
    return EntityMatchResult(matches=tuple(matches), missing=tuple(missing), spurious=spurious)


def _claim(
    ref: Entity,
    by_name: dict[str, EntrySummary],
    by_slug: dict[str, EntrySummary],
    claimed: set[str],
) -> EntityMatch | None:
    """First-hit claim for one reference entity (name → aliases, name → slug).

    ``via`` records the rule: the name index yields the candidate label
    (``"name"`` / ``"alias:<alias>"``); the slug index yields ``"slug"``
    for the reference name, or the alias label when an alias matched a
    slug (the reference-side source is the traceable fact).
    """
    candidates: tuple[tuple[str, str], ...] = (
        (ref.name, "name"),
        *((alias, f"alias:{alias}") for alias in ref.aliases),
    )
    for candidate, label in candidates:
        keyed = normalize_text(candidate)
        entry = by_name.get(keyed)
        if entry is not None and entry.id not in claimed:
            return EntityMatch(ref=ref, entry=entry, via=label)
        entry = by_slug.get(keyed)
        if entry is not None and entry.id not in claimed:
            via = label if label != "name" else "slug"
            return EntityMatch(ref=ref, entry=entry, via=via)
    return None
