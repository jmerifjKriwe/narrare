"""Uncertain-band adjudication schemas (ADR-085 P5, spec §2).

Discharges the last two provisional aliases in ``contracts.py``:
``PairCandidate`` (what the adjudicator consumes) and ``Adjudication``
(what it produces). Split from ``schemas_resolution.py`` per RULE-04 —
the resolution schema file sits near its 200-line hard limit.
"""

from __future__ import annotations

from pydantic import BaseModel


class PairCandidate(BaseModel):
    """One uncertain-band pair submitted for LLM adjudication (D7).

    Carries the minimum the governed merge prompt needs plus the stable
    pair identity used to match the verdict back to its suggestion.
    """

    pair_key: str
    """Suggestion identity (``sha256(min ‖ max)[:16]``) this pair adjudicates."""

    entity_type: str
    """KB entity type of both entries (the merge prompt's entity variable)."""

    name_a: str
    """KB name of the first entry (min-id order, mirroring the suggestion)."""

    name_b: str
    """KB name of the second entry."""


class Adjudication(BaseModel):
    """LLM adjudication verdict for one uncertain-band pair (D7).

    ``supports_merge`` is advisory annotation only — it never executes a
    merge (spec §6/D3: merges run exclusively on explicit endorsement).
    """

    pair_key: str
    """Suggestion identity this verdict belongs to."""

    supports_merge: bool
    """``True`` only when the governed merge analysis decided ``merge``."""

    note: str
    """Human-readable verdict (or failure) note surfaced on the suggestion."""
