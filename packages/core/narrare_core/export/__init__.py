"""Manuscript export pipeline — Core contracts + normalizer (IO-001 / ADR-081).

This package holds the pure-Narrare layer of the export pipeline: the
``ManuscriptNormalizer`` Protocol, the data shapes it produces, and the
concrete :class:`NarrareNormalizer`. It is **non-LLM** (no
``agents``/``prompts`` imports) and **Pure Core** (RULE-05: no ``apps/``
imports, no I/O, no subprocess).

Contracts live in :mod:`narrare_core.export.contracts`. The normalizer
(:mod:`narrare_core.export.normalizer`) transforms TipTap HTML into the clean
semantic form the renderers consume.
"""

from narrare_core.export.contracts import (
    ChapterMeta,
    Language,
    ManuscriptMetadata,
    ManuscriptNormalizer,
    NormalizedManuscript,
)
from narrare_core.export.normalizer import NarrareNormalizer

__all__ = [
    "ChapterMeta",
    "Language",
    "ManuscriptMetadata",
    "ManuscriptNormalizer",
    "NarrareNormalizer",
    "NormalizedManuscript",
]
