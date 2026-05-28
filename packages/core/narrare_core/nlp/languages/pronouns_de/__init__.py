"""
German pronoun lexicon — comprehensive pronoun data for literary analysis.

Split into sub-modules for maintainability (RULE-04).
Merged into a single ``PRONOUNS_DE`` dict at package level.
"""

from narrare_core.nlp.languages.pronouns_de.indefinite import INDEFINITE
from narrare_core.nlp.languages.pronouns_de.personal import PERSONAL
from narrare_core.nlp.languages.pronouns_de.possessive import POSSESSIVE
from narrare_core.nlp.languages.pronouns_de.reflexive import REFLEXIVE
from narrare_core.nlp.languages.pronouns_de.relative import RELATIVE_DEM_INT

PRONOUNS_DE: dict[str, dict[str, str | int | bool | None]] = {
    **PERSONAL,
    **POSSESSIVE,
    **RELATIVE_DEM_INT,
    **INDEFINITE,
    **REFLEXIVE,
}

__all__ = ["PRONOUNS_DE"]
