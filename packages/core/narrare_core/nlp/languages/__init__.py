"""Language-specific resources: pronouns, emotion lexicons.

This package bundles linguistic data for English, German, and French,
including comprehensive pronoun tables and emotion lexicons with
Valence-Arousal-Dominance (VAD) mapping.

Usage::

    from narrare_core.nlp.languages import PRONOUNS, EMOTION_LEXICONS

    # Look up a pronoun
    features = PRONOUNS["en"]["she"]
    # features == {"person": 3, "number": "singular", ...}

    # Look up emotion associations
    emotions = EMOTION_LEXICONS["en"].get("joyful", set())
    # emotions == {"joy", "positive", "anticipation"}
"""

from narrare_core.nlp.languages.emotions import (
    EMOTION_LEXICON_DE,
    EMOTION_LEXICON_EN,
    EMOTION_LEXICON_FR,
    get_emotions,
    get_vad,
)
from narrare_core.nlp.languages.pronouns_de import PRONOUNS_DE
from narrare_core.nlp.languages.pronouns_en import PRONOUNS_EN
from narrare_core.nlp.languages.pronouns_fr import PRONOUNS_FR

__all__ = [
    "EMOTION_LEXICONS",
    "EMOTION_LEXICON_DE",
    "EMOTION_LEXICON_EN",
    "EMOTION_LEXICON_FR",
    "PRONOUNS",
    "PRONOUNS_DE",
    "PRONOUNS_EN",
    "PRONOUNS_FR",
    "get_emotions",
    "get_vad",
]

PRONOUNS: dict[str, dict[str, dict[str, str | int | bool | None]]] = {
    "de": PRONOUNS_DE,
    "en": PRONOUNS_EN,
    "fr": PRONOUNS_FR,
}

EMOTION_LEXICONS: dict[str, dict[str, set[str]]] = {
    "en": EMOTION_LEXICON_EN,
    "de": EMOTION_LEXICON_DE,
    "fr": EMOTION_LEXICON_FR,
}
