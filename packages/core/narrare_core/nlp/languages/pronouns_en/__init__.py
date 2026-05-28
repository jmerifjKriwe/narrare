"""
English pronoun lexicon — comprehensive pronoun data for literary analysis.

Split into sub-modules for maintainability (RULE-04).
Merged into a single ``PRONOUNS_EN`` dict at package level.
"""

from narrare_core.nlp.languages.pronouns_en.other import OTHER
from narrare_core.nlp.languages.pronouns_en.personal import PERSONAL_POSS

PRONOUNS_EN: dict[str, dict[str, str | int | bool | None]] = {
    **PERSONAL_POSS,
    **OTHER,
}

__all__ = ["PRONOUNS_EN"]
