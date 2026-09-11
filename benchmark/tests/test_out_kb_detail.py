"""Unit tests for the OUT-detail drivers: entity detail + graph (Task 9).

Covers CAP-OUT-03 (the COMPLETE KB-state fetch the Task-11 scorer
consumes) and CAP-OUT-04 (graph + shortest-path probe). Split from
``test_out_direction.py`` per RULE-04 (file-size limit); shared
fixtures in ``out_direction_helpers.py``. The browse/search tests and
the 500-matrix live in ``test_out_direction.py``; the CAP-OUT-05..10
tests in ``test_out_direction_surfaces.py``.
"""

from __future__ import annotations

from benchmark.drivers.out_direction import EntityDetailDriver, GraphDriver
from benchmark.drivers.out_records import (
    EntityDetailRecord,
    GraphEdgeRef,
    GraphNodeRef,
    GraphRecord,
    KbEntryDetail,
    RelationshipDetail,
)
from benchmark.tests.out_direction_helpers import (
    ENTRY_A as ENTRY_DETAIL_BODY,
)
from benchmark.tests.out_direction_helpers import (
    GRAPH_BODY,
    GRAPH_SINGLE_NODE_BODY,
    INVERSE_BODY,
    KB_DETAIL,
    KB_GRAPH,
    KB_INVERSE,
    KB_RELATIONSHIPS,
    KB_SHORTEST_PATH,
    PATH_BODY,
    RELATIONSHIPS_BODY,
    invoke,
)

# ---------------------------------------------------------------------------
# CAP-OUT-03 — EntityDetailDriver: entry + relationships + inverse suggestion
# ---------------------------------------------------------------------------


def test_entity_detail_driver_fetches_entry_relationships_and_inverse() -> None:
    routes = {
        f"GET {KB_DETAIL}": ENTRY_DETAIL_BODY,
        f"GET {KB_RELATIONSHIPS}": RELATIONSHIPS_BODY,
        f"GET {KB_INVERSE}": INVERSE_BODY,
    }

    api, events, parsed = invoke(EntityDetailDriver, routes, targets={"entry_id": "entry-9"})

    assert api.paths() == [
        f"GET {KB_DETAIL}",
        f"GET {KB_RELATIONSHIPS}",
        f"GET {KB_INVERSE}",
    ]
    assert api.calls[2].params == {"rel_type": "lives_in"}
    assert isinstance(parsed, EntityDetailRecord)
    assert parsed == EntityDetailRecord(
        entry=KbEntryDetail(
            id="entry-9",
            novel_id="novel-1",
            entity_type="character",
            name="Benchmark Figur",
            slug="benchmark-figur",
            status="draft",
            tags=None,
            metadata=None,
            body=None,
            template_version=None,
            source="benchmark",
            review_status="approved",
            embeddings_dirty=False,
        ),
        relationships=(
            RelationshipDetail(
                id="rel-1",
                rel_type="lives_in",
                source_id="entry-9",
                target_id="entry-1",
                label=None,
                direction="directed",
                source_name="Anna Meyer",
                target_name="HafenCity",
                metadata=None,
            ),
        ),
        inverse_of="lives_in",
        inverse_rel_type="inhabited_by",
    )
    assert [event.step for event in events] == [
        "CAP-OUT-03:entry",
        "CAP-OUT-03:relationships",
        "CAP-OUT-03:inverse-suggestion",
    ]


def test_entity_detail_driver_skips_inverse_without_relationships() -> None:
    routes: dict[str, object] = {
        f"GET {KB_DETAIL}": ENTRY_DETAIL_BODY,
        f"GET {KB_RELATIONSHIPS}": [],
    }

    api, _events, parsed = invoke(EntityDetailDriver, routes, targets={"entry_id": "entry-9"})

    assert api.paths() == [f"GET {KB_DETAIL}", f"GET {KB_RELATIONSHIPS}"]
    assert isinstance(parsed, EntityDetailRecord)
    assert parsed.relationships == ()
    assert parsed.inverse_of is None
    assert parsed.inverse_rel_type is None


# ---------------------------------------------------------------------------
# CAP-OUT-04 — GraphDriver: nodes/edges/stats + shortest-path probe
# ---------------------------------------------------------------------------


def test_graph_driver_fetches_graph_and_shortest_path_between_first_nodes() -> None:
    routes = {
        f"GET {KB_GRAPH}": GRAPH_BODY,
        f"GET {KB_SHORTEST_PATH}": PATH_BODY,
    }

    api, events, parsed = invoke(GraphDriver, routes)

    assert api.paths() == [f"GET {KB_GRAPH}", f"GET {KB_SHORTEST_PATH}"]
    assert api.calls[1].params == {"source_id": "entry-9", "target_id": "entry-2"}
    assert isinstance(parsed, GraphRecord)
    assert parsed.nodes == (
        GraphNodeRef(id="entry-9", label="Anna Meyer", entity_type="character", degree=1),
        GraphNodeRef(id="entry-2", label="HafenCity", entity_type="location", degree=1),
    )
    assert parsed.edges == (
        GraphEdgeRef(
            id="rel-1",
            source="entry-9",
            target="entry-2",
            rel_type="lives_in",
            direction="directed",
        ),
    )
    assert parsed.entity_type_counts == (("character", 1), ("location", 1))
    assert parsed.rel_type_counts == (("lives_in", 1),)
    assert parsed.isolated_count == 0
    assert parsed.connected_components == 1
    assert parsed.path == ("entry-9", "entry-2")
    assert parsed.path_length == 1
    assert [event.step for event in events] == [
        "CAP-OUT-04:graph",
        "CAP-OUT-04:shortest-path",
    ]


def test_graph_driver_skips_path_probe_for_single_node_graph() -> None:
    routes = {f"GET {KB_GRAPH}": GRAPH_SINGLE_NODE_BODY}

    api, _events, parsed = invoke(GraphDriver, routes)

    assert api.paths() == [f"GET {KB_GRAPH}"]
    assert isinstance(parsed, GraphRecord)
    assert parsed.path is None
    assert parsed.path_length is None
