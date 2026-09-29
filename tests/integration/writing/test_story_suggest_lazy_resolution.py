"""ADR-086 L34 integration pins — story-suggest endpoint vs. the cascades.

Real-chain proofs for the lazy ``get_story_suggest_service`` wiring. The
writing integration suites do not cover this endpoint elsewhere, so the
pin belongs to the slice. With the REAL factory (no fake override):

- invalid body → 422 before any cascade work (post-validation contract;
  the deferral proof itself lives in the unit deferral tests
  ``tests/unit/api/writing/test_story_suggest_lazy_resolution.py``),
- valid body + unknown novel → pre-header 404: the eager factory's
  uid-scoped novel guard, relocated into the service's ``validate_
  suggest`` first-use path per the planning guard ruling, keeps firing
  BEFORE the ``StreamingResponse`` is constructed (no SSE media type on
  the error response — gate-before-resolution, preserved).

The graceful no-provider surface is intentionally NOT pinned as a 400:
story-suggest is AI-optional (Pattern M-graceful) — an unconfigured
provider never raises at the seam; the preserved ``no_model_config``
outcome stays in-band (unit-pinned in the lazy-resolution suite).

Mirrors ``tests/integration/writing/test_extend_lazy_resolution.py``
(ADR-086 L32 convention).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from httpx import AsyncClient

_REAL_FACTORY = "narrare.writing.router_story_suggest.get_story_suggest_service"

_UNKNOWN_NOVEL_ID = "00000000-0000-0000-0000-000000000000"


class TestStorySuggestLazyResolutionIntegration:
    """ADR-086 L34: validation → 422 first; novel gate → pre-header 404."""

    async def test_story_suggest_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid body → 422 with the REAL factory (no fake override).

        The SUGGEST cascade is wired lazily, so body validation precedes
        any routing work on the request path.
        """
        from narrare.writing.deps_story_suggest import get_story_suggest_service

        with patch(_REAL_FACTORY, new=get_story_suggest_service):
            response = await client.post(
                f"/api/v1/writing/story-suggest/{_UNKNOWN_NOVEL_ID}",
                json={},
                headers=auth_headers,
            )

        assert response.status_code == 422

    async def test_story_suggest_404_pre_header_for_unknown_novel(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid body + unknown novel → 404 with NO SSE headers sent.

        The relocated uid-scoped novel guard in ``validate_suggest`` (the
        router's pre-stream seam) fires BEFORE the ``StreamingResponse``
        is constructed — gate-before-resolution preserved across the L34
        relocation (foreign ≡ unknown, anti-enumeration).
        """
        from narrare.writing.deps_story_suggest import get_story_suggest_service

        with patch(_REAL_FACTORY, new=get_story_suggest_service):
            response = await client.post(
                f"/api/v1/writing/story-suggest/{_UNKNOWN_NOVEL_ID}",
                json={
                    "novel_id": _UNKNOWN_NOVEL_ID,
                    "author_instructions": "Surprise me with a plot twist",
                },
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert "text/event-stream" not in response.headers.get("content-type", "")
