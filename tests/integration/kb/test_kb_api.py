"""Integration tests for KB API endpoints.

Tests full CRUD cycle for entries and relationships,
plus search and error handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _register_user(client: AsyncClient) -> dict[str, str]:
    """Register a user and return auth headers."""
    email = f"kb-test-{uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpassword123",
            "display_name": "KB Test User",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


async def _create_novel(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    """Create a novel and return its ID."""
    resp = await client.post(
        "/api/v1/novels",
        json={"title": "KB Test Novel", "language": "en"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Entry CRUD
# ---------------------------------------------------------------------------


class TestCreateEntry:
    async def test_create_entry_returns_201(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={
                "entity_type": "character",
                "name": "John Smith",
                "body": "A brave hero.",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["entity_type"] == "character"
        assert data["name"] == "John Smith"
        assert data["slug"] == "john-smith"
        assert data["status"] == "draft"

    async def test_create_entry_with_metadata(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={
                "entity_type": "character",
                "name": "Jane Doe",
                "metadata": {"age": 30, "role": "protagonist"},
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["metadata"]["age"] == 30

    async def test_create_entry_invalid_type_returns_422(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character"},
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_create_entry_without_auth_returns_401(self, client: AsyncClient) -> None:
        resp = await client.post(
            f"/api/v1/novels/{uuid4()}/kb/entries",
            json={"entity_type": "character", "name": "Test"},
        )
        assert resp.status_code == 401


class TestListEntries:
    async def test_list_entries_returns_paginated(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        # Create two entries
        for name in ["Alice", "Bob"]:
            await client.post(
                f"/api/v1/novels/{novel_id}/kb/entries",
                json={"entity_type": "character", "name": name},
                headers=headers,
            )

        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/entries",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_entries_filter_by_type(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character", "name": "Hero"},
            headers=headers,
        )
        await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "location", "name": "Castle"},
            headers=headers,
        )

        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/entries",
            params={"entity_type": "character"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["entity_type"] == "character"


class TestSearchEntries:
    async def test_search_by_name(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character", "name": "Dragon Slayer"},
            headers=headers,
        )

        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/entries/search",
            params={"q": "Dragon"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert "Dragon" in data["items"][0]["name"]


class TestGetEntry:
    async def test_get_existing_entry(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        create = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character", "name": "Fetch Me"},
            headers=headers,
        )
        entry_id = create.json()["id"]

        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/entries/{entry_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Fetch Me"

    async def test_get_nonexistent_returns_404(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/entries/{uuid4()}",
            headers=headers,
        )
        assert resp.status_code == 404


class TestUpdateEntry:
    async def test_update_entry_name(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        create = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character", "name": "Old Name"},
            headers=headers,
        )
        entry_id = create.json()["id"]

        resp = await client.patch(
            f"/api/v1/novels/{novel_id}/kb/entries/{entry_id}",
            json={"name": "New Name"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"


class TestDeleteEntry:
    async def test_delete_entry_returns_204(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        create = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character", "name": "Delete Me"},
            headers=headers,
        )
        entry_id = create.json()["id"]

        resp = await client.delete(
            f"/api/v1/novels/{novel_id}/kb/entries/{entry_id}",
            headers=headers,
        )
        assert resp.status_code == 204

        # Verify it's gone
        get = await client.get(
            f"/api/v1/novels/{novel_id}/kb/entries/{entry_id}",
            headers=headers,
        )
        assert get.status_code == 404


# ---------------------------------------------------------------------------
# Relationship CRUD
# ---------------------------------------------------------------------------


class TestCreateRelationship:
    async def test_create_relationship_returns_201(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        # Create two entries
        source = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character", "name": "Alice"},
            headers=headers,
        )
        target = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character", "name": "Bob"},
            headers=headers,
        )

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/relationships",
            json={
                "source_id": source.json()["id"],
                "target_id": target.json()["id"],
                "rel_type": "ally",
                "direction": "mutual",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["rel_type"] == "ally"
        assert data["direction"] == "mutual"


class TestListRelationships:
    async def test_list_relationships_for_entry(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        source = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character", "name": "Alice"},
            headers=headers,
        )
        target = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character", "name": "Bob"},
            headers=headers,
        )

        await client.post(
            f"/api/v1/novels/{novel_id}/kb/relationships",
            json={
                "source_id": source.json()["id"],
                "target_id": target.json()["id"],
                "rel_type": "ally",
            },
            headers=headers,
        )

        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/entries/{source.json()['id']}/relationships",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["rel_type"] == "ally"


class TestDeleteRelationship:
    async def test_delete_relationship_returns_204(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        source = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character", "name": "Alice"},
            headers=headers,
        )
        target = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character", "name": "Bob"},
            headers=headers,
        )

        create = await client.post(
            f"/api/v1/novels/{novel_id}/kb/relationships",
            json={
                "source_id": source.json()["id"],
                "target_id": target.json()["id"],
                "rel_type": "ally",
            },
            headers=headers,
        )
        rel_id = create.json()["id"]

        resp = await client.delete(
            f"/api/v1/novels/{novel_id}/kb/relationships/{rel_id}",
            headers=headers,
        )
        assert resp.status_code == 204


class TestInverseSuggestion:
    async def test_get_inverse_suggestion(self, client: AsyncClient) -> None:
        headers = await _register_user(client)
        novel_id = await _create_novel(client, headers)

        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/relationships/inverse-suggestion",
            params={"rel_type": "mentor"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rel_type"] == "mentor"
        assert data["inverse"] == "mentee"
