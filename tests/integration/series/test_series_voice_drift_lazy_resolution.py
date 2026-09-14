"""ADR-086 L29 integration pins — series voice-drift endpoint vs. the cascade.

Real-chain proofs for the lazy ``get_series_voice_drift_service`` wiring (no
factory patch): request validation precedes the VOICE cascade's resolution.
Like the voice routes (L28), the drift route's ONLY model-resolving wiring
becomes lazy with this slice — the 422 pin needs no provider seeding:
pre-migration this same request surfaced as the eager factory's
``NO_AI_PROVIDER`` 400 (captured as this slice's red-phase probe evidence).

This slice ALSO resolves the L26 shared-chain caveat: with both factories in
the drift-persistence chain lazy, no wiring-time resolve remains on any
series drift/consistency endpoint.

Mirrors ``tests/integration/series/test_series_voice_lazy_resolution.py``
(ADR-086 L28 convention). New file: the pin belongs to the slice
(per-slice regression contract).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestSeriesVoiceDriftLazyResolutionIntegration:
    """ADR-086 L29: validation → 422 first; unconfigured provider → 400."""

    async def test_check_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid body → 422 with the REAL factory (no override).

        The voice-drift cascade is wired lazily, so an invalid ``novel_id``
        in the body is rejected by validation BEFORE the model-routing
        resolve runs. Pre-migration this same request surfaced as the
        eager factory's 400 (red-phase probe recorded in the L29 report).
        """
        resp = await client.post(
            f"/api/v1/series/{uuid4()}/voice-drift/check",
            json={"novel_id": "not-a-uuid"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_check_400_when_provider_unconfigured(
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
            json={"title": "L29 Voice Drift Series"},
            headers=auth_headers,
        )
        assert series_resp.status_code == 201
        series_id = series_resp.json()["id"]

        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "L29 Voice Drift Novel", "writing_language": "en"},
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
            f"/api/v1/series/{series_id}/voice-drift/check",
            json={"novel_id": novel_id},
            headers=auth_headers,
        )

        assert response.status_code == 400
