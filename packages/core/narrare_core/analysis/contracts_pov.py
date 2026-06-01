"""POV analysis contract — Protocol definition (RULE-03).

Protocol for POV character detection and violation analysis.

See Also
--------
ADR-021 — Deterministic Analysis Strategy.
CONSTRAINTS.md RULE-03 — Contracts before implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.analysis.types import POVResult
    from narrare_core.nlp.contracts_types import LanguageCode


# ---------------------------------------------------------------------------
# ANAL-004: POV Analysis — Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class POVDetector(Protocol):
    """Protocol for POV character detection and POV violation analysis.

    Detects POV character per scene, identifies head-hopping,
    knowledge leakage, emotional leakage, and physical impossibility.
    LLM-based -- uses a pydantic-ai agent (``POVDetectionAgent``).

    This is a ``@runtime_checkable`` protocol -- use
    ``isinstance(detector, POVDetector)`` for runtime checks.
    """

    async def analyze(
        self,
        text: str,
        *,
        novel_id: UUID,
        language: LanguageCode = "en",
    ) -> POVResult:
        """Analyse POV consistency for the given text.

        Args:
            text: The chapter / scene text to analyse.
            novel_id: The novel project ID (used for KB lookups
                to resolve character names).
            language: Language code (``"en"``, ``"de"``, ``"fr"``).
                Defaults to ``"en"``.

        Returns:
            A :class:`POVResult` with per-scene assignments, flagged
            issues, distribution statistics, and switch counts.
        """
        ...
