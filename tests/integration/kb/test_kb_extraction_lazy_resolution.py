"""ADR-086 L16 integration pins — extraction endpoint vs. the routing cascade.

Real-chain proofs for the lazy `get_extraction_service` wiring (no service
override): request validation precedes resolution, and an unconfigured
provider surfaces as a LOUD typed 400 — never the route's broad 500
(``router_extraction.py`` re-raises ``NarrareError`` for exactly this).

Mirrors ``tests/integration/generation/test_generation_api.py`` (L14
convention). Split from ``test_kb_extraction_api.py`` per RULE-04 (the
additions crossed the 400-line hard limit there).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestExtractionLazyResolutionIntegration:
    """ADR-086 L16: validation → 422 first; unconfigured provider → 400."""

    async def test_extract_422_with_invalid_uuid_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Malformed path → 422 with the REAL factory (no override).

        The cascade is wired lazily, so a malformed novel_id never
        reaches — nor is it preempted by — the model-routing resolve,
        regardless of provider/DB state.
        """
        resp = await client.post(
            f"/api/v1/novels/not-a-uuid/kb/extract/{uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_extract_400_when_provider_unconfigured(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid path + unconfigured provider → 400 (RULE-11 loud).

        Real chain, NO factory patch: the routing cascade resolves at the
        service's first use — after the ownership gate — so a fresh user
        without a provider gets a loud typed 400, never a swallowed
        result or the route's broad 500. The novel is created first so
        the gate passes and the cascade is what fails; the chapter id is
        never consulted (resolution precedes the chapter load).
        """
        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "KB Extraction 400 Novel", "writing_language": "en"},
            headers=auth_headers,
        )
        assert novel_resp.status_code == 201
        novel_id = novel_resp.json()["id"]

        response = await client.post(
            f"/api/v1/novels/{novel_id}/kb/extract/{uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 400
