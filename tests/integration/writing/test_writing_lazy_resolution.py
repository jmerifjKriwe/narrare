"""ADR-086 L37 integration pins — writing endpoints vs. the cascades.

Real-chain proofs for the lazy ``get_writing_service`` wiring. The
writing integration conftest patches the factory import sites with a
fixed-runtime fake for the happy-path suites; these tests RE-PATCH the
import sites with the REAL factories to pin the endpoint contract under
the production wiring:

- invalid body → 422 before any cascade work,
- valid body + unconfigured provider → the POST (request-row creation)
  succeeds WITHOUT resolving — the deferral proof — and the loud 400
  surfaces on the SSE stream call with NO SSE headers (the first-use
  composition fires inside ``validate_request_access``, the router's
  pre-stream seam — pre-header proof per the ADR-086 regression
  contract).

Scope note (honest baseline): the writing factory is called INSIDE the
endpoint bodies (post body-validation), so the 422 pin documents the
contract rather than demonstrating a migration flip — the
resolution-timing proof lives in the unit deferral tests
(``tests/unit/api/writing/test_deps_writing_lazy_wiring.py``). The
POST-200 + stream-400 pair IS the migration flip for this two-phase
endpoint: pre-migration the eager factory 400'd the POST itself;
post-migration the row is created and the unconfigured provider
surfaces as a loud pre-header 400 exactly where the model is first
used (same premise as the L32/L33/L35 pins: the test user has no
provider configuration).

Mirrors ``tests/integration/writing/test_style_variant_lazy_resolution.py``
(ADR-086 L35 convention). New file: the pin belongs to the slice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from httpx import AsyncClient

_REAL_FACTORY = "narrare.writing.router.get_writing_service"
_REAL_STREAM_FACTORY = "narrare.writing.router.get_writing_service_for_stream"


async def _create_novel_with_chapter(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> tuple[str, str]:
    """One owned novel + chapter via the real API (L35 helper shape)."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "L37 Writing Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "L37 Writing Chapter", "position": 1},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    return novel_id, chapter_id


class TestWritingLazyResolutionIntegration:
    """ADR-086 L37: validation → 422 first; unconfigured provider → 400
    pre-header on the stream, never on request-row creation."""

    async def test_generate_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid body → 422 with the REAL factory (no fake override).

        The WRITE cascades are wired lazily, so body validation precedes
        any routing/token-limit work on the request path.
        """
        from narrare.writing.deps_writing import get_writing_service

        with patch(_REAL_FACTORY, new=get_writing_service):
            response = await client.post(
                "/api/v1/writing/chapters/00000000-0000-0000-0000-000000000000/generate",
                params={"novel_id": "00000000-0000-0000-0000-000000000001"},
                # word_target below the schema floor (ge=100) → 422.
                json={"mode": "full_draft", "word_target": 50},
                headers=auth_headers,
            )

        assert response.status_code == 422

    async def test_generate_defers_resolution_and_stream_400s_pre_header(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid request + unconfigured provider → POST creates the row
        (200 — the cascades were NOT consulted), then the SSE stream
        call surfaces the loud 400 BEFORE any headers: the first-use
        composition inside ``validate_request_access`` raises
        ``ConfigurationError`` (``NO_AI_PROVIDER``) and the error
        response must NOT carry the SSE media type (pre-header proof).
        """
        from narrare.writing.deps_writing import get_writing_service
        from narrare.writing.deps_writing_stream import get_writing_service_for_stream

        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        with (
            patch(_REAL_FACTORY, new=get_writing_service),
            patch(_REAL_STREAM_FACTORY, new=get_writing_service_for_stream),
        ):
            start_resp = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/generate",
                params={"novel_id": novel_id},
                json={
                    "mode": "full_draft",
                    "prompt": "Write a dramatic opening scene",
                    "tone": "dramatic",
                    "language": "en",
                },
                headers=auth_headers,
            )

            assert start_resp.status_code == 200, (
                "request-row creation must not resolve the cascades (ADR-086 L37 deferral)"
            )
            request_id = start_resp.json()["request_id"]

            stream_resp = await client.get(
                f"/api/v1/writing/generation/{request_id}/stream",
                headers=auth_headers,
            )

        assert stream_resp.status_code == 400
        assert "text/event-stream" not in stream_resp.headers.get("content-type", "")
