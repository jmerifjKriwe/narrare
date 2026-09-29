"""ADR-086 L12 integration pins — chat SSE endpoint vs. the cascade.

Real-chain proofs for the lazy ``get_chat_service`` wiring (no factory
patch): request-body validation precedes the CHAT cascade's resolution,
and an unconfigured provider surfaces as a loud pre-header 400 — the
router awaits ``service.ask(...)`` (the service's first-use resolve)
BEFORE constructing the ``StreamingResponse``, so the error response
carries NO ``text/event-stream`` header (regression contract #6).

Pre-migration the eager factory resolved at DI time, so the invalid-body
request surfaced as the factory's ``NO_AI_PROVIDER`` 400 (red-phase
premise codified in the former eager assertions of
``tests/unit/api/chat/test_dependencies_user_routing.py``).

Mirrors ``tests/integration/series/test_series_voice_lazy_resolution.py``
(ADR-086 L28 convention). New file: the pin belongs to the slice
(per-slice regression contract).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestChatLazyResolutionIntegration:
    """ADR-086 L12: validation → 422 first; unconfigured provider → 400."""

    async def test_chat_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid body → 422 with the REAL factory (no override).

        The CHAT cascade is wired lazily, so an empty ``message``
        (``min_length=1``) is rejected by body validation BEFORE the
        model-routing resolve runs. Pre-migration this same request
        surfaced as the eager factory's 400.
        """
        resp = await client.post(
            "/api/v1/chat",
            json={"message": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_chat_400_pre_header_when_provider_unconfigured(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid request + unconfigured provider → 400 with NO SSE headers.

        Real chain, NO factory patch, provider NOT seeded: the routing
        cascade cannot resolve, and the endpoint surfaces the typed
        ``NO_AI_PROVIDER`` 400. Project-less chat (``project_id`` omitted)
        skips the project tiers, so the 400 provably originates at the
        first-use resolve, not at a gate — and because ``ask()`` runs
        before the ``StreamingResponse``, the SSE media type is absent.
        """
        resp = await client.post(
            "/api/v1/chat",
            json={"message": "Hello!"},
            headers=auth_headers,
        )

        assert resp.status_code == 400
        assert "text/event-stream" not in resp.headers.values()
