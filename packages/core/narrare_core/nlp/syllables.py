"""
Syllable counting for English, German, and French.

Primary implementation uses ``pyphen`` for hyphenation-based counting.
When ``pyphen`` is not installed, falls back to a heuristic vowel-group
counting algorithm that handles each language's specific patterns.

Usage::

    >>> count_syllables("beautiful", "en")
    3
    >>> count_syllables("wunderschöne", "de")
    4
    >>> count_syllables("magnifique", "fr")
    3

See Also
--------
ADR-021 — spaCy + multilingual lexica as deterministic NLP backbone.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.nlp.contracts_types import LanguageCode

# ---------------------------------------------------------------------------
# Pyphen locale mapping
# ---------------------------------------------------------------------------

_PYPHEN_LOCALE: dict[LanguageCode, str] = {
    "en": "en_US",
    "de": "de_DE",
    "fr": "fr_FR",
}

# ---------------------------------------------------------------------------
# Vowel sets
# ---------------------------------------------------------------------------

_VOWELS = set("aeiouyAEIOUY")
_VOWELS_DE = _VOWELS | set("äöüÄÖÜ")
_VOWELS_FR = _VOWELS | set("éèêëàâùûôîïÉÈÊËÀÂÙÛÔÎÏ")

# Diphthong patterns that count as a single vowel group
_EN_DIPHTHONGS = re.compile(r"(?i:ai|au|ea|ee|ei|eu|ie|oa|oe|oi|oo|ou|ue|ui)")
_DE_DIPHTHONGS = re.compile(r"(?i:ai|au|äu|ei|eu|ie|oi|ui)")
_FR_DIPHTHONGS = re.compile(r"(?i:ai|aî|au|eau|ei|eu|œu|oi|oin|ou|ui)")

# Silent-e patterns for English (word-final "e" that doesn't add a syllable)
_EN_SILENT_E = re.compile(r"(?i:(?:[^aeiouy]e)$|(?:[^aeiouy]e[ds])$|^(?:the|ate)$)")

# Language-specific vowel set lookup
_LANGUAGE_VOWELS: dict[LanguageCode, set[str]] = {
    "en": _VOWELS,
    "de": _VOWELS_DE,
    "fr": _VOWELS_FR,
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def count_syllables(word: str, language: LanguageCode = "en") -> int:
    """Count the number of syllables in *word* for the given *language*.

    Strips leading/trailing whitespace and punctuation before counting.
    Returns ``0`` for empty strings.

    Args:
        word: A single word (may include surrounding whitespace/punctuation).
        language: Language code (``"en"``, ``"de"``, ``"fr"``).

    Returns:
        Number of syllables (``0`` for empty or whitespace-only input).

    Raises:
        ValueError: If *language* is not ``"en"``, ``"de"``, or ``"fr"``.
    """
    if language not in _PYPHEN_LOCALE:
        raise ValueError(
            f"Unsupported language '{language}'. Supported: {list(_PYPHEN_LOCALE.keys())}."
        )

    # Strip whitespace and common punctuation
    cleaned = word.strip().strip(".,!?;:\"'«»-—()[]{}").lower()
    if not cleaned:
        return 0

    # Try pyphen first
    result = _count_syllables_pyphen(cleaned, language)
    if result is not None:
        return result

    # Fallback to heuristic
    return _count_syllables_heuristic(cleaned, language)


# ---------------------------------------------------------------------------
# Pyphen-based counting
# ---------------------------------------------------------------------------


def _count_syllables_pyphen(word: str, language: LanguageCode) -> int | None:
    """Count syllables using pyphen hyphenation.

    Returns ``None`` when pyphen is not installed or the locale is missing.

    Args:
        word: Cleaned word (lowercase, no punctuation).
        language: Language code for locale lookup.

    Returns:
        Syllable count, or ``None`` if pyphen is unavailable.
    """
    try:
        import pyphen as _pyphen  # pyright: ignore[reportMissingImports, reportMissingTypeStubs] -- optional dependency
    except ImportError:
        return None

    try:
        locale = _PYPHEN_LOCALE[language]
        dic = _pyphen.language_fallback(locale)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        # Insert hyphenation points and count segments
        hyphenated = dic.inserted(word)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]
        if hyphenated and hyphenated != word:
            return hyphenated.count("-") + 1  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        # If pyphen could not hyphenate at all, let the caller decide
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Heuristic vowel-group counting
# ---------------------------------------------------------------------------


def _count_syllables_heuristic(word: str, language: LanguageCode) -> int:
    """Heuristic syllable counting via vowel-group detection.

    This is a fallback when pyphen is not available or fails.
    It counts groups of consecutive vowels, then applies
    language-specific corrections.

    Args:
        word: Cleaned word (lowercase, no punctuation).
        language: Language code for language-specific rules.

    Returns:
        Estimated syllable count (minimum 1 for non-empty words).
    """
    vowels = _LANGUAGE_VOWELS.get(language, _VOWELS)

    if len(word) == 1:
        return 1

    # Count vowel groups (consecutive vowels = 1 group)
    count = 0
    in_vowel = False
    for char in word:
        if char in vowels:
            if not in_vowel:
                count += 1
                in_vowel = True
        else:
            in_vowel = False

    if count == 0:
        return 1  # Every word has at least one syllable

    # Language-specific corrections
    if language == "en":
        count = _apply_english_corrections(word, count)
    elif language == "de":
        count = _apply_german_corrections(word, count)
    elif language == "fr":
        count = _apply_french_corrections(word, count)

    return max(1, count)


# ---------------------------------------------------------------------------
# Language-specific heuristic corrections
# ---------------------------------------------------------------------------


def _apply_english_corrections(word: str, count: int) -> int:
    """Apply English-specific syllable corrections."""
    # Silent final "e": "make" → 1, "table" → 2
    # But not "the", "be", "me" etc.
    if word.endswith("e") and len(word) > 2 and word[-2] not in "aeiou":
        # "able", "ible" keep the e syllable
        if word.endswith(("able", "ible", "acle", "icle")):
            return count
        # Silent e
        count -= 1

    # "-ed" at end: "walked" → 1, "wanted" → 2
    if word.endswith("ed") and len(word) > 3:
        if word[-3] in "dt":
            return count  # "wanted", "needed" → keep
        count -= 1  # "walked" → remove e syllable

    # "-es" at end: "boxes" → 2, "makes" → 1
    if word.endswith("es") and len(word) > 3:
        if word[-3] in "sxzčšž":
            return count
        count -= 1

    # "-le" at end: "table", "people" → the 'le' is syllabic
    if (
        word.endswith("le")
        and len(word) > 3
        and word[-3] not in "aeiou"
        and word.endswith(("able", "ible"))
    ):
        return count
    # Already counted correctly in vowel grouping

    return count


def _apply_german_corrections(word: str, count: int) -> int:
    """Apply German-specific syllable corrections."""
    # "-en" ending: "gehen" → 2 (not 3)
    if word.endswith("en") and len(word) > 3 and word[-3] not in "aeiouäöü" and word[-3] in "mnlr":
        count -= 1

    # "-el" ending: "Tafel" → 2
    if word.endswith("el") and len(word) > 3 and word[-3] not in "aeiouäöü":
        pass  # Already correctly counted

    # "-ig" at end: "lustig" → 2
    if word.endswith("ig") and len(word) > 3 and word[-3] not in "aeiouäöü":
        pass  # Already correctly counted

    # "ie" is one syllable in German: "Liebe" → 2
    if "ie" in word:
        # ie counted as 2 vowel groups by heuristic, should be 1
        count -= word.count("ie")
        # But if "ie" appears with other vowels around it, may overcorrect
        # The simple count is close enough for analysis purposes

    return count


def _apply_french_corrections(word: str, count: int) -> int:
    """Apply French-specific syllable corrections.

    French has specific patterns:
    - Final silent "e": "parle" → 1 (only if preceded by a consonant)
    - "-ent" verb ending: "parlent" → 1
    - Nasal vowels count as one: "temps" → 1
    - "oi" is one syllable: "trois" → 1
    """
    # Final silent "e" (not "é", "è", "ê", "ë") — ALWAYS silent in French,
    # regardless of preceding letter. "que", "gue", "che", "le", "me", etc.
    # the "e" never adds a syllable in multi-syllable words.
    if word.endswith("e") and not word.endswith(("é", "è", "ê", "ë")) and len(word) > 2:
        count -= 1

    # "-ent" verb ending: "parlent", "aiment"
    if word.endswith("ent") and len(word) > 4 and word[-4] not in "aeiouéèêë":
        count -= 1

    # Nasal: "an", "am", "en", "em", "in", "im", "on", "om", "un", "um"
    # These are single syllables even with two vowel letters
    # The heuristic overcounts these

    # "oi" in French is one syllable
    if "oi" in word:
        count -= word.count("oi")

    # "au" / "eau" are one syllable
    if "eau" in word:
        count -= word.count("eau")
    elif "au" in word:
        count -= word.count("au")

    return count
