"""ADR-086 L31 integration pins — co-author endpoint vs. the cascades.

Real-chain proofs for the lazy ``get_coauthor_service`` wiring. The
writing integration conftest does NOT replace the co-author factory
(the N1 ownership-gate proof relies on the real chain), so these pins
run the production wiring directly:

- invalid body → 422 before any cascade work,
- valid body + unconfigured provider → loud 400 with NO SSE headers
  (the first-use composition fires inside ``validate_coauthor``, the
  router's pre-stream seam — pre-header proof per the ADR-086
  regression contract).

Scope note (honest baseline): the co-author factory is called INSIDE
the endpoint body (post body-validation), so the 422 pin documents the
contract rather than demonstrating a migration flip — the resolution-
timing proof lives in the unit deferral tests
(``tests/unit/api/writing/test_coauthor_service_lazy_resolution.py``).
The loud-400 pin proves the first-use composition propagates
un-swallowed on the real chain with the provider unseeded (same premise
as the L33 rewrite pin: the test user has no provider configuration).

Mirrors ``tests/integration/writing/test_rewrite_lazy_resolution.py``
(ADR-086 L33 convention). New file: the pin belongs to the slice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient

_REAL_FACTORY = "narrare.writing.router_coauthor.get_coauthor_service"

_SELECTION = (
    "The old lighthouse keeper climbed the spiral stairs every evening "
    "to light the lamp before the fishing boats returned home."
)


class TestCoauthorLazyResolutionIntegration:
    """ADR-086 L31: validation → 422 first; unconfigured provider → 400."""

    async def test_coauthor_422_with_invalid_body_on_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid body → 422 with the REAL factory (no fake override).

        The CO_AUTHOR cascades are wired lazily, so body validation
        precedes any routing/token-limit work on the request path.
        """
        response = await client.post(
            "/api/v1/writing/chapters/00000000-0000-0000-0000-000000000000/co-author",
            params={"novel_id": "00000000-0000-0000-0000-000000000001"},
            json={"selection_text": "x" * 60},
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_coauthor_400_pre_header_when_provider_unconfigured(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid request + unconfigured provider → 400 loud, pre-header.

        Real chain, NO fake override, provider NOT seeded: the first-use
        composition inside ``validate_coauthor`` raises
        ``ConfigurationError`` (``NO_AI_PROVIDER``) BEFORE the router
        constructs the ``StreamingResponse`` — the error response must
        NOT carry the SSE media type (pre-header proof).
        """
        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "L31 Coauthor Novel", "language": "en"},
            headers=auth_headers,
        )
        assert novel_resp.status_code == 201
        novel_id = novel_resp.json()["id"]

        chapter_resp = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": "L31 Coauthor Chapter", "position": 1},
            headers=auth_headers,
        )
        assert chapter_resp.status_code == 201
        chapter_id = chapter_resp.json()["id"]

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/co-author",
            params={"novel_id": novel_id},
            json={"selection_text": _SELECTION, "focus": ["word_choice"]},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "text/event-stream" not in response.headers.get("content-type", "")
