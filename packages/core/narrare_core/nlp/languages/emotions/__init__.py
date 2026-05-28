"""
Built-in emotion lexicon with Valence-Arousal-Dominance (VAD) mapping.

This module provides word-level emotion associations for English, German,
and French, covering 10 emotion categories from the NRC Emotion Lexicon
(EmoLex) framework.

The built-in lexicons focus on words that appear frequently in literary
prose. They are sufficient for ANAL-002 sentiment analysis without
requiring the full NRC EmoLex download.

To use the complete NRC EmoLex (14,000+ words), download it from
https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm and call
:func:`load_full_nrc_emolex` with the path to the downloaded file.

Usage::

    >>> get_emotions("melancholy", "en")
    {"sadness", "negative"}
    >>> get_vad("joyful", "en")
    VADScores(valence=0.81, arousal=0.35, dominance=0.31)

Attribution
-----------
NRC Emotion Lexicon (EmoLex) — Copyright © 2011 National Research Council
Canada. Licensed under CC BY-SA 3.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from narrare_core.nlp.languages.emotions.de import EMOTION_LEXICON_DE
from narrare_core.nlp.languages.emotions.en import EMOTION_LEXICON_EN
from narrare_core.nlp.languages.emotions.fr import EMOTION_LEXICON_FR

__all__ = [
    "ATTRIBUTION",
    "EMOTION_LEXICON_DE",
    "EMOTION_LEXICON_EN",
    "EMOTION_LEXICON_FR",
    "VADScores",
    "get_emotions",
    "get_vad",
    "load_full_nrc_emolex",
]

if TYPE_CHECKING:
    from narrare_core.nlp.contracts_types import LanguageCode

# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

ATTRIBUTION: str = (
    "NRC Emotion Lexicon (EmoLex) — Copyright © 2011 National Research "
    "Council Canada. Licensed under CC BY-SA 3.0. This built-in subset "
    "covers common literary words; the full lexicon can be loaded via "
    "load_full_nrc_emolex()."
)

# ---------------------------------------------------------------------------
# VAD (Valence-Arousal-Dominance) mapping
# ---------------------------------------------------------------------------

# Valence: unpleasant (-1) → pleasant (+1)
# Arousal: calm (-1) → excited (+1)
# Dominance: submissive (-1) → dominant (+1)
_EMOTION_TO_VAD: dict[str, tuple[float, float, float]] = {
    "anger": (-0.51, 0.59, 0.25),
    "anticipation": (0.29, 0.36, 0.28),
    "disgust": (-0.60, 0.35, 0.11),
    "fear": (-0.64, 0.60, -0.43),
    "joy": (0.81, 0.35, 0.31),
    "negative": (-0.70, 0.10, -0.30),
    "positive": (0.65, 0.10, 0.30),
    "sadness": (-0.63, -0.27, -0.33),
    "surprise": (0.13, 0.30, 0.10),
    "trust": (0.37, -0.05, 0.28),
}


@dataclass(frozen=True)
class VADScores:
    """Valence-Arousal-Dominance scores for an emotion or word.

    Attributes:
        valence: Pleasantness (-1 = unpleasant, +1 = pleasant).
        arousal: Intensity (-1 = calm, +1 = excited).
        dominance: Control (-1 = submissive, +1 = dominant).
    """

    valence: float
    arousal: float
    dominance: float


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_emotions(word: str, language: LanguageCode = "en") -> set[str]:
    """Return the set of emotion labels associated with *word*.

    Args:
        word: The word to look up (case-insensitive lookup).
        language: Language code (``"en"``, ``"de"``, or ``"fr"``).

    Returns:
        Set of emotion labels (e.g. ``{"joy", "positive"}``).
        Returns an empty set if the word is not in the lexicon.
    """
    normalized = word.lower().strip()
    lexicon = _LEXICONS.get(language)
    if lexicon is None:
        return set()
    return lexicon.get(normalized, set())


def get_vad(word: str, language: LanguageCode = "en") -> VADScores | None:
    """Return the aggregate VAD scores for *word* across its emotion labels.

    Computes the mean VAD across all emotion categories associated with
    the word. Returns ``None`` if the word is not in the lexicon.

    Args:
        word: The word to look up (case-insensitive).
        language: Language code (``"en"``, ``"de"``, or ``"fr"``).

    Returns:
        Aggregate :class:`VADScores`, or ``None`` if not found.
    """
    emotions = get_emotions(word, language)
    if not emotions:
        return None

    total_v = 0.0
    total_a = 0.0
    total_d = 0.0
    count = 0

    for emotion in emotions:
        vad = _EMOTION_TO_VAD.get(emotion)
        if vad is not None:
            total_v += vad[0]
            total_a += vad[1]
            total_d += vad[2]
            count += 1

    if count == 0:
        return None

    return VADScores(
        valence=round(total_v / count, 3),
        arousal=round(total_a / count, 3),
        dominance=round(total_d / count, 3),
    )


# ---------------------------------------------------------------------------
# Full NRC EmoLex loader (placeholder)
# ---------------------------------------------------------------------------


def load_full_nrc_emolex(path: str) -> dict[str, set[str]]:
    """Load the complete NRC EmoLex from a downloaded file.

    Placeholder for future full lexicon loading. Not yet implemented.

    Args:
        path: Path to the downloaded NRC-Emotion-Lexicon.txt file.

    Returns:
        Dictionary mapping words to sets of emotion labels.

    Raises:
        NotImplementedError: This function is not yet implemented.
    """
    raise NotImplementedError(
        "Full NRC EmoLex loading is not yet implemented. "
        "The built-in subset is available via get_emotions(). "
        f"Attribution: {ATTRIBUTION}"
    )


# ---------------------------------------------------------------------------
# Aggregated lookup
# ---------------------------------------------------------------------------

_LEXICONS: dict[str, dict[str, set[str]]] = {
    "en": EMOTION_LEXICON_EN,
    "de": EMOTION_LEXICON_DE,
    "fr": EMOTION_LEXICON_FR,
}
