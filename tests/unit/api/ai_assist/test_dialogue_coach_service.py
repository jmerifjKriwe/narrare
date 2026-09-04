"""Tests for DialogueCoachService (RULE-03 contract conformance, RULE-13 run/stream).

Uses fakes for all I/O dependencies. The TestModel exercises the real
DialogueCoachAgent (Task 11) end-to-end through the service.

The DialogueCoachAgent's structured output is a tool call (``final_result``,
single ``DialogueCoachOutput`` schema). Per pydantic-ai 2.x (see
``tests/unit/core/agents/test_dialogue_coach_agent.py`` header note),
tool-mode output requires ``custom_output_args`` (a dict of tool-call
arguments), NOT ``custom_output_text`` (a plain JSON string).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai.models.test import TestModel

from narrare.ai_assist.schemas import DialogueCoachRequest
from narrare.ai_assist.service import DialogueCoachService
from narrare_core.ai_invocation.adaptive_context import AdaptiveContext


def _coach_output_args(*, adaptive_summary: str = "signals active") -> dict[str, Any]:
    """Build ``custom_output_args`` matching DialogueCoachOutput.

    Tool-mode output: the structured output is invoked as the ``final_result``
    tool, so TestModel must supply the call arguments as a dict, not a JSON
    string via ``custom_output_text``.
    """
    return {
        "issues": [
            {
                "issue_type": "voice_mismatch",
                "speaker": "Alice",
                "original_quote": '"Good morning."',
                "diagnosis": "Too formal for Alice.",
                "severity": "medium",
            }
        ],
        "adaptive_summary": adaptive_summary,
    }


class FakeChapterRepo:
    """Async fake ChapterRepository — returns a chapter with content."""

    class _Chapter:
        def __init__(self, novel_id: Any, content: str) -> None:
            self.id = uuid4()
            self.novel_id = novel_id
            self.content = content
            self.title = "Test Chapter"

    async def get(self, chapter_id: Any) -> Any:
        return self._Chapter(novel_id=uuid4(), content='"Hello," Alice said.')

    async def get_by_id(self, chapter_id: Any, novel_id: Any | None = None) -> Any:
        return self._Chapter(novel_id=uuid4(), content='"Hello," Alice said.')


class FakeNovelRepo:
    """Async fake NovelRepository — returns a novel with metadata.

    Plan-Bug #23: the service now loads the novel for access control +
    project metadata (title, genre, writing_language).
    """

    class _Novel:
        def __init__(self) -> None:
            self.id = uuid4()
            self.title = "Test Novel"
            self.genre = "Fantasy"
            self.writing_language = "en"

    async def get_by_id(self, novel_id: Any, user_id: Any | None = None) -> Any:
        return self._Novel()


class FakeComposer:
    """Async fake PromptComposer — returns a minimal composed prompt."""

    async def build(self, *args: Any, **kwargs: Any) -> Any:
        from narrare_core.prompts.composer import ComposedPrompt

        # user="" (empty) so the agent_runner falls back to build_run_prompt()
        # via the ``composed.user or build_run_prompt(...)`` expression.
        return ComposedPrompt(system="You are a dialogue coach.", user="")


class FakeModelRegistry:
    """Async fake ModelRegistry — returns the supplied TestModel."""

    def __init__(self, model: TestModel) -> None:
        self._model = model

    async def get_model(
        self,
        config: Any,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> TestModel:
        # api_key/base_url: per-user routing credentials (Task 4 migration) —
        # accepted for protocol fidelity with ModelRegistry.get_model; the
        # fake ignores them.
        _ = api_key, base_url
        return self._model


class FakeAdaptiveProvider:
    """Async fake AdaptiveContextProvider."""

    def __init__(self, context: AdaptiveContext | None = None) -> None:
        self._context = context or AdaptiveContext(
            user_id=uuid4(), project_id=uuid4(), source_summary="preferences"
        )
        self.snapshot_calls: list[tuple[Any, AdaptiveContext]] = []

    async def get_context(self, user_id: Any, project_id: Any) -> AdaptiveContext:
        return self._context

    async def get_settings(self, user_id: Any, project_id: Any) -> Any:
        from narrare_core.ai_invocation.adaptive_context import AdaptiveSettings

        return AdaptiveSettings()

    async def record_snapshot(
        self, invocation_id: Any, adaptive_context: AdaptiveContext, evidence_repo: Any
    ) -> None:
        self.snapshot_calls.append((invocation_id, adaptive_context))


def _make_service(*, model: TestModel | None = None) -> DialogueCoachService:
    return DialogueCoachService(
        chapter_repo=FakeChapterRepo(),  # type: ignore[arg-type]
        novel_repo=FakeNovelRepo(),  # type: ignore[arg-type]
        model_registry=FakeModelRegistry(model or TestModel()),  # type: ignore[arg-type]
        model_config=None,  # type: ignore[arg-type]
        composer=FakeComposer(),  # type: ignore[arg-type]
        invocation_pipeline=None,
        adaptive_provider=FakeAdaptiveProvider(),  # type: ignore[arg-type]
    )


class TestRun:
    """Non-streaming run() — returns the full DialogueCoachResponse."""

    @pytest.mark.asyncio
    async def test_returns_response_with_issues(self) -> None:
        model = TestModel(custom_output_args=_coach_output_args())
        service = _make_service(model=model)
        request = DialogueCoachRequest(
            selection_text='"Good morning," Alice said.',
            mode="analyze",
        )
        result = await service.run(chapter_id=uuid4(), user_id=uuid4(), request=request)
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "voice_mismatch"
        assert result.issues[0].speaker == "Alice"
        assert result.mode == "analyze"

    @pytest.mark.asyncio
    async def test_returns_adaptive_summary(self) -> None:
        model = TestModel(custom_output_args=_coach_output_args())
        service = _make_service(model=model)
        request = DialogueCoachRequest(selection_text='"Hi."', mode="analyze")
        result = await service.run(chapter_id=uuid4(), user_id=uuid4(), request=request)
        # adaptive_summary is surfaced (may be the LLM's or empty):
        assert isinstance(result.adaptive_summary, str)


class TestStream:
    """Streaming stream() — yields progress / result / done events."""

    @pytest.mark.asyncio
    async def test_yields_done_event_at_end(self) -> None:
        model = TestModel(custom_output_args=_coach_output_args())
        service = _make_service(model=model)
        request = DialogueCoachRequest(selection_text='"Hi."', mode="improve")

        events = []
        async for event in service.stream(chapter_id=uuid4(), user_id=uuid4(), request=request):
            events.append(event)

        # Last event MUST be terminal (done or error):
        assert events[-1].is_final is True
        assert events[-1].event in ("done", "error")

    @pytest.mark.asyncio
    async def test_yields_result_event_with_issues(self) -> None:
        model = TestModel(custom_output_args=_coach_output_args())
        service = _make_service(model=model)
        request = DialogueCoachRequest(selection_text='"Hi."', mode="analyze")

        result_events = []
        async for event in service.stream(chapter_id=uuid4(), user_id=uuid4(), request=request):
            if event.event == "result" and event.result is not None:
                result_events.append(event.result)

        assert len(result_events) >= 1
        assert len(result_events[0].issues) == 1


class TestInvocationIdPlumbing:
    """record_snapshot receives the real invocation_id (not chapter.id).

    ADR-069 Decision 11 correlation: the adaptive evidence row MUST be
    keyed on the invocation_id from ``compose_invocation`` so it joins
    against ``invocation_evidence.invocation_id``. The previous
    placeholder (``getattr(chapter, "id", chapter_id)``) would write a
    bogus key that never matches an evidence row.
    """

    @pytest.mark.asyncio
    async def test_snapshot_uses_chapter_id_when_pipeline_is_none(
        self,
    ) -> None:
        """Fallback path: no pipeline → invocation_id is None → chapter_id used.

        In the unit-test setup (``invocation_pipeline=None``),
        ``compose_invocation`` follows the backward-compat path that
        skips ``prepare()``, so ``invocation.prepared.context.invocation_id``
        is ``None``. The service falls back to ``chapter_id`` (still
        correlatable for testing; production always wires a pipeline).
        """
        model = TestModel(custom_output_args=_coach_output_args())
        provider = FakeAdaptiveProvider()
        service = DialogueCoachService(
            chapter_repo=FakeChapterRepo(),  # type: ignore[arg-type]
            novel_repo=FakeNovelRepo(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(model),  # type: ignore[arg-type]
            model_config=None,  # type: ignore[arg-type]
            composer=FakeComposer(),  # type: ignore[arg-type]
            invocation_pipeline=None,
            adaptive_provider=provider,  # type: ignore[arg-type]
        )
        chapter_id = uuid4()
        await service.run(
            chapter_id=chapter_id,
            user_id=uuid4(),
            request=DialogueCoachRequest(selection_text='"Hello," Alice said.', mode="analyze"),
        )
        assert len(provider.snapshot_calls) == 1
        # Fallback: invocation_id is None → service uses chapter_id.
        assert provider.snapshot_calls[0][0] == chapter_id

    @pytest.mark.asyncio
    async def test_prompt_helper_returns_invocation_id_alongside_prompt(
        self,
    ) -> None:
        """resolve_dialogue_coach_prompt returns (ComposedPrompt, UUID | None).

        Direct helper test — verifies the tuple contract independently of
        the service. With ``invocation_pipeline=None`` the id is None
        (the unit-test fallback path); production wiring mints a real id.
        """
        from narrare.ai_assist._prompt import resolve_dialogue_coach_prompt

        composed, invocation_id = await resolve_dialogue_coach_prompt(
            FakeComposer(),  # type: ignore[arg-type]
            None,
            project_id=uuid4(),
            user_id=uuid4(),
            language="en",
            project_title="Test",
            genre="Fantasy",
            selection_text='"Hi."',
            mode="analyze",
            characters=["Alice"],
            adaptive_extra={},
        )
        assert composed.system == "You are a dialogue coach."
        # No pipeline → prepare() skipped → invocation_id is None.
        assert invocation_id is None
