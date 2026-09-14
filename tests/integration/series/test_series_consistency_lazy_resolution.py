"""ADR-086 L26 integration pins — series consistency endpoint vs. the cascade.

Real-chain proofs for the lazy ``get_series_consistency_service`` wiring (no
factory patch): request validation precedes the CONSISTENCY cascade's
resolution.

Shared-chain caveat (documented, ledger-tracked): the check endpoint's
route chains ``get_series_drift_persistence_service``, which Depends-chains
BOTH run-service factories — consistency (lazy as of L26) AND voice-drift
(still eager until L29 lands). Until L29, the voice-drift factory's eager
resolve runs at wiring time for every request on this endpoint; the 422 pin
therefore seeds a provider so that eager resolve succeeds and validation is
free to reject the invalid body (it stays green after L29 defers that
resolve too). The unconfigured-provider pin surfaces the typed 400 from the
shared chain — post-L29 the consistency first-use resolve (after the
ownership gates) becomes its only source.

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


async def _seed_provider(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Configure a provider + user-default model via the settings API.

    Makes the per-user routing cascade resolvable, so the (still eager)
    voice-drift sibling factory in the shared dependency chain succeeds
    instead of preempting validation with 400.
    """
    provider_resp = await client.post(
        "/api/v1/settings/ai/providers",
        json={"provider_name": "anthropic", "api_key": "sk-ant-test-key-12345678"},
        headers=auth_headers,
    )
    assert provider_resp.status_code == 201
    provider_id = provider_resp.json()["id"]

    settings_resp = await client.patch(
        "/api/v1/settings/ai",
        json={"default_provider_id": provider_id, "default_model": "test-model"},
        headers=auth_headers,
    )
    assert settings_resp.status_code == 200


class TestSeriesConsistencyLazyResolutionIntegration:
    """ADR-086 L26: validation → 422 first; unconfigured provider → 400."""

    async def test_check_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid body → 422 with the REAL factory (no override).

        The consistency cascade is wired lazily, so an invalid ``novel_id``
        in the body is rejected by validation BEFORE the model-routing
        resolve runs. Pre-migration this same request surfaced as the
        eager factory's 400. The provider is seeded so the still-eager
        voice-drift sibling (L29 debt) does not preempt validation first.
        """
        await _seed_provider(client, auth_headers)

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
        While the voice-drift sibling factory is still eager (L29) the
        400 fires at wiring time; once L29 lands it fires at the
        consistency service's first use — after the series-ownership +
        novel-membership gates — with identical status. Post-L29 this
        pin is the endpoint-level loudness proof for THIS slice.
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

        response = await client.post(
            f"/api/v1/series/{series_id}/consistency/check",
            json={"novel_id": novel_resp.json()["id"]},
            headers=auth_headers,
        )

        assert response.status_code == 400
