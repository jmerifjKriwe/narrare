"""Name-tier classification for KB entity resolution (ADR-085, signal S1).

Pure stdlib normalization plus deterministic tier classification consumed by
the resolution signals and scoring layers.  Tier semantics per ADR-085 §4 S1:

- ``EXACT``  (1.0): normalized names are equal
- ``SUBSET`` (0.7): one token set is a subset of the other AND the first
  tokens match (short form of a longer name, e.g. "Anna" ⊂ "Anna Meyer")
- ``FUZZY``  (0.4): ``difflib.SequenceMatcher.ratio() >= FUZZY_RATIO`` on
  the shorter-vs-longer normalized full names (e.g. "Meier" ~ "Meyer")
- ``NONE``   (0.0): no supported name similarity
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Final

# Tier values (spec §4 S1) — ADR-085-referenced defaults, not runtime config.
EXACT: Final[float] = 1.0
SUBSET: Final[float] = 0.7
FUZZY: Final[float] = 0.4
NONE: Final[float] = 0.0

# Fuzzy-match calibration (spec §4 calibration constants).
FUZZY_RATIO: Final[float] = 0.87

# Runs of whitespace and/or punctuation (incl. underscore) collapse to one
# space during normalization.
_SEPARATOR_RUN: Final[re.Pattern[str]] = re.compile(r"[\W_]+")


def normalize_name(value: str) -> str:
    """Normalize a raw name for comparison.

    Pipeline (order matters): casefold → NFKD decomposition with combining
    marks stripped (diacritic fold) → whitespace/punctuation runs collapsed
    to single spaces → strip.  ``"Ánnà  MÉYER!"`` → ``"anna meyer"``.
    """
    folded = value.casefold()
    decomposed = unicodedata.normalize("NFKD", folded)
    without_combining = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _SEPARATOR_RUN.sub(" ", without_combining).strip()


def classify_name_tier(a: str, b: str) -> tuple[float, str]:
    """Classify the name-tier (signal S1) for two raw names.

    Returns ``(tier_value, tier_name)`` with the tier constants above.
    Checks run in strict precedence: EXACT → SUBSET → FUZZY → NONE.  The
    fuzzy ratio is computed on the shorter-vs-longer normalized full names
    (equal lengths keep argument order — ``difflib`` ratios are not
    guaranteed symmetric, so the convention is pinned).
    """
    normalized_a = normalize_name(a)
    normalized_b = normalize_name(b)

    if normalized_a == normalized_b:
        return (EXACT, "EXACT")

    tokens_a = normalized_a.split()
    tokens_b = normalized_b.split()
    if (
        tokens_a
        and tokens_b
        and tokens_a[0] == tokens_b[0]
        and (set(tokens_a) <= set(tokens_b) or set(tokens_b) <= set(tokens_a))
    ):
        return (SUBSET, "SUBSET")

    shorter, longer = sorted((normalized_a, normalized_b), key=len)
    if SequenceMatcher(None, shorter, longer).ratio() >= FUZZY_RATIO:
        return (FUZZY, "FUZZY")

    return (NONE, "NONE")


__all__ = [
    "EXACT",
    "FUZZY",
    "FUZZY_RATIO",
    "NONE",
    "SUBSET",
    "classify_name_tier",
    "normalize_name",
]
