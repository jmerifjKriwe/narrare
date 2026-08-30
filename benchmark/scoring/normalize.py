"""Deterministic normalization primitives shared by the build-quality matchers.

Single source of the text/date rules cited by the entity, fact, and
relation matchers:

- ``normalize_text`` — names AND fact values: casefold; every run of
  non-alphanumeric characters (whitespace, hyphens, punctuation)
  collapses to one space. ``"Anna   MEYER"``, ``"anna-meyer"`` and
  ``"Anna Meyer"`` all normalize to ``"anna meyer"``.
- ``normalize_predicate`` — predicates / relationship types: casefold;
  non-alphanumeric runs become a single underscore (snake_case
  normalization). camelCase is deliberately NOT converted: both the
  reference registry and the KB use snake_case predicates by
  construction.
- ``parse_date_value`` — actual-side interval values: positive ``int``
  years and ``"YYYY"`` / ``"YYYY-MM"`` / ``"YYYY-MM-DD"`` strings parse
  into ``PartialDate``; anything else is ``None`` (unparseable = no
  date evidence, never a contradiction).
- ``boundary_matches`` — month-precision interval boundary comparison
  with a ±1 month tolerance (prose ``"Ende Februar"`` materialized as
  ``2017-03`` still matches a ``{2017, 2}`` reference bound).

Pure functions only — the scorer must stay deterministic (plan Global
Constraints: no wall-clock, no randomness in scoring).
"""

from __future__ import annotations

from typing import Final

from benchmark.corpus_views import PartialDate

MONTH_TOLERANCE: Final[int] = 1
"""Month-precision boundary tolerance (±1 month) for interval bounds."""


def normalize_text(value: str) -> str:
    """Fold case/whitespace/punctuation: alnum runs joined by single spaces."""
    pieces: list[str] = []
    current: list[str] = []
    for char in value.casefold():
        if char.isalnum():
            current.append(char)
        elif current:
            pieces.append("".join(current))
            current = []
    if current:
        pieces.append("".join(current))
    return " ".join(pieces)


def normalize_predicate(value: str) -> str:
    """Snake_case normalization: alnum runs joined by single underscores."""
    return "_".join(normalize_text(value).split())


def parse_date_value(raw: object) -> PartialDate | None:
    """Parse an actual-side date value into a ``PartialDate`` (else None)."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return PartialDate(year=raw) if raw >= 1 else None
    if not isinstance(raw, str):
        return None
    parts = raw.strip().split("-")
    if not 1 <= len(parts) <= 3 or not all(part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    if numbers[0] < 1:
        return None
    month = numbers[1] if len(numbers) > 1 else None
    day = numbers[2] if len(numbers) > 2 else None
    if month is not None and not 1 <= month <= 12:
        return None
    if day is not None and not 1 <= day <= 31:
        return None
    return PartialDate(year=numbers[0], month=month, day=day)


def _month_index(date: PartialDate) -> int:
    return date.year * 12 + (date.month or 0)


def boundary_matches(ref: PartialDate, actual: PartialDate) -> bool:
    """Month-precision boundary comparison with ±1 month tolerance.

    A year-precision reference bound (``{year: 2017}``) accepts any actual
    date within that year. A month-precision reference bound accepts actual
    dates within ±``MONTH_TOLERANCE`` months. A year-only actual value is
    consistent with any month of the same year (a coarser actual statement
    cannot contradict a finer reference bound).
    """
    if ref.month is None or actual.month is None:
        return ref.year == actual.year
    return abs(_month_index(actual) - _month_index(ref)) <= MONTH_TOLERANCE
