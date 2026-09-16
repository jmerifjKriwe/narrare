"""ADR-086 L35 integration pins — style-variant endpoint vs. the cascades.

Real-chain proofs for the lazy ``get_style_variant_service`` wiring. The
writing integration conftest patches the factory import site with a
fixed-runtime fake for the happy-path suites; these tests RE-PATCH the
import site with the REAL factory to pin the endpoint contract under
the production wiring:

- invalid body → 422 before any cascade work,
- valid body + unconfigured provider → loud 400 with NO SSE headers
  (the first-use composition fires inside ``validate_variant``, the
  router's pre-stream seam — pre-header proof per the ADR-086
  regression contract).

Scope note (honest baseline): the style-variant factory is called
INSIDE the endpoint body (post body-validation), so the 422 pin
documents the contract rather than demonstrating a migration flip —
the resolution-timing proof lives in the unit deferral tests
(``tests/unit/api/writing/test_deps_style_variants_lazy_wiring.py``).
The loud-400 pin proves the first-use composition propagates
un-swallowed on the real chain with the provider unseeded (same
premise as the L32/L33 pins: the test user has no provider
configuration).

Mirrors ``tests/integration/writing/test_extend_lazy_resolution.py``
(ADR-086 L32 convention). New file: the pin belongs to the slice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from httpx import AsyncClient

_REAL_FACTORY = "narrare.writing.router_style_variants.get_style_variant_service"

_SOURCE_TEXT = (
    "The old lighthouse keeper climbed the spiral stairs every evening "
    "to light the lamp before the fishing boats returned home."
)


class TestStyleVariantLazyResolutionIntegration:
    """ADR-086 L35: validation → 422 first; unconfigured provider → 400."""

    async def test_style_variant_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid body → 422 with the REAL factory (no fake override).

        The REWRITE cascades are wired lazily, so body validation
        precedes any routing/token-limit work on the request path.
        """
        from narrare.writing.deps_style_variants import get_style_variant_service

        with patch(_REAL_FACTORY, new=get_style_variant_service):
            response = await client.post(
                "/api/v1/writing/chapters/00000000-0000-0000-0000-000000000000"
                "/style-variants/regenerate",
                params={"novel_id": "00000000-0000-0000-0000-000000000001"},
                json={"source_text": "Too short"},
                headers=auth_headers,
            )

        assert response.status_code == 422

    async def test_style_variant_400_pre_header_when_provider_unconfigured(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid request + unconfigured provider → 400 loud, pre-header.

        Real chain, NO fake override, provider NOT seeded: the first-use
        composition inside ``validate_variant`` raises
        ``ConfigurationError`` (``NO_AI_PROVIDER``) BEFORE the router
        constructs the ``StreamingResponse`` — the error response must
        NOT carry the SSE media type (pre-header proof).
        """
        from narrare.writing.deps_style_variants import get_style_variant_service

        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "L35 Style Variant Novel", "language": "en"},
            headers=auth_headers,
        )
        assert novel_resp.status_code == 201
        novel_id = novel_resp.json()["id"]

        chapter_resp = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": "L35 Style Variant Chapter", "position": 1},
            headers=auth_headers,
        )
        assert chapter_resp.status_code == 201
        chapter_id = chapter_resp.json()["id"]

        with patch(_REAL_FACTORY, new=get_style_variant_service):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
                params={"novel_id": novel_id},
                json={"source_text": _SOURCE_TEXT, "style_variant": "leaner"},
                headers=auth_headers,
            )

        assert response.status_code == 400
        assert "text/event-stream" not in response.headers.get("content-type", "")
