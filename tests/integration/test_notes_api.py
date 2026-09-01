"""Integration tests for the notes endpoints (NOTES-001 §5).

CRUD + filters + tags endpoint + ownership/404/422 paths. Embedding dispatch
runs through the real wiring but is fire-and-forget (RULE-11): without a
configured provider the background task fails and logs — CRUD assertions are
unaffected either way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def _second_user_headers(db_session: AsyncSession) -> dict[str, str]:
    """Auth headers for a second, distinct user (cross-user tests, B1).

    Real ``User`` row on the app's overridden session (the notes FK requires
    it) plus a JWT signed with the app's settings — mirrors ``auth_headers``.
    """
    import uuid
    from datetime import UTC, datetime

    from narrare._app.config import get_settings
    from narrare.auth.models import User
    from narrare.auth.security import create_access_token

    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(),
        email=f"notes-b-{uuid.uuid4().hex[:12]}@example.com",
        hashed_password="not-a-real-hash",
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    await db_session.flush()
    settings = get_settings()
    token = create_access_token(
        subject=str(user.id),
        secret_key=settings.secret_key,
        expires_minutes=settings.access_token_expire_minutes,
    )
    return {"Authorization": f"Bearer {token}"}


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


class TestCrossUserIsolation:
    """B1 review pin: user A's notes are invisible and immutable to user B.

    Foreign resources answer EXACTLY like unknown ones (404, identical body
    shape — anti-enumeration); foreign links are rejected with 404, never
    201/500. A-side controls keep each empty-B assertion non-vacuous.
    """

    async def test_other_user_get_patch_delete_get_404_like_unknown(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        create = await client.post(
            "/api/v1/notes", json={"content": "secret of A"}, headers=auth_headers
        )
        assert create.status_code == 201
        note_id = create.json()["id"]
        headers_b = await _second_user_headers(db_session)
        unknown_id = "00000000-0000-0000-0000-000000000000"

        patch_body = {"json": {"content": "hijacked"}}
        variants: list[tuple[str, dict[str, Any]]] = [
            ("GET", {}),
            ("PATCH", patch_body),
            ("DELETE", {}),
        ]
        for method, extra in variants:
            foreign = await client.request(
                method, f"/api/v1/notes/{note_id}", headers=headers_b, **extra
            )
            control = await client.request(
                method, f"/api/v1/notes/{unknown_id}", headers=headers_b, **extra
            )

            assert foreign.status_code == control.status_code == 404
            assert set(foreign.json()) == set(control.json()) == {"detail", "code"}
            assert foreign.json()["code"] == control.json()["code"] == "NOT_FOUND"

    async def test_other_user_list_and_search_find_nothing(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        import uuid

        needle = f"quartz-{uuid.uuid4().hex[:10]}"
        content = f"A secret {needle} note"
        create = await client.post("/api/v1/notes", json={"content": content}, headers=auth_headers)
        assert create.status_code == 201
        headers_b = await _second_user_headers(db_session)

        listing_b = await client.get("/api/v1/notes", headers=headers_b)
        assert listing_b.status_code == 200 and listing_b.json() == []

        filtered_b = await client.get("/api/v1/notes", params={"q": needle}, headers=headers_b)
        assert filtered_b.json() == []

        search_b = await client.post(
            "/api/v1/notes/search", json={"query": needle}, headers=headers_b
        )
        assert search_b.status_code == 200
        assert search_b.json()["results"] == []

        # Non-vacuous control: the same search DOES surface the note for A.
        search_a = await client.post(
            "/api/v1/notes/search", json={"query": needle}, headers=auth_headers
        )
        assert [r["content"] for r in search_a.json()["results"]] == [content]

    async def test_other_user_scoped_lists_empty_for_foreign_novel_and_series(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel = await client.post("/api/v1/novels", json={"title": "N-A"}, headers=auth_headers)
        series = await client.post("/api/v1/series", json={"title": "S-A"}, headers=auth_headers)
        novel_id, series_id = novel.json()["id"], series.json()["id"]
        for payload in (
            {"content": "in novel", "novel_id": novel_id},
            {"content": "in series", "series_id": series_id},
        ):
            linked = await client.post("/api/v1/notes", json=payload, headers=auth_headers)
            assert linked.status_code == 201
        headers_b = await _second_user_headers(db_session)

        # Control: the scope params are live — A sees exactly the linked note.
        by_novel_a = await client.get(
            "/api/v1/notes", params={"novel_id": novel_id}, headers=auth_headers
        )
        assert [n["content"] for n in by_novel_a.json()] == ["in novel"]
        by_series_a = await client.get(
            "/api/v1/notes", params={"series_id": series_id}, headers=auth_headers
        )
        assert [n["content"] for n in by_series_a.json()] == ["in series"]

        by_novel_b = await client.get(
            "/api/v1/notes", params={"novel_id": novel_id}, headers=headers_b
        )
        assert by_novel_b.json() == []
        by_series_b = await client.get(
            "/api/v1/notes", params={"series_id": series_id}, headers=headers_b
        )
        assert by_series_b.json() == []

    async def test_other_user_cannot_link_foreign_novel_or_series(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel = await client.post("/api/v1/novels", json={"title": "N-A"}, headers=auth_headers)
        series = await client.post("/api/v1/series", json={"title": "S-A"}, headers=auth_headers)
        novel_id, series_id = novel.json()["id"], series.json()["id"]
        headers_b = await _second_user_headers(db_session)
        own = await client.post("/api/v1/notes", json={"content": "b own"}, headers=headers_b)
        assert own.status_code == 201
        note_id = own.json()["id"]

        # CREATE with a foreign novel_id/series_id: 404, never 201, never 500.
        for note in (
            {"content": "x", "novel_id": novel_id},
            {"content": "x", "series_id": series_id},
        ):
            response = await client.post("/api/v1/notes", json=note, headers=headers_b)
            assert response.status_code == 404
            assert response.json()["code"] == "NOT_FOUND"

        # PATCH of B's OWN note with a foreign link: 404 on the merged state.
        for patch in ({"novel_id": novel_id}, {"series_id": series_id}):
            response = await client.patch(f"/api/v1/notes/{note_id}", json=patch, headers=headers_b)
            assert response.status_code == 404
            assert response.json()["code"] == "NOT_FOUND"

        # Nothing was silently created; B's note survives untouched.
        listing_b = await client.get("/api/v1/notes", headers=headers_b)
        assert [n["content"] for n in listing_b.json()] == ["b own"]
        detail = (await client.get(f"/api/v1/notes/{note_id}", headers=headers_b)).json()
        assert detail["novel_id"] is None and detail["series_id"] is None
