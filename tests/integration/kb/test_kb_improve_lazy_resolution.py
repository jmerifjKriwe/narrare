"""ADR-086 L17 integration pins — improve endpoints vs. the routing cascade.

Real-chain proofs for the lazy `get_kb_improve_service` wiring (no service
override): request validation precedes resolution, and an unconfigured
provider surfaces as a LOUD typed 400. The apply node is the defect-class
discriminator: pre-migration the eager factory's routing cascade raised at
dependency time — BEFORE body validation — so an invalid body never
yielded 422; with lazy wiring the same request yields 422 (validation
first).

Mirrors ``tests/integration/kb/test_kb_extraction_lazy_resolution.py``
(L16 convention).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestImproveLazyResolutionIntegration:
    """ADR-086 L17: validation → 422 first; unconfigured provider → 400."""

    async def test_improve_apply_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Malformed body → 422 with the REAL factory (no override).

        The cascade is wired lazily, so the dependency no longer raises
        before body validation — ``suggestion_ids: "not-a-list"`` surfaces
        as 422 regardless of provider/DB state. (Probed against a
        temporarily re-eagered factory: the same request then yields 404 —
        the cascade's novel guard raising at dependency time — body
        validation never ran. That dependency-time preemption is the
        ADR-086 defect class this node pins shut.)
        """
        resp = await client.post(
            f"/api/v1/novels/{uuid4()}/kb/entities/{uuid4()}/improve/apply",
            json={"suggestion_ids": "not-a-list"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_improve_400_when_provider_unconfigured(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid request + unconfigured provider → 400 (RULE-11 loud).

        Real chain, NO factory patch: the routing cascade resolves at the
        analyzer's first use — after the ownership and entry∈novel gates —
        so a fresh user without a provider gets a loud typed 400, never a
        swallowed result. The novel AND the entry are created first so both
        gates pass and the cascade is what fails.
        """
        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "KB Improve 400 Novel", "writing_language": "en"},
            headers=auth_headers,
        )
        assert novel_resp.status_code == 201
        novel_id = novel_resp.json()["id"]

        entry_resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entries",
            json={"entity_type": "character", "name": "Alice"},
            headers=auth_headers,
        )
        assert entry_resp.status_code == 201
        entry_id = entry_resp.json()["id"]

        response = await client.post(
            f"/api/v1/novels/{novel_id}/kb/entities/{entry_id}/improve",
            headers=auth_headers,
        )

        assert response.status_code == 400
