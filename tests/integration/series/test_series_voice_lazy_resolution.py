"""ADR-086 L28 integration pins — series voice endpoints vs. the cascade.

Real-chain proofs for the lazy ``get_series_voice_service`` wiring (no
factory patch): request validation precedes the VOICE cascade's
resolution. Unlike the consistency check endpoint (L26), the voice
routes chain NO sibling factories — the voice factory is the only
model-resolving dependency on the route, so the 422 pin needs no
provider seeding: pre-migration this same request surfaced as the eager
factory's ``NO_AI_PROVIDER`` 400 (captured as this slice's red-phase
probe evidence).

Mirrors ``tests/integration/series/test_series_consistency_lazy_resolution.py``
(ADR-086 L26 convention). New file: the pin belongs to the slice
(per-slice regression contract).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestSeriesVoiceLazyResolutionIntegration:
    """ADR-086 L28: validation → 422 first; unconfigured provider → 400."""

    async def test_profile_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid body → 422 with the REAL factory (no override).

        The voice cascade is wired lazily, so an invalid ``novel_id`` in
        the body is rejected by validation BEFORE the model-routing
        resolve runs. Pre-migration this same request surfaced as the
        eager factory's 400 (red-phase probe recorded in the L28
        report).
        """
        resp = await client.post(
            f"/api/v1/series/{uuid4()}/voice/profile",
            json={"novel_id": "not-a-uuid"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_profile_400_when_provider_unconfigured(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid request + unconfigured provider → 400 loud (RULE-11).

        Real chain, NO factory patch, provider NOT seeded: the routing
        cascade cannot resolve, and the endpoint surfaces the typed
        ``NO_AI_PROVIDER`` 400 — never a swallowed or degraded result.
        The 400 fires at the service's first use — AFTER the
        series-ownership + novel-membership gates (hence the member
        novel join flow below, which keeps the gates green so the error
        provably originates at resolution, not at a gate).
        """
        series_resp = await client.post(
            "/api/v1/series",
            json={"title": "L28 Voice Series"},
            headers=auth_headers,
        )
        assert series_resp.status_code == 201
        series_id = series_resp.json()["id"]

        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "L28 Voice Novel", "writing_language": "en"},
            headers=auth_headers,
        )
        assert novel_resp.status_code == 201
        novel_id = novel_resp.json()["id"]

        # Join the novel into the series so the membership gate passes
        # and the request reaches the first-use resolve.
        preview_resp = await client.post(
            f"/api/v1/series/{series_id}/novels",
            json={"novel_id": novel_id},
            headers=auth_headers,
        )
        assert preview_resp.status_code == 200
        apply_resp = await client.post(
            f"/api/v1/series/{series_id}/novels/{novel_id}/apply",
            json={"position": 1},
            headers=auth_headers,
        )
        assert apply_resp.status_code == 200

        response = await client.post(
            f"/api/v1/series/{series_id}/voice/profile",
            json={"novel_id": novel_id},
            headers=auth_headers,
        )

        assert response.status_code == 400
