"""Temporal metadata-key grammar and year coverage (fact-match round 2).

The extraction keeps historical/temporal facts under suffixed metadata
keys. The observed grammar (run ``2026-09-07-clean-incremental-1``) has
THREE forms beyond the plain ``pred`` key:

- ``pred_YYYY``            — single year (``age_2017``)
- ``pred_YYYY_M``          — year with month suffix (``age_2019_12``);
  the month is 1-2 digits and does NOT tighten coverage (matching stays
  year-precision, like ``pred_YYYY``)
- ``pred_YYYY1_YYYY2``     — year range (``profession_2016_2021``)

``parse_temporal_key`` parses candidates by REGEX, not string equality;
the stripped predicate is returned raw — callers canonicalize it via
``canonical_fact_predicate``. ``covers_year`` decides whether a parsed
key's year set covers a fact's temporal position: single-year/month keys
are covered when the key year lies within the fact's reference interval
(bounds are year-precision; absent bounds never fail), range keys are
covered when the fact's anchor year (``valid_from``, falling back to
``valid_to``) lies within the key's range — an unanchored (unbounded,
non-range) fact accepts any year.

Pure functions only — deterministic scoring, no wall-clock.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from benchmark.corpus_views import Fact

TEMPORAL_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<predicate>.+?)_(?P<first>\d{4})(?:_(?P<second>\d{1,2}|\d{4}))?$"
)
"""Temporal key grammar: ``pred_YYYY``, ``pred_YYYY_M`` (1-2 digit
month), ``pred_YYYY1_YYYY2`` (range). The predicate group is NON-greedy
so the parse prefers the longest suffix: ``profession_2016_2021`` is a
range (``profession``, 2016→2021), not the single year 2021 under
``profession_2016``. A 3-digit suffix matches neither alternative and
leaves the key unparsed (stays unlicensed/spurious)."""

_RANGE_MIN_YEAR: Final[int] = 1000
"""A 4-digit second group is a range end; a 1-2 digit group is a month."""


@dataclass(frozen=True)
class TemporalKey:
    """One parsed temporal metadata key.

    ``predicate`` is the RAW stripped surface (pre-canonicalization);
    ``second`` is a month (1-2 digits) for the year_month form or the
    range end (4 digits) for the range form.
    """

    surface: str
    predicate: str
    first_year: int
    second: int | None


def parse_temporal_key(key: str) -> TemporalKey | None:
    """Parse a metadata key into its temporal form, else ``None``."""
    match = TEMPORAL_KEY_PATTERN.match(key)
    if match is None:
        return None
    second = match.group("second")
    return TemporalKey(
        surface=key,
        predicate=match.group("predicate"),
        first_year=int(match.group("first")),
        second=int(second) if second is not None else None,
    )


def year_in_bounds(fact: Fact, year: int) -> bool:
    """Year-precision containment of ``year`` in the fact's interval.

    Absent bounds never fail (open interval on that side).
    """
    lower = fact.valid_from.year if fact.valid_from is not None else None
    upper = fact.valid_to.year if fact.valid_to is not None else None
    return (lower is None or year >= lower) and (upper is None or year <= upper)


def covers_year(key: TemporalKey, fact: Fact) -> bool:
    """Whether the key's year set covers the fact's temporal position.

    Range keys cover the fact's ANCHOR year (``valid_from`` falling back
    to ``valid_to``; unanchored facts accept any year); single-year and
    year_month keys are covered when their year lies within the fact's
    reference interval.
    """
    second = key.second
    if second is not None and second >= _RANGE_MIN_YEAR:
        anchor = _anchor_year(fact)
        return anchor is None or key.first_year <= anchor <= second
    return year_in_bounds(fact, key.first_year)


def _anchor_year(fact: Fact) -> int | None:
    """The fact's own temporal anchor: ``valid_from`` year, else ``valid_to``."""
    if fact.valid_from is not None:
        return fact.valid_from.year
    if fact.valid_to is not None:
        return fact.valid_to.year
    return None
