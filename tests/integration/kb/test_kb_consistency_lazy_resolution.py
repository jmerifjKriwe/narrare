"""ADR-086 L15 integration pins — KB consistency-check endpoint vs. the cascades.

Real-chain proofs for the dual-lazy ``get_consistency_service`` wiring
(no service override): request validation precedes BOTH routing-cascade
resolutions, and an unconfigured provider surfaces as a LOUD typed 400.
The 422 node is the defect-class discriminator: pre-migration the eager
factory resolved KB_CONSISTENCY at dependency time — BEFORE body
validation — so an invalid body never yielded 422; with dual lazy wiring
the same request yields 422.

Mirrors ``tests/integration/kb/test_kb_worldbuilding_lazy_resolution.py``
(L19 convention).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestConsistencyLazyResolutionIntegration:
    """ADR-086 L15: validation → 422 first; unconfigured provider → 400."""

    async def test_consistency_check_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Malformed body → 422 with the REAL factory (no override).

        Both cascades are wired lazily, so the dependency no longer
        raises before body validation — ``refresh: "not-a-bool"``
        surfaces as 422 regardless of provider/DB state. (Pre-migration
        probe: the eager factory's KB_CONSISTENCY cascade raised the
        routing novel-guard at dependency time for the unknown novel —
        404, body validation never ran. That dependency-time preemption
        is the ADR-086 defect class this node pins shut.)
        """
        resp = await client.post(
            f"/api/v1/novels/{uuid4()}/kb/consistency-check",
            json={"refresh": "not-a-bool"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_consistency_check_400_when_provider_unconfigured(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid request + unconfigured provider → 400 (RULE-11 loud).

        Real chain, NO factory patch: BOTH cascades resolve at the
        service's first use — after the novel ownership gate — so a
        fresh user without a provider gets a loud typed 400, never a
        swallowed result. The novel is created first so the ownership
        gate passes and the cascades are what fail.
        """
        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "KB Consistency 400 Novel", "writing_language": "en"},
            headers=auth_headers,
        )
        assert novel_resp.status_code == 201
        novel_id = novel_resp.json()["id"]

        response = await client.post(
            f"/api/v1/novels/{novel_id}/kb/consistency-check",
            json={"refresh": True},
            headers=auth_headers,
        )

        assert response.status_code == 400
