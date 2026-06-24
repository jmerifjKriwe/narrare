"""Integration tests for PROMPT-003 prompt UX router (CR-AUFG-07-16).

Tests the three new endpoints:
- ``POST /api/v1/prompts/{prompt_id:path}/preview`` (provider-free)
- ``POST /api/v1/prompts/{prompt_id:path}/reset`` (metadata)
- ``POST /api/v1/prompts/{prompt_id:path}/live-test`` (provider-gated SSE)

The test user created by ``auth_headers`` has no AI provider configured,
so the live-test endpoint returns 503 (Service Unavailable). The 400 path
(unacknowledged token cost) is tested separately.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from narrare.prompts.schemas_prompt_ux import LiveTestStartedResponse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import pytest
    from httpx import AsyncClient

_PROMPT_ID = "writing/en/new_chapter"


class TestPreviewEndpoint:
    async def test_preview_returns_200_without_provider(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Preview is provider-free — no LLM, no tokens required."""
        resp = await client.post(
            f"/api/v1/prompts/{_PROMPT_ID}/preview",
            json={"variables": {"language": "en"}, "language": "en"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "system_prompt" in body
        assert "variables" in body
        assert "diagnostics" in body
        assert "cascade_source" in body

    async def test_preview_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """Preview requires authentication."""
        resp = await client.post(
            f"/api/v1/prompts/{_PROMPT_ID}/preview",
            json={"variables": {}, "language": "en"},
        )
        assert resp.status_code == 401


class TestResetEndpoint:
    async def test_reset_returns_metadata(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Reset returns effective_source + effective_content, not bare bool."""
        resp = await client.post(
            f"/api/v1/prompts/{_PROMPT_ID}/reset",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "reset" in body
        assert body["reset"] in {True, False}
        assert "effective_source" in body
        assert "effective_content" in body

    async def test_reset_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """Reset requires authentication."""
        resp = await client.post(
            f"/api/v1/prompts/{_PROMPT_ID}/reset",
        )
        assert resp.status_code == 401


class TestLiveTestEndpoint:
    async def test_live_test_sse_meta_contains_started_metadata(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The first SSE meta frame contains the validated start metadata."""

        class FakeLiveTestService:
            async def validate_live_test(
                self,
                prompt_id: str,
                request: object,
                *,
                user_id: str,
            ) -> LiveTestStartedResponse:
                return LiveTestStartedResponse(
                    prompt_id=prompt_id,
                    intent="writing",
                    model_id="test-model",
                    rate_limit_remaining=4,
                )

            async def stream_live_test(
                self,
                prompt_id: str,
                request: object,
                *,
                user_id: str,
                metadata: LiveTestStartedResponse,
            ) -> AsyncIterator[str]:
                yield f"event: meta\ndata: {metadata.model_dump_json()}\n\n"
                yield 'event: done\ndata: {"is_final": true}\n\n'
                yield "data: [DONE]\n\n"

        async def fake_get_live_test_service(session: object) -> FakeLiveTestService:
            return FakeLiveTestService()

        monkeypatch.setattr(
            "narrare.prompts.router_prompt_ux.get_live_test_service",
            fake_get_live_test_service,
        )

        resp = await client.post(
            f"/api/v1/prompts/{_PROMPT_ID}/live-test",
            json={
                "variables": {"language": "en"},
                "acknowledge_token_cost": True,
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        first_frame = resp.text.split("\n\n", maxsplit=1)[0]
        assert first_frame.startswith("event: meta\n")
        meta_payload = json.loads(first_frame.split("data: ", maxsplit=1)[1])
        assert meta_payload == {
            "prompt_id": _PROMPT_ID,
            "intent": "writing",
            "model_id": "test-model",
            "rate_limit_remaining": 4,
        }

    async def test_live_test_400_when_unacknowledged(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """acknowledge_token_cost=False → 400 before any provider call."""
        resp = await client.post(
            f"/api/v1/prompts/{_PROMPT_ID}/live-test",
            json={"variables": {}, "acknowledge_token_cost": False},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_live_test_503_when_no_provider(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """No provider configured → 503 (Service Unavailable).

        The test user created by ``auth_headers`` has no AI provider, so
        the resolver raises ``ConfigurationError`` → mapped to 503 by the
        route handler.
        """
        resp = await client.post(
            f"/api/v1/prompts/{_PROMPT_ID}/live-test",
            json={
                "variables": {"language": "en"},
                "acknowledge_token_cost": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 503

    async def test_live_test_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """Live test requires authentication."""
        resp = await client.post(
            f"/api/v1/prompts/{_PROMPT_ID}/live-test",
            json={"variables": {}, "acknowledge_token_cost": True},
        )
        assert resp.status_code == 401
