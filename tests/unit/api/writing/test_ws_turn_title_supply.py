"""WS-turn novel title/genre supply tests — HTTP parity with b2faa851 (#10).

The HTTP generation path supplies the ownership-checked novel title/genre
into ``pipeline.generate`` (b2faa851, pinned in
``test_writing_service_title_supply.py``). The WS turn path had the gap:
``WsWritingContextAssembler`` already fetches the novel row into
``WritingContext.project_title`` / ``.genre``, but
``build_prompt_context`` (``_ws_turn_support``) dropped them — the
governed ``interactive_session`` / ``interview`` templates rendered
``- Project:`` / ``- Genre:`` empty. The fix threads the assembled
metadata into the first-class ``PromptContext`` fields at that seam.

Pinned at two levels:

1. Seam level — a ``FakeAssembler``-supplied ``WritingContext`` renders
   the populated label lines on the real composer for BOTH session
   modes; missing metadata keeps the empty label render (RULE-11
   degradation unchanged).
2. Production wiring — the real ``WsWritingContextAssembler`` plus
   fake repositories (novel row present / missing) renders the populated
   lines through a real-composer turn.

RULE-04 note: new module because both natural host files
(``test_ws_context_assembler.py`` 373 lines,
``test_ws_turn_prompt_supply.py`` 391 lines) lack headroom under the
400-line hard limit; naming mirrors the HTTP-side
``test_writing_service_title_supply.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock
from uuid import uuid4

import pytest

from narrare.writing.ws_context_assembler import WsWritingContextAssembler
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.writing.models import WritingContext
from tests.unit.api.writing.test_ws_context_assembler import (
    _CHAPTER_ID,
    _NOVEL_TITLE,
    _PROJECT_ID,
    _chapter,
    _FakeRepos,
    _kb_entry,
)
from tests.unit.api.writing.test_ws_turn_prompt_supply import (
    FakeAssembler,
    _make_service,
    _run_turn,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class TestWsTurnNovelMetadataSupply:
    """Seam level: assembled title/genre reach the composed system prompt."""

    @pytest.mark.parametrize("session_mode", ["interactive_session", "interview_assisted"])
    async def test_populated_novel_metadata_renders(self, session_mode: str) -> None:
        """Populated WritingContext → `- Project:` / `- Genre:` lines."""
        context = WritingContext(project_title="Codex of Tides", genre="fantasy")
        service, captured = _make_service(FakeAssembler(context=context))
        await _run_turn(service, session_mode)
        assert "- Project: Codex of Tides" in captured["system"]
        assert "- Genre: fantasy" in captured["system"]

    async def test_missing_novel_metadata_renders_empty_labels(self) -> None:
        """No novel metadata → label lines render empty (RULE-11)."""
        service, captured = _make_service(FakeAssembler(context=WritingContext()))
        await _run_turn(service, "interactive_session")
        assert "- Project: \n" in captured["system"]
        assert "- Genre: \n" in captured["system"]


class TestWsAssemblerTurnMetadataRender:
    """Production wiring: the fetching assembler renders novel metadata."""

    @staticmethod
    async def _run_turn_with_novel(
        monkeypatch: pytest.MonkeyPatch,
        *,
        novel: SimpleNamespace | None,
    ) -> str:
        """Run a production-assembler turn and return the system prompt."""
        from narrare.writing._ws_turn_support import WritingTurnRuntime
        from narrare.writing.ws_turn_service import WritingTurnService

        repos = _FakeRepos(
            chapter=_chapter(chapter_id=_CHAPTER_ID, position=1),
            novel=novel,
            kb_entries=[_kb_entry()],
        )
        repos.install(monkeypatch)

        captured: dict[str, str] = {}

        async def fake_stream(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
            captured["system"] = str(kwargs["system_prompt"])
            yield StreamChunk(text="ok", is_final=True, usage=TokenUsage(1, 2, 3))

        registry = Mock()
        registry.stream = Mock(side_effect=fake_stream)

        async def static_runtime() -> WritingTurnRuntime:
            return WritingTurnRuntime(
                config=ResolvedModelConfig(
                    provider_name="test",
                    model_id="test-model",
                    temperature=0.7,
                    max_tokens=2000,
                ),
                context_assembler=WsWritingContextAssembler(),
            )

        service = WritingTurnService(
            composer=PromptComposer(PromptRegistry()),
            invocation_pipeline=InvocationPipeline(),
            registry=registry,
            runtime_factory=static_runtime,
            run_limit_resolver=DefaultRunLimitResolver(),
        )
        [
            chunk
            async for chunk in service.stream_turn(
                content="Continue the scene.",
                session_mode="interactive_session",
                user_id=uuid4(),
                project_id=_PROJECT_ID,
                chapter_id=_CHAPTER_ID,
                session_id=uuid4(),
            )
        ]
        return captured["system"]

    async def test_turn_renders_populated_project_and_genre(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Novel row present → `- Project:` / `- Genre:` render populated."""
        system = await self._run_turn_with_novel(
            monkeypatch,
            novel=SimpleNamespace(
                title=_NOVEL_TITLE,
                genre="fantasy",
                writing_language="en",
                tone="",
                story_structure="",
                series_id=None,
            ),
        )
        assert f"- Project: {_NOVEL_TITLE}" in system
        assert "- Genre: fantasy" in system

    async def test_turn_without_novel_renders_empty_metadata(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing novel row → label lines render empty (RULE-11)."""
        system = await self._run_turn_with_novel(monkeypatch, novel=None)
        assert f"- Project: {_NOVEL_TITLE}" not in system
        assert "- Project: \n" in system
        assert "- Genre: \n" in system
