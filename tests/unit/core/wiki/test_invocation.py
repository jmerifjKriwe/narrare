"""Unit tests for ``compose_wiki_invocation`` (ADR-048 Mode 2).

The helper bridges wiki agent calls to the invocation pipeline. When the
pipeline is ``None`` it is skipped (backward-compatible default); failures
inside ``compose_invocation`` are swallowed (RULE-11 graceful degradation).
``compose_invocation`` is monkeypatched so no real pipeline is needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import LLMIntent
from narrare_core.wiki import invocation
from narrare_core.wiki.manual_injection import (
    WIKI_CHAPTER_GENERATION_MANUAL_INJECTION,
    WIKI_ENTITY_GENERATION_MANUAL_INJECTION,
)

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import PromptInvocationContext


def _patch_recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, object]]:
    """Patch ``compose_invocation`` to record its keyword arguments."""
    recorded: list[dict[str, object]] = []

    async def _fake_compose(
        *,
        invocation_pipeline: object,
        invocation_context: PromptInvocationContext,
        manual_injection: object,
    ) -> None:
        recorded.append(
            {
                "pipeline": invocation_pipeline,
                "feature_id": invocation_context.feature_id,
                "manual_injection": manual_injection,
                "project_id": invocation_context.project_id,
            }
        )

    monkeypatch.setattr(invocation, "compose_invocation", _fake_compose)
    return recorded


class TestComposeWikiInvocationNonePipeline:
    @pytest.mark.asyncio
    async def test_none_pipeline_is_a_noop(self) -> None:
        """A None pipeline skips composition entirely (backward compat)."""
        await invocation.compose_wiki_invocation(None, "wiki_generate_entity", LLMIntent.GENERATE)


class TestComposeWikiInvocationDispatch:
    @pytest.mark.asyncio
    async def test_entity_feature_uses_entity_manual_injection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded = _patch_recorder(monkeypatch)
        pipeline = MagicMock(spec=InvocationPipeline)

        await invocation.compose_wiki_invocation(
            pipeline,
            "wiki_generate_entity",
            LLMIntent.GENERATE,
            project_id="novel-1",
        )

        assert len(recorded) == 1
        assert recorded[0]["feature_id"] == "wiki_generate_entity"
        assert recorded[0]["project_id"] == "novel-1"
        assert recorded[0]["manual_injection"] is WIKI_ENTITY_GENERATION_MANUAL_INJECTION

    @pytest.mark.asyncio
    async def test_chapter_feature_uses_chapter_manual_injection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded = _patch_recorder(monkeypatch)
        pipeline = MagicMock(spec=InvocationPipeline)

        await invocation.compose_wiki_invocation(
            pipeline, "wiki_generate_chapter", LLMIntent.GENERATE
        )

        assert len(recorded) == 1
        assert recorded[0]["feature_id"] == "wiki_generate_chapter"
        assert recorded[0]["manual_injection"] is WIKI_CHAPTER_GENERATION_MANUAL_INJECTION


class TestComposeWikiInvocationGracefulDegradation:
    @pytest.mark.asyncio
    async def test_composition_failure_is_swallowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _boom(
            *,
            invocation_pipeline: object,
            invocation_context: PromptInvocationContext,
            manual_injection: object,
        ) -> None:
            raise RuntimeError("pipeline exploded")

        monkeypatch.setattr(invocation, "compose_invocation", _boom)
        pipeline = MagicMock(spec=InvocationPipeline)

        # Must not raise — RULE-11 graceful degradation lets the agent proceed.
        await invocation.compose_wiki_invocation(
            pipeline, "wiki_generate_entity", LLMIntent.GENERATE
        )
