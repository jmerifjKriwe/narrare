"""Integration tests for KB graph visualization endpoints.

Tests the /novels/{id}/kb/graph and /novels/{id}/kb/graph/shortest-path
endpoints with real database, real auth, mocked LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _register_user(client: AsyncClient) -> dict[str, str]:
    """Register a user and return auth headers."""
    email = f"graph-test-{uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpassword123",
            "display_name": "Graph Test User",
        },
    )
    assert resp.status_code == 201
    data: dict[str, Any] = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


async def _create_novel(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    """Create a novel and return its ID."""
    resp = await client.post(
        "/api/v1/novels",
        json={"title": "Graph Test Novel", "language": "en"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return str(resp.json()["id"])


async def _create_entry(
    client: AsyncClient,
    novel_id: str,
    auth_headers: dict[str, str],
    entity_type: str = "character",
    name: str = "Test Entity",
) -> dict[str, Any]:
    """Create a KB entry and return its JSON data."""
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/kb/entries",
        json={"entity_type": entity_type, "name": name},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_relationship(
    client: AsyncClient,
    novel_id: str,
    auth_headers: dict[str, str],
    source_id: str,
    target_id: str,
    rel_type: str = "ally",
) -> dict[str, Any]:
    """Create a KB relationship and return its JSON data."""
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/kb/relationships",
        json={
            "source_id": source_id,
            "target_id": target_id,
            "rel_type": rel_type,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# GET /novels/{id}/kb/graph
# ---------------------------------------------------------------------------


class TestGetGraph:
    async def test_graph_endpoint_returns_200(self, client: AsyncClient) -> None:
        """GET /novels/{id}/kb/graph returns valid graph response."""
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        # Create entries
        alice = await _create_entry(client, novel_id, headers, "character", "Alice")
        bob = await _create_entry(client, novel_id, headers, "character", "Bob")
        castle = await _create_entry(client, novel_id, headers, "location", "Castle")

        # Create relationships
        await _create_relationship(
            client, novel_id, headers, str(alice["id"]), str(bob["id"]), "ally"
        )
        await _create_relationship(
            client, novel_id, headers, str(alice["id"]), str(castle["id"]), "lives_in"
        )

        # Fetch graph
        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/graph",
            headers=headers,
        )
        assert resp.status_code == 200
        data: dict[str, Any] = resp.json()

        # Verify response structure
        assert "nodes" in data
        assert "edges" in data
        assert "stats" in data

        # Verify nodes
        assert len(data["nodes"]) == 3
        node_labels = {n["label"] for n in data["nodes"]}
        assert node_labels == {"Alice", "Bob", "Castle"}

        # Verify edges
        assert len(data["edges"]) == 2
        edge_types = {e["rel_type"] for e in data["edges"]}
        assert edge_types == {"ally", "lives_in"}

        # Verify stats
        stats = data["stats"]
        assert stats["node_count"] == 3
        assert stats["edge_count"] == 2
        assert "entity_type_counts" in stats
        assert "rel_type_counts" in stats

    async def test_graph_endpoint_returns_401_without_auth(self, client: AsyncClient) -> None:
        """GET /novels/{id}/kb/graph without auth returns 401."""
        novel_id = str(uuid4())
        resp = await client.get(f"/api/v1/novels/{novel_id}/kb/graph")
        assert resp.status_code == 401

    async def test_graph_endpoint_filters_by_entity_type(self, client: AsyncClient) -> None:
        """GET /novels/{id}/kb/graph?entity_types=character filters nodes."""
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        # Create entries of different types
        await _create_entry(client, novel_id, headers, "character", "Alice")
        await _create_entry(client, novel_id, headers, "character", "Bob")
        await _create_entry(client, novel_id, headers, "location", "Castle")

        # Fetch graph filtered to characters only
        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/graph",
            params={"entity_types": "character"},
            headers=headers,
        )
        assert resp.status_code == 200
        data: dict[str, Any] = resp.json()

        # Only character nodes should be present
        assert len(data["nodes"]) == 2
        assert all(n["entity_type"] == "character" for n in data["nodes"])


# ---------------------------------------------------------------------------
# GET /novels/{id}/kb/graph/shortest-path
# ---------------------------------------------------------------------------


class TestGetShortestPath:
    async def test_shortest_path_endpoint_returns_200(self, client: AsyncClient) -> None:
        """GET /novels/{id}/kb/graph/shortest-path returns valid path response."""
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        # Create a chain: Alice -> Bob -> Castle
        alice = await _create_entry(client, novel_id, headers, "character", "Alice")
        bob = await _create_entry(client, novel_id, headers, "character", "Bob")
        castle = await _create_entry(client, novel_id, headers, "location", "Castle")

        await _create_relationship(
            client, novel_id, headers, str(alice["id"]), str(bob["id"]), "ally"
        )
        await _create_relationship(
            client, novel_id, headers, str(bob["id"]), str(castle["id"]), "lives_in"
        )

        # Find path from Alice to Castle
        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/graph/shortest-path",
            params={"source_id": str(alice["id"]), "target_id": str(castle["id"])},
            headers=headers,
        )
        assert resp.status_code == 200
        data: dict[str, Any] = resp.json()

        # Verify path response
        assert data["path"] is not None
        assert data["length"] == 2  # Alice -> Bob -> Castle
        assert data["entity_names"] is not None
        # Path should include Alice, arrow, Bob, arrow, Castle
        assert "Alice" in data["entity_names"]
        assert "Castle" in data["entity_names"]

    async def test_shortest_path_endpoint_returns_401_without_auth(
        self, client: AsyncClient
    ) -> None:
        """GET /novels/{id}/kb/graph/shortest-path without auth returns 401."""
        novel_id = str(uuid4())
        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/graph/shortest-path",
            params={"source_id": str(uuid4()), "target_id": str(uuid4())},
        )
        assert resp.status_code == 401
