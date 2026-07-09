"""Typed case inputs and outputs for the ``names`` eval suite.

Extracted from ``evals/models.py`` per RULE-04 (modularize, do not compress)
to mirror ``models_writing.py`` / ``models_planning.py`` /
``models_kb_operations.py``. The models are re-exported from
``evals.models`` so existing ``from evals.models import ...`` imports keep
working.

The ``names`` suite is smoke-only (no Tier-1 agent behind it; see
``SMOKE_ONLY_SUITES`` in ``tests/unit/evals/test_runner_and_drift.py``): it
has no runtime task. These models only define the deterministic case I/O
contract consumed by the smoke task and the ``NameListQuality`` evaluator.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

__all__ = [
    "NameGenerationInput",
    "NameGenerationResult",
]


class NameGenerationInput(BaseModel):
    """Input for name-generation eval cases (character / place / plot).

    ``name_type`` selects the generation kind, ``count`` is the requested
    number of names, and ``seed_terms`` are optional inspiration tokens the
    generator should fold into (not merely echo) the output.
    """

    name_type: Literal["character", "place", "plot"]
    count: int = 3
    language: str = "en"
    genre: str = "Fantasy"
    seed_terms: list[str] = []
    constraints: str = ""


class NameGenerationResult(BaseModel):
    """Normalized name-generation result.

    ``names`` is the generated name list, ``name_type`` echoes the requested
    kind, and ``notes`` carries optional provenance (e.g. "Smoke" marker).
    """

    names: list[str]
    name_type: str
    notes: str = ""
