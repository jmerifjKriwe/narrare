"""Edge-case pins for KB resolution detection signals (ADR-085).

Deliberately separate from ``test_signals.py``: that file sits at 394 of
the 400 lines allowed by RULE-04, so the Task 3 review carry-forward pin
(non-numeric age values stay neutral) landed here instead of growing the
ratcheted file past its hard limit.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

from narrare_core.kb.resolution.models import EntitySnapshot
from narrare_core.kb.resolution.signals import attributes_signal

if TYPE_CHECKING:
    from collections.abc import Mapping


def make_snapshot(
    *,
    metadata: Mapping[str, object] | None = None,
) -> EntitySnapshot:
    return EntitySnapshot(
        entry_id=uuid4(),
        name="Anna Meyer",
        entity_type="character",
        status="active",
        metadata=dict(metadata or {}),
        provenance=None,
        neighbor_ids=frozenset(),
        embedding=None,
    )


# --- S3 attributes: edge semantics --------------------------------------------------


def test_attributes_non_numeric_age_values_stay_neutral():
    # Task 3 review carry-forward: non-numeric age values are dropped before
    # comparison -> shared family without comparable pairs -> 0.0, never veto.
    a = make_snapshot(metadata={"age": "twenty-four"})
    b = make_snapshot(metadata={"age": 24})
    result = attributes_signal(a, b)
    assert result.value == 0.0
    assert result.veto is False
