"""Typed case inputs and outputs for the ``writing_prose`` eval suite.

Extracted from ``evals/models.py`` per RULE-04 (modularize, do not compress)
to mirror ``models_planning.py`` / ``models_kb_operations.py``. The models are
re-exported from ``evals/models`` so existing ``from evals.models import ...``
imports keep working.

The input shape is modelled after the real writing services
(``apps/api/narrare/writing/{extend,suggest,style_variant}_service.py``) and
their contracts, but the eval uses its OWN deterministic smoke task (no
provider calls) — these models only define the case I/O contract.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

__all__ = [
    "WritingProseInput",
    "WritingProseResult",
]


class WritingProseInput(BaseModel):
    """Input for writing-prose eval cases (extend / suggest / variant).

    ``anchor_text`` is the selection or preceding text to continue or rewrite,
    ``instruction`` is the author's creative direction, and the surrounding
    context fields mirror ``context_before`` / ``context_after`` on the real
    writing requests.
    """

    operation: Literal["extend", "suggest", "variant"]
    anchor_text: str
    context_before: str = ""
    context_after: str = ""
    instruction: str
    genre: str = "Fantasy"
    language: str = "en"


class WritingProseResult(BaseModel):
    """Normalized writing-prose generation result.

    ``operation`` echoes the requested operation, ``text`` is the generated
    prose, ``word_count`` is the deterministic word count of ``text``, and
    ``notes`` carries optional provenance (e.g. "Smoke" marker).
    """

    operation: str
    text: str
    word_count: int = 0
    notes: str = ""
