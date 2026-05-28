"""
French pronoun lexicon — comprehensive pronoun data for literary analysis.

Split into sub-modules for maintainability (RULE-04).
Merged into a single ``PRONOUNS_FR`` dict at package level.
"""

from narrare_core.nlp.languages.pronouns_fr.other import OTHER
from narrare_core.nlp.languages.pronouns_fr.personal import PERSONAL
from narrare_core.nlp.languages.pronouns_fr.possessive import POSSESSIVE

PRONOUNS_FR: dict[str, dict[str, str | int | bool | None]] = {
    **PERSONAL,
    **POSSESSIVE,
    **OTHER,
}

__all__ = ["PRONOUNS_FR"]
