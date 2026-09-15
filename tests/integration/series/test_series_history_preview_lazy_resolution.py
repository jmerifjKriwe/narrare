"""ADR-086 L27 integration pins — series history preview vs. the cascades.

Real-chain proofs for the lazy ``get_series_history_preview_service``
wiring (no factory patch): request validation precedes the WRITE-intent
routing cascade's resolution AND the token-limits cascade. The preview
endpoint is a GET with no body — the only invalidatable input is the
path ``series_id`` (FastAPI solves sub-dependencies before raising
request-validation errors, so the eager factory's resolve preempted the
422 with ``NO_AI_PROVIDER`` 400 — captured as this slice's red-phase
probe evidence).

Mirrors ``tests/integration/series/test_series_voice_lazy_resolution.py``
(ADR-086 L28 convention). New file: the pin belongs to the slice
(per-slice regression contract).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestSeriesHistoryPreviewLazyResolutionIntegration:
    """ADR-086 L27: validation → 422 first; unconfigured provider → 400."""

    async def test_preview_422_with_invalid_series_id_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid path ``series_id`` → 422 with the REAL factory (no
        override).

        Both cascades are wired lazily, so the path-param validation
        error surfaces BEFORE the WRITE-intent routing resolve runs.
        Pre-migration this same request surfaced as the eager factory's
        400 (red-phase probe recorded in the L27 report).
        """
        resp = await client.get(
            "/api/v1/series/not-a-uuid/settings/context-preview",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_preview_400_when_provider_unconfigured(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid request + unconfigured provider → 400 loud (RULE-11).

        Real chain, NO factory patch, provider NOT seeded: the cascades
        cannot resolve, and the endpoint surfaces the typed
        ``NO_AI_PROVIDER`` 400 — never a swallowed or degraded result.
        The 400 fires at the service's first use — AFTER the
        series-ownership gate (hence the owned series created below,
        which keeps the gate green so the error provably originates at
        resolution, not at the gate).
        """
        series_resp = await client.post(
            "/api/v1/series",
            json={"title": "L27 Preview Series"},
            headers=auth_headers,
        )
        assert series_resp.status_code == 201
        series_id = series_resp.json()["id"]

        response = await client.get(
            f"/api/v1/series/{series_id}/settings/context-preview",
            headers=auth_headers,
        )

        assert response.status_code == 400
