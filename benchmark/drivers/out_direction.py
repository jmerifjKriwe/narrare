"""OUT-direction capability drivers, KB surface (CAP-OUT-01..04, Task 9).

This module owns the four drivers on the core KB routes
(``/novels/{novel_id}/kb/...``): browse (01), search (02), entity
detail (03), graph (04). The remaining six OUT drivers live in
``benchmark.drivers.out_direction_surfaces`` (read surfaces 05-07) and
``benchmark.drivers.out_direction_assist`` (assist surfaces 08-10,
plus the shared retrieval probe); THIS module is the direction's
registration facade — ``OUT_DIRECTION_DRIVERS`` (the cap_id → driver
class map wired into ``benchmark.drivers``) is assembled here from all
three halves (RULE-04 split, facade precedent:
``benchmark.drivers.in_direction``).

Shared rules (module docstring of ``benchmark.drivers.in_parsing``):
every driver invokes exactly its registry ``EndpointSpec`` surface via
the REST shape helper, parses responses into the typed records of
``benchmark.drivers.out_records``, and returns a ``CapabilityResult``
whose ``parsed`` carries that record; raw exchanges flow to the run
sink. A missing ingest-discovered target → ``SKIPPED(structural)``;
transport/HTTP/shape failures → ``ERROR`` with a reason.

All ten OUT entries are REST-shaped (registry-verified — the five SSE
capabilities are IN-07/IN-09/CHK-05/06/07); this direction never opens
a stream.

Pagination: ``GET /kb/entries`` and ``GET /kb/entries/search`` return
``KBEntryListResponse`` (``page``/``page_size``/``total``,
``page_size ≤ 100``) — both are driven to exhaustion page by page at
the API's max page size, stopping on a short page or once ``total``
is collected (finite by construction: every iteration either stops or
collects a full page). The other OUT list surfaces (wiki summaries,
timeline events, series canon, templates, suggestions) are NOT
paginated — plain lists — and are driven in a single call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.drivers.in_parsing import (
    as_bool,
    as_int,
    as_list,
    as_opt_int,
    as_opt_object,
    as_opt_str_list,
    as_opt_text,
    as_str_tuple,
    as_text,
    guarded,
    require_target,
    response_field,
)
from benchmark.drivers.out_direction_assist import (
    ASSIST_OUT_DRIVERS,
    probe_name,
)
from benchmark.drivers.out_direction_surfaces import (
    SURFACES_OUT_DRIVERS,
)
from benchmark.drivers.out_records import (
    AutocompleteHit,
    EntityDetailRecord,
    EntryBrowseRecord,
    EntrySummary,
    GraphEdgeRef,
    GraphNodeRef,
    GraphRecord,
    KbEntryDetail,
    RelationshipDetail,
    SearchRecord,
)
from benchmark.drivers.shapes import invoke_rest

if TYPE_CHECKING:
    from collections.abc import Mapping

    from benchmark.drivers.base import CapabilityContext, CapabilityDriver, CapabilityResult

PAGE_SIZE: Final[int] = 100
"""API max page size (``page_size … le=100``, ``kb/router.py``)."""

AUTOCOMPLETE_LIMIT: Final[int] = 10
"""API default autocomplete breadth (le=50, ``kb/router_references.py``); pinned."""


# ---------------------------------------------------------------------------
# Shared: paginated KBEntryListResponse driving (CAP-OUT-01/02)
# ---------------------------------------------------------------------------


def _entry_summary(body: object) -> EntrySummary:
    """``KBEntryResponse`` scoring-relevant identity fields."""
    return EntrySummary(
        id=as_text(response_field(body, "id")),
        name=as_text(response_field(body, "name")),
        entity_type=as_text(response_field(body, "entity_type")),
        slug=as_text(response_field(body, "slug")),
        status=as_text(response_field(body, "status")),
        review_status=as_text(response_field(body, "review_status")),
    )


def _paginated_entries(
    ctx: CapabilityContext,
    *,
    step: str,
    path: str,
    params: Mapping[str, str],
) -> tuple[tuple[EntrySummary, ...], int, int]:
    """Collect ALL pages of a ``KBEntryListResponse`` endpoint.

    Stops on a short page (server exhausted) or once ``total`` entries
    are collected — every iteration either stops or adds a full page,
    so the loop is finite even against a drifting server.
    """
    entries: list[EntrySummary] = []
    total = 0
    page = 1
    while True:
        body = invoke_rest(
            ctx,
            step=f"{step}-page-{page}",
            method="GET",
            path=path,
            params={**params, "page": str(page), "page_size": str(PAGE_SIZE)},
        )
        items = as_list(response_field(body, "items"), "entry list")
        total = as_int(response_field(body, "total"))
        entries.extend(_entry_summary(item) for item in items)
        if len(items) < PAGE_SIZE or len(entries) >= total:
            return tuple(entries), total, page
        page += 1


def _autocomplete(ctx: CapabilityContext) -> tuple[AutocompleteHit, ...]:
    """Prefix-probe ``GET /kb/entries/autocomplete`` (plain dict rows)."""
    body = invoke_rest(
        ctx,
        step="CAP-OUT-01:autocomplete",
        method="GET",
        path=f"/api/v1/novels/{ctx.novel_id}/kb/entries/autocomplete",
        params={"q": probe_name(ctx), "limit": str(AUTOCOMPLETE_LIMIT)},
    )
    return tuple(
        AutocompleteHit(
            id=as_text(response_field(row, "id")),
            name=as_text(response_field(row, "name")),
            entity_type=as_text(response_field(row, "entity_type")),
            slug=as_text(response_field(row, "slug")),
        )
        for row in as_list(body, "autocomplete list")
    )


# ---------------------------------------------------------------------------
# CAP-OUT-01 — EntryBrowseDriver: full listing + autocomplete
# ---------------------------------------------------------------------------


def _drive_entry_browse(ctx: CapabilityContext) -> EntryBrowseRecord:
    entries, total, pages = _paginated_entries(
        ctx,
        step="CAP-OUT-01:browse",
        path=f"/api/v1/novels/{ctx.novel_id}/kb/entries",
        params={},
    )
    return EntryBrowseRecord(
        entries=entries, total=total, pages_fetched=pages, autocomplete=_autocomplete(ctx)
    )


class EntryBrowseDriver:
    """CAP-OUT-01 — worldbuilding browser data: all entries + autocomplete."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-OUT-01", ctx, _drive_entry_browse)


# ---------------------------------------------------------------------------
# CAP-OUT-02 — EntrySearchDriver: lexical search over the probe term
# ---------------------------------------------------------------------------


def _drive_entry_search(ctx: CapabilityContext) -> SearchRecord:
    query = probe_name(ctx)
    entries, total, pages = _paginated_entries(
        ctx,
        step="CAP-OUT-02:search",
        path=f"/api/v1/novels/{ctx.novel_id}/kb/entries/search",
        params={"q": query},
    )
    return SearchRecord(query=query, entries=entries, total=total, pages_fetched=pages)


class EntrySearchDriver:
    """CAP-OUT-02 — lexical (ILIKE) search; query = reference probe term."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-OUT-02", ctx, _drive_entry_search)


# ---------------------------------------------------------------------------
# CAP-OUT-03 — EntityDetailDriver: entry + relationships + inverse lookup
# ---------------------------------------------------------------------------


def _entry_detail(body: object) -> KbEntryDetail:
    """COMPLETE ``KBEntryResponse`` projection (Task-11 scorer surface)."""
    return KbEntryDetail(
        id=as_text(response_field(body, "id")),
        novel_id=as_text(response_field(body, "novel_id")),
        entity_type=as_text(response_field(body, "entity_type")),
        name=as_text(response_field(body, "name")),
        slug=as_text(response_field(body, "slug")),
        status=as_text(response_field(body, "status")),
        tags=as_opt_str_list(response_field(body, "tags")),
        metadata=as_opt_object(response_field(body, "metadata")),
        body=as_opt_text(response_field(body, "body")),
        template_version=as_opt_text(response_field(body, "template_version")),
        source=as_text(response_field(body, "source")),
        review_status=as_text(response_field(body, "review_status")),
        embeddings_dirty=as_bool(response_field(body, "embeddings_dirty")),
    )


def _relationship_detail(body: object) -> RelationshipDetail:
    """COMPLETE ``KBRelationshipResponse`` projection (scorer surface)."""
    return RelationshipDetail(
        id=as_text(response_field(body, "id")),
        rel_type=as_text(response_field(body, "rel_type")),
        source_id=as_text(response_field(body, "source_id")),
        target_id=as_text(response_field(body, "target_id")),
        label=as_opt_text(response_field(body, "label")),
        direction=as_text(response_field(body, "direction")),
        source_name=as_opt_text(response_field(body, "source_name")),
        target_name=as_opt_text(response_field(body, "target_name")),
        metadata=as_opt_object(response_field(body, "metadata")),
    )


def _drive_entity_detail(ctx: CapabilityContext) -> EntityDetailRecord:
    entry_id = require_target(ctx, "entry_id")
    base = f"/api/v1/novels/{ctx.novel_id}/kb/entries/{entry_id}"
    entry = invoke_rest(ctx, step="CAP-OUT-03:entry", method="GET", path=base)
    listed = invoke_rest(
        ctx, step="CAP-OUT-03:relationships", method="GET", path=f"{base}/relationships"
    )
    relationships = tuple(_relationship_detail(rel) for rel in as_list(listed, "relationship list"))
    inverse_of = relationships[0].rel_type if relationships else None
    inverse_rel_type: str | None = None
    if inverse_of is not None:
        inverse = invoke_rest(
            ctx,
            step="CAP-OUT-03:inverse-suggestion",
            method="GET",
            path=f"/api/v1/novels/{ctx.novel_id}/kb/relationships/inverse-suggestion",
            params={"rel_type": inverse_of},
        )
        inverse_rel_type = as_opt_text(response_field(inverse, "inverse"))
    return EntityDetailRecord(
        entry=_entry_detail(entry),
        relationships=relationships,
        inverse_of=inverse_of,
        inverse_rel_type=inverse_rel_type,
    )


class EntityDetailDriver:
    """CAP-OUT-03 — the KB-state fetch the Task-11 build-quality scorer reads."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-OUT-03", ctx, _drive_entity_detail)


# ---------------------------------------------------------------------------
# CAP-OUT-04 — GraphDriver: nodes/edges/stats + shortest-path probe
# ---------------------------------------------------------------------------


def _count_pairs(raw: object) -> tuple[tuple[str, int], ...]:
    """``dict[str, int]`` → key-sorted tuple pairs (deterministic equality)."""
    counts = as_opt_object(raw)
    if counts is None:
        return ()
    return tuple(sorted((as_text(key), as_int(value)) for key, value in counts.items()))


def _drive_graph(ctx: CapabilityContext) -> GraphRecord:
    graph = invoke_rest(
        ctx,
        step="CAP-OUT-04:graph",
        method="GET",
        path=f"/api/v1/novels/{ctx.novel_id}/kb/graph",
    )
    nodes = tuple(
        GraphNodeRef(
            id=as_text(response_field(node, "id")),
            label=as_text(response_field(node, "label")),
            entity_type=as_text(response_field(node, "entity_type")),
            degree=as_int(response_field(node, "degree")),
        )
        for node in as_list(response_field(graph, "nodes"), "node list")
    )
    edges = tuple(
        GraphEdgeRef(
            id=as_text(response_field(edge, "id")),
            source=as_text(response_field(edge, "source")),
            target=as_text(response_field(edge, "target")),
            rel_type=as_text(response_field(edge, "rel_type")),
            direction=as_text(response_field(edge, "direction")),
        )
        for edge in as_list(response_field(graph, "edges"), "edge list")
    )
    stats = response_field(graph, "stats")
    path: tuple[str, ...] | None = None
    path_length: int | None = None
    if len(nodes) >= 2:
        probed = invoke_rest(
            ctx,
            step="CAP-OUT-04:shortest-path",
            method="GET",
            path=f"/api/v1/novels/{ctx.novel_id}/kb/graph/shortest-path",
            params={"source_id": nodes[0].id, "target_id": nodes[1].id},
        )
        raw_path = response_field(probed, "path")
        path = None if raw_path is None else as_str_tuple(raw_path)
        path_length = as_opt_int(response_field(probed, "length"))
    return GraphRecord(
        nodes=nodes,
        edges=edges,
        entity_type_counts=_count_pairs(response_field(stats, "entity_type_counts")),
        rel_type_counts=_count_pairs(response_field(stats, "rel_type_counts")),
        isolated_count=as_int(response_field(stats, "isolated_count")),
        connected_components=as_int(response_field(stats, "connected_components")),
        path=path,
        path_length=path_length,
    )


class GraphDriver:
    """CAP-OUT-04 — graph data + BFS path between the first two nodes."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-OUT-04", ctx, _drive_graph)


OUT_DIRECTION_DRIVERS: Final[dict[str, type[CapabilityDriver]]] = {
    "CAP-OUT-01": EntryBrowseDriver,
    "CAP-OUT-02": EntrySearchDriver,
    "CAP-OUT-03": EntityDetailDriver,
    "CAP-OUT-04": GraphDriver,
    **SURFACES_OUT_DRIVERS,
    **ASSIST_OUT_DRIVERS,
}
"""cap_id → driver class for the whole ``out`` direction (registry-mirrored)."""
