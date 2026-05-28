"""NLP infrastructure — tokenization, POS, NER, syllables, dialogue.

All NLP operations go through the NLPProvider Protocol (RULE-08).
Use :func:`get_nlp_provider` to obtain the default provider.

See Also
--------
ADR-021 — Deterministic Analysis Strategy (spaCy as NLP backbone).
"""

from narrare_core.nlp.contracts import NLPProvider
from narrare_core.nlp.contracts_types import (
    Entity,
    LanguageCode,
    POSTag,
    Token,
    TokenResult,
)

__all__ = [
    "Entity",
    "LanguageCode",
    "NLPProvider",
    "POSTag",
    "Token",
    "TokenResult",
]
