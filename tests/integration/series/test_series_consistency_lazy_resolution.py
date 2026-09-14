"""ADR-086 L26 integration pins — series consistency endpoint vs. the cascade.

Real-chain proofs for the lazy ``get_series_consistency_service`` wiring (no
factory patch): request validation precedes the CONSISTENCY cascade's
resolution.

Shared-chain caveat (L26 → RESOLVED by L29): the check endpoint's route
chains ``get_series_drift_persistence_service``, which Depends-chains BOTH
run-service factories. Until L29 landed, the voice-drift sibling was still
eager and its wiring-time resolve forced this file's 422 pin to seed a
provider. With BOTH factories lazy (L29), no wiring-time resolve remains on
any series drift/consistency endpoint, so the 422 pin now proves the stronger
fact — validation precedes ANY routing cascade, unseeded — and the 400 pin's
error provably originates at the consistency service's first-use resolve
after the ownership gates (hence the member-novel join flow, which keeps the
gates green).

Mirrors ``tests/integration/kb/test_kb_extraction_lazy_resolution.py``
(ADR-086 L16 convention). New file: the additions would cross the size
comfort of the (future) series API test file and this pin belongs to the
slice (RULE-04 / per-slice regression contract).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestSeriesConsistencyLazyResolutionIntegration:
    """ADR-086 L26: validation → 422 first; unconfigured provider → 400."""

    async def test_check_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid body → 422 with the REAL factory (no override).

        Both factories in the drift-persistence chain wire their cascades
        lazily (consistency since L26, voice-drift since L29), so an
        invalid ``novel_id`` in the body is rejected by validation BEFORE
        any routing cascade runs — with NO provider seeded. Pre-L26 this
        same request surfaced as the eager consistency factory's 400;
        while the voice-drift sibling was still eager (L26-L28) the pin
        needed a provider seed to keep that sibling's wiring-time resolve
        from preempting validation first.
        """
        resp = await client.post(
            f"/api/v1/series/{uuid4()}/consistency/check",
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
        Since L29 (both chain factories lazy) the 400 fires at the
        consistency service's first use — after the series-ownership +
        novel-membership gates (hence the member-novel join flow below,
        which keeps the gates green so the error provably originates at
        resolution, not at a gate). While the voice-drift sibling was
        still eager, the 400 fired at wiring time instead (same status,
        earlier timing — the L26 caveat, now closed).
        """
        series_resp = await client.post(
            "/api/v1/series",
            json={"title": "L26 Consistency Series"},
            headers=auth_headers,
        )
        assert series_resp.status_code == 201
        series_id = series_resp.json()["id"]

        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "L26 Consistency Novel", "writing_language": "en"},
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
            f"/api/v1/series/{series_id}/consistency/check",
            json={"novel_id": novel_id},
            headers=auth_headers,
        )

        assert response.status_code == 400
