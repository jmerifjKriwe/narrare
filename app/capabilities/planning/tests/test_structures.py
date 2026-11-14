"""The story-structure registry: five structures tiling the unit interval.

Every structure tiles [0, 1] contiguously from zero with unique stage keys
(the backend contract the suggestion relies on: the shared boundary belongs
to the earlier stage), and each stage carries its title key in the registry's
keyed shape (`storyboard.stage.<key>`). The catalog half — every stage and
structure title key resolving in the en/de/fr planning catalogs — left with
the demolished planning web folder and returns when the rebuilt storyboard
screens bring their catalogs back (W2). A suggestion at 0 lands in the first
stage and at 1.0 in the last.
"""

from itertools import pairwise

import pytest

from app.capabilities.planning.structures import (
    STRUCTURES,
    UnknownStructureError,
    require_structure,
    suggest_stage,
)

EXPECTED_IDS = ("three-act", "heros-journey", "save-the-cat", "five-act", "seven-point")


def test_registry_holds_exactly_the_five_structures() -> None:
    assert tuple(sorted(STRUCTURES)) == tuple(sorted(EXPECTED_IDS))


@pytest.mark.parametrize("structure_id", EXPECTED_IDS)
def test_stages_tile_the_unit_interval_contiguously(structure_id: str) -> None:
    stages = require_structure(structure_id)

    assert len(stages) >= 3
    keys = [stage.key for stage in stages]
    assert len(set(keys)) == len(keys)
    assert stages[0].from_ratio == 0.0
    assert stages[-1].to_ratio == 1.0
    for stage in stages:
        assert stage.from_ratio < stage.to_ratio
        assert stage.title_key == f"storyboard.stage.{stage.key}"
    for earlier, later in pairwise(stages):
        assert later.from_ratio == earlier.to_ratio


@pytest.mark.parametrize("structure_id", EXPECTED_IDS)
def test_suggestion_bounds_land_in_first_and_last_stage(structure_id: str) -> None:
    stages = require_structure(structure_id)

    assert suggest_stage(stages, 0).key == stages[0].key
    assert suggest_stage(stages, 1.0).key == stages[-1].key
    # The shared boundary belongs to the earlier stage.
    for earlier, later in pairwise(stages):
        assert suggest_stage(stages, earlier.to_ratio).key == earlier.key
        assert later.key != earlier.key


def test_unknown_structure_is_refused_by_name() -> None:
    with pytest.raises(UnknownStructureError, match="unknown structure"):
        require_structure("three-moods")
