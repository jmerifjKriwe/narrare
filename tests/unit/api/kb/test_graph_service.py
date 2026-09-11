"""Unit tests for GraphService.get_graph — node/edge serialization and filtering.

Tests graph construction, entity type filtering, and statistics computation
with faked dependencies (no I/O, no DB, no LLM).
"""

from __future__ import annotations

import types
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from narrare.kb.graph_schemas import GraphFilter
from narrare.kb.graph_service import GraphService

# ---------------------------------------------------------------------------
# Factory helpers — lightweight fakes for KBEntry and KBRelationship
# ---------------------------------------------------------------------------


def _make_entry(
    *,
    entity_type: str = "character",
    name: str = "Test Entity",
    novel_id: UUID | None = None,
    entry_id: UUID | None = None,
    status: str = "draft",
    tags: list[str] | None = None,
    metadata_: dict[str, object] | None = None,
) -> types.SimpleNamespace:
    """Create a minimal KBEntry-like object for testing."""
    return types.SimpleNamespace(
        id=entry_id or uuid4(),
        novel_id=novel_id or uuid4(),
        entity_type=entity_type,
        name=name,
        slug=name.lower().replace(" ", "-"),
        status=status,
        tags=tags,
        metadata_=metadata_,
    )


def _make_relationship(
    *,
    source_id: UUID | None = None,
    target_id: UUID | None = None,
    rel_type: str = "ally",
    label: str | None = None,
    direction: str = "directed",
) -> types.SimpleNamespace:
    """Create a minimal KBRelationship-like object for testing."""
    return types.SimpleNamespace(
        id=uuid4(),
        source_id=source_id or uuid4(),
        target_id=target_id or uuid4(),
        rel_type=rel_type,
        label=label,
        direction=direction,
    )


def _make_service(
    *,
    entries: list[types.SimpleNamespace] | None = None,
    total_count: int | None = None,
    relationships: list[types.SimpleNamespace] | None = None,
    adjacency: dict[str, set[str]] | None = None,
) -> tuple[GraphService, dict[str, AsyncMock]]:
    """Create a GraphService with faked dependencies.

    The novel-ownership gate (IDOR fix S9) is permissive by default:
    ``novel_repo.get_by_id`` always resolves a novel. Ownership behavior
    is covered by ``test_graph_suggest_consistency_ownership.py``.
    """
    kb_repo = AsyncMock()
    rel_repo = AsyncMock()
    novel_repo = AsyncMock()
    _entries = entries or []
    _total = total_count if total_count is not None else len(_entries)
    kb_repo.list_entries = AsyncMock(return_value=(_entries, _total))
    kb_repo.get_by_id = AsyncMock(return_value=None)
    _rels = relationships or []
    rel_repo.list_all_for_novel = AsyncMock(return_value=_rels)
    _adj = adjacency or {}
    rel_repo.get_adjacency_map = AsyncMock(return_value=_adj)
    novel_repo.get_by_id = AsyncMock(return_value=object())  # gate: caller owns it
    service = GraphService(kb_repo=kb_repo, rel_repo=rel_repo, novel_repo=novel_repo)
    return service, {"kb_repo": kb_repo, "rel_repo": rel_repo}


# ===========================================================================


class TestGetGraph:
    """Tests for GraphService.get_graph()."""

    async def test_get_graph_returns_nodes_and_edges(self) -> None:
        """Verify service returns all entries as nodes + all relationships as edges."""
        novel_id = uuid4()
        user_id = uuid4()
        e1 = _make_entry(name="Alice", entity_type="character", novel_id=novel_id)
        e2 = _make_entry(name="Bob", entity_type="character", novel_id=novel_id)
        rel = _make_relationship(source_id=e1.id, target_id=e2.id, rel_type="ally")

        adjacency = {str(e1.id): {str(e2.id)}, str(e2.id): {str(e1.id)}}

        service, _ = _make_service(
            entries=[e1, e2],
            relationships=[rel],
            adjacency=adjacency,
        )

        result = await service.get_graph(novel_id=novel_id, user_id=user_id)

        assert len(result.nodes) == 2
        assert len(result.edges) == 1
        assert result.nodes[0].label == "Alice"
        assert result.nodes[1].label == "Bob"
        assert result.edges[0].source == e1.id
        assert result.edges[0].target == e2.id
        assert result.edges[0].rel_type == "ally"

    async def test_get_graph_filters_by_entity_type(self) -> None:
        """Verify entity_types filter excludes non-matching entries and their edges."""
        novel_id = uuid4()
        user_id = uuid4()
        char1 = _make_entry(name="Alice", entity_type="character", novel_id=novel_id)
        char2 = _make_entry(name="Bob", entity_type="character", novel_id=novel_id)
        loc1 = _make_entry(name="Castle", entity_type="location", novel_id=novel_id)

        rel1 = _make_relationship(source_id=char1.id, target_id=loc1.id, rel_type="lives_in")
        rel2 = _make_relationship(source_id=char1.id, target_id=char2.id, rel_type="ally")

        adjacency = {
            str(char1.id): {str(loc1.id), str(char2.id)},
            str(char2.id): {str(char1.id)},
            str(loc1.id): {str(char1.id)},
        }

        service, _ = _make_service(
            entries=[char1, char2, loc1],
            relationships=[rel1, rel2],
            adjacency=adjacency,
        )

        graph_filter = GraphFilter(entity_types=["character"])
        result = await service.get_graph(novel_id=novel_id, user_id=user_id, filter=graph_filter)

        assert len(result.nodes) == 2
        assert all(n.entity_type == "character" for n in result.nodes)
        # Only edges where BOTH endpoints are in the node set should remain
        assert len(result.edges) == 1
        assert result.edges[0].rel_type == "ally"

    async def test_get_graph_computes_stats(self) -> None:
        """Verify stats: total_nodes, total_edges, nodes_by_type, isolated_nodes."""
        novel_id = uuid4()
        user_id = uuid4()
        e1 = _make_entry(name="Alice", entity_type="character", novel_id=novel_id)
        e2 = _make_entry(name="Bob", entity_type="character", novel_id=novel_id)
        e3 = _make_entry(name="Castle", entity_type="location", novel_id=novel_id)
        e4 = _make_entry(name="Orphan", entity_type="concept", novel_id=novel_id)

        rel1 = _make_relationship(source_id=e1.id, target_id=e2.id, rel_type="ally")
        rel2 = _make_relationship(source_id=e1.id, target_id=e3.id, rel_type="lives_in")

        adjacency = {
            str(e1.id): {str(e2.id), str(e3.id)},
            str(e2.id): {str(e1.id)},
            str(e3.id): {str(e1.id)},
            # e4 (Orphan) has no connections — isolated node
        }

        service, _ = _make_service(
            entries=[e1, e2, e3, e4],
            relationships=[rel1, rel2],
            adjacency=adjacency,
        )

        result = await service.get_graph(novel_id=novel_id, user_id=user_id)

        stats = result.stats
        assert stats.node_count == 4
        assert stats.edge_count == 2
        assert stats.isolated_count == 1  # Only e4 (Orphan)
        assert stats.entity_type_counts == {"character": 2, "location": 1, "concept": 1}
        assert stats.rel_type_counts == {"ally": 1, "lives_in": 1}
        # 2 connected components: {e1, e2, e3} and {e4}
        assert stats.connected_components == 2
