"""Integration tests for the notes endpoints (NOTES-001 §5).

CRUD + filters + tags endpoint + ownership/404/422 paths. Embedding dispatch
runs through the real wiring but is fire-and-forget (RULE-11): without a
configured provider the background task fails and logs — CRUD assertions are
unaffected either way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestListAndCreate:
    async def test_create_and_list_roundtrip(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        create = await client.post(
            "/api/v1/notes",
            json={"content": "First thought", "note_type": "idea", "tags": ["Plot"]},
            headers=auth_headers,
        )
        assert create.status_code == 201
        body = create.json()
        assert body["content"] == "First thought"
        assert body["note_type"] == "idea"
        assert body["tags"] == ["plot"]  # normalized

        listing = await client.get("/api/v1/notes", headers=auth_headers)
        assert listing.status_code == 200
        assert [n["id"] for n in listing.json()] == [body["id"]]

    async def test_list_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/notes")
        assert response.status_code == 401

    async def test_scope_violation_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        novel = await client.post("/api/v1/novels", json={"title": "N"}, headers=auth_headers)
        series = await client.post("/api/v1/series", json={"title": "S"}, headers=auth_headers)
        response = await client.post(
            "/api/v1/notes",
            json={
                "content": "x",
                "novel_id": novel.json()["id"],
                "series_id": series.json()["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestFilters:
    async def test_filter_by_type_tag_and_q(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post(
            "/api/v1/notes", json={"content": "a", "note_type": "question"}, headers=auth_headers
        )
        await client.post(
            "/api/v1/notes", json={"content": "b", "tags": ["world"]}, headers=auth_headers
        )
        by_type = await client.get(
            "/api/v1/notes", params={"note_type": "question"}, headers=auth_headers
        )
        assert [n["content"] for n in by_type.json()] == ["a"]
        by_tag = await client.get("/api/v1/notes", params={"tag": "world"}, headers=auth_headers)
        assert [n["content"] for n in by_tag.json()] == ["b"]
        by_q = await client.get("/api/v1/notes", params={"q": "b"}, headers=auth_headers)
        assert [n["content"] for n in by_q.json()] == ["b"]


class TestTagsEndpoint:
    async def test_distinct_tags_with_prefix(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post(
            "/api/v1/notes", json={"content": "a", "tags": ["plot", "world"]}, headers=auth_headers
        )
        await client.post(
            "/api/v1/notes", json={"content": "b", "tags": ["Plot Twist"]}, headers=auth_headers
        )
        response = await client.get("/api/v1/notes/tags", params={"q": "pl"}, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["tags"] == ["plot", "plot twist"]


class TestDetailUpdateDelete:
    async def test_get_patch_delete_lifecycle(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        create = await client.post(
            "/api/v1/notes", json={"content": "original"}, headers=auth_headers
        )
        note_id = create.json()["id"]

        detail = await client.get(f"/api/v1/notes/{note_id}", headers=auth_headers)
        assert detail.status_code == 200

        patch = await client.patch(
            f"/api/v1/notes/{note_id}", json={"content": "edited"}, headers=auth_headers
        )
        assert patch.status_code == 200
        assert patch.json()["content"] == "edited"

        delete = await client.delete(f"/api/v1/notes/{note_id}", headers=auth_headers)
        assert delete.status_code == 204

        gone = await client.get(f"/api/v1/notes/{note_id}", headers=auth_headers)
        assert gone.status_code == 404

    async def test_patch_missing_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.patch(
            "/api/v1/notes/00000000-0000-0000-0000-000000000000",
            json={"content": "x"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_patch_conflicting_scope_returns_422_not_500(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """T7 review carry-over: service-level ScopeError (merged PATCH state)
        must map to a typed HTTP error, never surface as 500.

        The PATCH body alone is schema-valid (only ``series_id`` set); the
        scope invariant trips on the MERGED state — stored ``novel_id`` plus
        the patch — inside the service, which is not a NarrareError, so it
        needs the dedicated app-level ScopeError handler.
        """
        import uuid as uuid_module

        novel = await client.post("/api/v1/novels", json={"title": "N"}, headers=auth_headers)
        create = await client.post(
            "/api/v1/notes",
            json={"content": "scoped", "novel_id": novel.json()["id"]},
            headers=auth_headers,
        )
        assert create.status_code == 201

        response = await client.patch(
            f"/api/v1/notes/{create.json()['id']}",
            json={"series_id": str(uuid_module.uuid4())},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestSearch:
    async def test_search_without_provider_returns_lexical_mode(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """RULE-11 regression: no embedding provider → lexical, no 500."""
        await client.post(
            "/api/v1/notes", json={"content": "The aunt is the culprit"}, headers=auth_headers
        )
        response = await client.post(
            "/api/v1/notes/search", json={"query": "aunt"}, headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "lexical"
        assert [r["content"] for r in body["results"]] == ["The aunt is the culprit"]
        assert body["results"][0]["similarity"] is None

    async def test_search_respects_type_filter(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post(
            "/api/v1/notes",
            json={"content": "alpha", "note_type": "question"},
            headers=auth_headers,
        )
        await client.post(
            "/api/v1/notes", json={"content": "beta", "note_type": "idea"}, headers=auth_headers
        )
        response = await client.post(
            "/api/v1/notes/search",
            json={"query": "a", "note_type": "idea"},
            headers=auth_headers,
        )
        assert [r["content"] for r in response.json()["results"]] == ["beta"]

    async def test_search_empty_query_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/notes/search", json={"query": ""}, headers=auth_headers
        )
        assert response.status_code == 422

    async def test_search_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/notes/search", json={"query": "x"})
        assert response.status_code == 401
