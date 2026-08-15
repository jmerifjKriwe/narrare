"""Per-category mode definitions for invocation probes.

Aggregates the category modules into ``ALL_MODES`` — the single source of
truth for which modes exist and what inputs they need. Split from
``scripts/probes/mode_data.py`` (single file) for RULE-04 compliance
(file-size hard limit).

When adding new modes with ``requires_runtime_evidence: true`` in the
adoption registry, add them to the matching category module here AND in
``scripts/probes/validation_budget_probes.py``.

RULE-06: One responsibility — aggregation of the category mode lists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.probes.modes.analysis import ANALYSIS_MODES
from scripts.probes.modes.generation import GENERATION_MODES
from scripts.probes.modes.kb import KB_MODES
from scripts.probes.modes.planning import PLANNING_MODES
from scripts.probes.modes.writing import WRITING_MODES

if TYPE_CHECKING:
    from narrare_core.llm.intents import LLMIntent

#: All modes across all categories (category order preserved).
ALL_MODES: list[tuple[str, str, LLMIntent, dict[str, str]]] = [
    *WRITING_MODES,
    *ANALYSIS_MODES,
    *KB_MODES,
    *PLANNING_MODES,
    *GENERATION_MODES,
]

__all__ = [
    "ALL_MODES",
    "ANALYSIS_MODES",
    "GENERATION_MODES",
    "KB_MODES",
    "PLANNING_MODES",
    "WRITING_MODES",
]
