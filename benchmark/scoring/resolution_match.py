"""Resolution scorer: expected duplicate pairs vs the system's suggestions
(CAP-IN-10, ADR-085 P6, spec §8).

Derivation contract — expected pairs come from the REFERENCE alone,
never from the system's output: every entry whose normalized name OR
slug matches a reference entity's ``name`` + ``aliases`` set (the
``normalize_text`` folding shared with ``entity_match``) binds to that
entity; all entries bound to one reference form ONE claim group, and a
group with ≥ 2 entries yields its complete unordered pair set
(deterministic, transitive). On normalized-key collisions the earlier
reference claims the entry (entity_match rule 3). "Anna" + "Anna
Meyer" → one group (alias "Anna"); the distractor "Anna Meier" binds to
its own reference — cross pairs are false positives by construction.

Metrics (spec §8; detection validity — records only, never the LLM):

- ``precision`` = |suggested ∩ expected| / |suggested|; with NO
  suggestions defined as 1.0 (no false positives exist).
- ``recall`` = |expected ∩ suggested| / |expected|; with NO expected
  pairs defined as 1.0 (no duplicate was missed — vacuous truth; a
  derivation failure surfaces as ``expected_pair_count == 0`` instead).
- ``auto_band_ok`` — AUTO_ELIGIBLE ⊆ expected (band quality).
- ``distractor_never_suggested`` — binary gate: False iff some
  suggested pair has BOTH endpoints bound and to DIFFERENT references.
  A pair with an unbound endpoint is a precision miss, not the spec's
  cross-reference trap, and keeps the gate True.
- Endorsed merges pair by {survivor, loser} ids (MergeResult carries no
  suggestion_id, ADR-085 Task-14 record shape) and are counted against
  the expected set as the merge-measurement evidence.

Post-merge inputs: the runner fetches the scored KB AFTER the drivers,
so endorsed losers are deprecated-hidden in the listing — the caller
reconstructs the pre-merge entry view (``ClaimEntry``) before deriving
groups (see ``benchmark.runner_scoring``).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING

from benchmark.scoring.normalize import normalize_text

if TYPE_CHECKING:
    from collections.abc import Sequence

    from benchmark.corpus_views import Entity
    from benchmark.drivers.in_records import MergeResult, ResolutionSuggestion

__all__ = ["ClaimEntry", "ResolutionScore", "claim_groups", "pair_key", "score_resolution"]


@dataclass(frozen=True)
class ClaimEntry:
    """The minimal binding shape of one pre-merge KB entry (id/name/slug).

    A deliberately narrower projection than ``EntrySummary``: merge
    losers are reconstructed from the resolution record (deprecated and
    hidden in the scored listing) and carry NO entity_type/status —
    absence stays absence instead of placeholder fields.
    """

    id: str
    name: str
    slug: str


@dataclass(frozen=True)
class ResolutionScore:
    """CAP-IN-10 scorer output (spec §8) — the ``resolution`` section."""

    precision: float
    recall: float
    auto_band_ok: bool
    distractor_never_suggested: bool
    expected_pair_count: int
    suggested_count: int
    endorsed_count: int
    endorsed_expected_pairs: int


def pair_key(entry_a: str, entry_b: str) -> tuple[str, str]:
    """Identity of an UNORDERED KB-entry pair (spec §8 pair semantics)."""
    return (entry_a, entry_b) if entry_a <= entry_b else (entry_b, entry_a)


def claim_groups(
    refs: Sequence[Entity], entries: Sequence[ClaimEntry]
) -> tuple[frozenset[str], ...]:
    """Bind entries to references (name/slug vs name + alias set); per
    reference, in reference order, one frozenset of bound entry ids.

    An entry is claimed at most once (first reference wins), so groups
    are disjoint and the cross-reference gate below is exact. References
    that bind nothing yield an empty frozenset — group count always
    equals reference count (positional, deterministic).
    """
    normalized_name = {entry.id: normalize_text(entry.name) for entry in entries}
    normalized_slug = {entry.id: normalize_text(entry.slug) for entry in entries}
    claimed: set[str] = set()
    groups: list[frozenset[str]] = []
    for ref in refs:
        keys = {normalize_text(ref.name), *(normalize_text(alias) for alias in ref.aliases)}
        members = frozenset(
            entry.id
            for entry in entries
            if entry.id not in claimed
            and (normalized_name[entry.id] in keys or normalized_slug[entry.id] in keys)
        )
        claimed |= members
        groups.append(members)
    return tuple(groups)


def score_resolution(
    expected_groups: Sequence[frozenset[str]],
    suggestions: Sequence[ResolutionSuggestion],
    endorsed: Sequence[MergeResult],
) -> ResolutionScore:
    """Score the surfaced suggestions against the reference-derived
    expected pairs (module docstring: derivation + metric conventions).
    """
    expected_pairs = _expected_pairs(expected_groups)
    suggested_pairs = {pair_key(s.entry_a_id, s.entry_b_id) for s in suggestions}
    auto_pairs = {
        pair_key(s.entry_a_id, s.entry_b_id) for s in suggestions if s.band == "AUTO_ELIGIBLE"
    }
    endorsed_pairs = {pair_key(merge.survivor_id, merge.loser_id) for merge in endorsed}
    return ResolutionScore(
        precision=(
            len(expected_pairs & suggested_pairs) / len(suggested_pairs) if suggested_pairs else 1.0
        ),
        recall=(
            len(expected_pairs & suggested_pairs) / len(expected_pairs) if expected_pairs else 1.0
        ),
        auto_band_ok=auto_pairs <= expected_pairs,
        distractor_never_suggested=_no_cross_reference_pair(expected_groups, suggested_pairs),
        expected_pair_count=len(expected_pairs),
        suggested_count=len(suggested_pairs),
        endorsed_count=len(endorsed),
        endorsed_expected_pairs=len(endorsed_pairs & expected_pairs),
    )


def _expected_pairs(groups: Sequence[frozenset[str]]) -> frozenset[tuple[str, str]]:
    """Transitive pair set: all unordered pairs within each ≥2 group."""
    return frozenset(pair_key(a, b) for group in groups for a, b in combinations(sorted(group), 2))


def _no_cross_reference_pair(
    groups: Sequence[frozenset[str]],
    suggested_pairs: frozenset[tuple[str, str]] | set[tuple[str, str]],
) -> bool:
    """True iff no suggested pair has both endpoints bound to DIFFERENT
    groups (references). Unbound endpoints keep the gate True — that
    case is precision's job, not the distractor trap's.
    """
    membership = {entry_id: index for index, group in enumerate(groups) for entry_id in group}
    return all(
        membership.get(pair[0]) is None
        or membership.get(pair[1]) is None
        or membership[pair[0]] == membership[pair[1]]
        for pair in suggested_pairs
    )
