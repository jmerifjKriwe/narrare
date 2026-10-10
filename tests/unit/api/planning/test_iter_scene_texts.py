"""Unit tests for planning._helpers.iter_scene_texts (PLAN-001 T14, spec §7).

The helper is the ONE shared scene text scan surface: the KB lifecycle
consumer uses it at event time; the consistency ref-index adopts it in
T15. These tests pin the exact field set and the ``scene_plans[{id}]``
location format.
"""

from __future__ import annotations

import uuid

from narrare.planning._helpers import iter_scene_texts
from tests.factories import make_scene_plan


def test_scans_core_text_fields_with_scene_plan_locations() -> None:
    scene = make_scene_plan(
        title="The gate",
        purpose="Create stakes",
        conflict="Guard refuses entry",
        resolution="They sneak past",
    )

    pairs = dict(iter_scene_texts(scene))

    base = f"scene_plans[{scene.id}]"
    assert pairs[f"{base}.title"] == "The gate"
    assert pairs[f"{base}.purpose"] == "Create stakes"
    assert pairs[f"{base}.conflict"] == "Guard refuses entry"
    assert pairs[f"{base}.resolution"] == "They sneak past"


def test_scans_beats_entries_with_indices() -> None:
    scene = make_scene_plan(beats=["first event", "second event"])

    pairs = dict(iter_scene_texts(scene))

    base = f"scene_plans[{scene.id}]"
    assert pairs[f"{base}.beats[0]"] == "first event"
    assert pairs[f"{base}.beats[1]"] == "second event"


def test_scans_present_character_names_and_goals() -> None:
    scene = make_scene_plan(
        present_characters=[
            {"id": str(uuid.uuid4()), "name": "John", "goal": "escape"},
            {"name": "Guard", "goal": "stop John"},
        ]
    )

    pairs = dict(iter_scene_texts(scene))

    base = f"scene_plans[{scene.id}]"
    assert pairs[f"{base}.present_characters[0].name"] == "John"
    assert pairs[f"{base}.present_characters[0].goal"] == "escape"
    assert pairs[f"{base}.present_characters[1].name"] == "Guard"
    assert pairs[f"{base}.present_characters[1].goal"] == "stop John"


def test_scans_hybrid_ref_names() -> None:
    scene = make_scene_plan(
        pov_character_ref={"id": str(uuid.uuid4()), "name": "John"},
        location_ref={"id": str(uuid.uuid4()), "name": "The keep"},
    )

    pairs = dict(iter_scene_texts(scene))

    base = f"scene_plans[{scene.id}]"
    assert pairs[f"{base}.pov_character_ref.name"] == "John"
    assert pairs[f"{base}.location_ref.name"] == "The keep"


def test_tolerates_arbitrary_jsonb_shapes() -> None:
    """JSONB is runtime-arbitrary: non-dict presences and missing names
    are skipped, not raised."""
    scene = make_scene_plan(
        present_characters=["garbage", {"goal": "nameless"}, 42],
        pov_character_ref="not-a-dict",
        location_ref=None,
    )

    pairs = dict(iter_scene_texts(scene))

    base = f"scene_plans[{scene.id}]"
    assert f"{base}.present_characters[1].goal" in pairs
    assert not any(".pov_character_ref" in loc for loc in pairs)
    assert not any(".location_ref" in loc for loc in pairs)
