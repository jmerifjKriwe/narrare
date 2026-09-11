"""Integration tests for rewrite SSE streaming — format, modes, and error scenarios.

Split from test_rewrite_api.py per RULE-04 (file size limit).

Tests:
- SSE protocol correctness (data: prefix, [DONE] sentinel)
- <alternative> XML tag structure in streamed output
- Mode variations: voice with character_id, custom with instructions
- Multiple alternatives (count parameter)
- LLM failure mid-stream error handling

LLM calls are mocked via dependency override in conftest.py.

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_novel_with_chapter(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> tuple[str, str]:
    """Create a novel and a chapter, return (novel_id, chapter_id)."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Test Novel for Rewrite Streaming", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "Test Chapter", "position": 1},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    return novel_id, chapter_id


def _parse_sse_events(body: str) -> list[dict[str, object]]:
    """Parse SSE body into a list of event data dicts."""
    events: list[dict[str, object]] = []
    for line in body.split("\n"):
        if line.startswith("data: ") and line != "data: [DONE]":
            events.append(json.loads(line[6:]))
    return events


# Minimal valid selection text (>=50 chars)
_SELECTION_TEXT = (
    "The old house stood at the end of the lane, its windows dark "
    "and unseeing. A cold wind blew through the broken shutters."
)


# ---------------------------------------------------------------------------
# Tests: SSE protocol correctness
# ---------------------------------------------------------------------------


class TestRewriteSSEProtocol:
    async def test_sse_events_have_data_prefix(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Every SSE event line starts with 'data: ' prefix."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "tone",
                "count": 1,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

        non_empty_lines = [line for line in response.text.split("\n") if line.strip()]
        assert len(non_empty_lines) > 0, "Expected at least one SSE event"

        for line in non_empty_lines:
            assert line.startswith("data: "), f"SSE line does not start with 'data: ': {line!r}"

    async def test_sse_stream_ends_with_done_sentinel(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """SSE stream terminates with 'data: [DONE]' sentinel."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "tone",
                "count": 1,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

        non_empty_lines = [line for line in response.text.split("\n") if line.strip()]
        assert non_empty_lines[-1] == "data: [DONE]", (
            f"Expected last SSE line to be 'data: [DONE]', got: {non_empty_lines[-1]!r}"
        )

    async def test_alternative_tag_has_label_attribute(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """<alternative> tags include a label attribute."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "tone",
                "count": 1,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

        # The streamed output should contain <alternative label="...">
        assert "<alternative label=" in response.text, (
            "Expected <alternative> tag with label attribute in response"
        )


# ---------------------------------------------------------------------------
# Tests: Mode variations — voice and custom happy paths
# ---------------------------------------------------------------------------


class TestRewriteModeVariations:
    async def test_voice_mode_with_character_id_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite with voice mode and character_id returns SSE stream."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "voice",
                "character_id": str(uuid.uuid4()),
                "count": 1,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # Verify it produces valid SSE events
        events = _parse_sse_events(response.text)
        assert len(events) > 0

    async def test_custom_mode_with_instructions_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite with custom mode and custom_instructions returns SSE."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "custom",
                "custom_instructions": "Make this more ominous and foreboding",
                "count": 1,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = _parse_sse_events(response.text)
        assert len(events) > 0

    async def test_rewrite_count_3_accepted(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite with count=3 returns valid SSE stream."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "style",
                "count": 3,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

        events = _parse_sse_events(response.text)
        assert len(events) > 0

        # Should still have proper structure: context_meta, text chunks, is_final
        final_events = [e for e in events if e.get("is_final")]
        assert len(final_events) > 0, "Expected at least one is_final event"


# ---------------------------------------------------------------------------
# Tests: LLM failure during streaming
# ---------------------------------------------------------------------------


class TestRewriteStreamErrors:
    async def test_llm_failure_stream_ends_without_is_final(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """When LLM fails, SSE stream ends with [DONE] but no is_final event."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        # Build a failing service factory for this test only.
        # Overrides the autouse conftest patch for the duration of this call.
        async def _make_failing_service(session, user_id, project_id=None):  # type: ignore[no-untyped-def]
            from narrare._app.dependencies import get_composer
            from narrare.chapters.repository import ChapterRepository
            from narrare.novels.repository import NovelRepository
            from narrare.writing.repository import GenerationRepository
            from narrare.writing.rewrite_service import RewriteService
            from narrare_core.llm import ResolvedModelConfig
            from narrare_core.writing.context_assembler import WritingContextAssembler
            from narrare_core.writing.draft_processor import DraftProcessor
            from narrare_core.writing.pipeline import WritingPipeline
            from tests.fakes.fake_llm_gateway import FakeModelRegistry

            repo = GenerationRepository(session)
            fake_registry = FakeModelRegistry()
            # Simulate LLM failure during streaming
            fake_registry.raises(RuntimeError("LLM connection lost"))
            config = ResolvedModelConfig(
                provider_name="test",
                model_id="test-model",
                temperature=0.7,
                max_tokens=4000,
            )
            pipeline = WritingPipeline(
                registry=fake_registry,
                composer=get_composer(),
                context_assembler=WritingContextAssembler(),
                draft_processor=DraftProcessor(),
            )
            return RewriteService(
                repo=repo,
                pipeline=pipeline,
                draft_processor=DraftProcessor(),
                config=config,
                chapter_repo=ChapterRepository(session),
                novel_repo=NovelRepository(session),
            )

        with patch(
            "narrare.writing.router_rewrite.get_rewrite_service",
            new=_make_failing_service,
        ):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/rewrite",
                params={"novel_id": str(novel_id)},
                json={
                    "selection_text": _SELECTION_TEXT,
                    "mode": "tone",
                    "count": 1,
                },
                headers=auth_headers,
            )

        # The endpoint should still return 200 (SSE stream starts before LLM
        # call), but the stream should not contain an is_final event.
        assert response.status_code == 200

        # Verify [DONE] sentinel is still present
        assert "data: [DONE]" in response.text

        # Verify no is_final event (LLM failed before completing)
        events = _parse_sse_events(response.text)
        final_events = [e for e in events if e.get("is_final")]
        assert len(final_events) == 0, "Expected no is_final event when LLM fails mid-stream"
