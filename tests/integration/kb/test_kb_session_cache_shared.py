"""Audit B05 regression — KB sessions survive across requests.

``get_kb_session_service`` built a fresh ``InMemorySessionCache`` per
request, so ``POST /kb/sessions`` returned 201 and the immediate
``GET /kb/sessions/{id}`` answered 404 (session invisible to the next
request's cache). The fix binds ONE cache on ``app.state`` at startup;
both requests now share it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestKBSessionCacheSharedAcrossRequests:
    async def test_create_then_get_roundtrip_with_real_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST 201 → GET 200 through the REAL factory (no service override)."""
        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "KB Session Cache Novel", "writing_language": "en"},
            headers=auth_headers,
        )
        assert novel_resp.status_code == 201
        novel_id = novel_resp.json()["id"]

        create_resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/sessions",
            json={"entity_type": "character"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        session_id = create_resp.json()["id"]

        get_resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/sessions/{session_id}",
            headers=auth_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == session_id
