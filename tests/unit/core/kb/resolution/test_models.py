import dataclasses
import uuid

import pytest

from narrare_core.kb.resolution.models import (
    EntitySnapshot,
    EntryProvenance,
    PairScore,
    ResolutionBand,
    SignalResult,
)


def _snap(name: str = "Anna") -> EntitySnapshot:
    return EntitySnapshot(
        entry_id=uuid.uuid4(),
        name=name,
        entity_type="character",
        status="active",
        metadata={},
        provenance=None,
        neighbor_ids=frozenset(),
        embedding=None,
    )


def test_snapshots_are_frozen():
    s = _snap()
    # Explicit __setattr__ call: this is exactly what the assignment statement
    # `s.name = "X"` compiles to — the frozen dataclass __setattr__ raises
    # FrozenInstanceError at runtime (ruff B010 rejects the setattr() form,
    # pyright rejects attribute assignment on frozen dataclasses).
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.__setattr__("name", "X")


def test_signal_result_defaults():
    r = SignalResult(signal="name_tier", value=0.7)
    assert r.veto is False and r.detail == ""


def test_provenance_fields():
    p = EntryProvenance(
        chapters=(1, 2, 3), first_seen_chapter=1, last_seen_chapter=3, name_variants=("Anna",)
    )
    assert p.chapters == (1, 2, 3)


def test_pair_score_fields_taken_as_given():
    a, b = uuid.uuid4(), uuid.uuid4()
    band: ResolutionBand = "AUTO_ELIGIBLE"
    score = PairScore(
        entry_a_id=a,
        entry_b_id=b,
        confidence=0.895,
        band=band,
        signals=(),
        vetoes=(),
    )
    assert score.entry_a_id == a and score.entry_b_id == b
    assert score.confidence == 0.895 and score.band == band
    assert score.signals == () and score.vetoes == ()
