"""WS-turn prompt supply tests — real-composer render per session mode.

Defect (proven by the R2-C2 probe): every WS writing turn raised
``PromptVariableError`` at compose on the real ``PromptComposer`` —
``WritingTurnService._build_prompt_context`` built a bare ``PromptContext``
that never supplied the SYSTEM variables demanded by the governed
``interactive_session`` / ``interview`` templates. Mock-composer unit tests
(``test_ws_turn_service.py`` RecordingComposer) masked the defect — the same
mock-masking class as the new_chapter draft fix (ac55a094) and the
inline_suggest fix (B').

Fix (mirrors ac55a094 / R2-A): the service assembles a ``WritingContext``
graceful-None (RULE-11: failure → empty values, turn proceeds), spreads the
``kb_context_extras`` SSOT (10 kb_* keys, ``None`` → ``""``), supplies
``chapter_outline`` / ``timeline_position`` / ``recent_chapters`` from the
assembled context, and supplies ``word_target`` for ``interactive_session``
only.

Probe evidence (real PromptRegistry + PromptComposer, /tmp/opencode
probe, 2026-09-11):

* ``interactive_session`` (WRITE intent) demand order:
  ``[kb_characters, kb_locations, chapter_outline, word_target]``.
* ``interview`` (CHAT intent, CHAT route has no optional_variables) demand
  order: ``[timeline_position, kb_context_warnings, kb_characters,
  kb_locations, kb_factions, kb_other, kb_relationships, kb_suggested,
  recent_chapters, chapter_outline, tone_instructions]``. All but
  ``tone_instructions`` are covered by the service supply;
  ``tone_instructions`` has no runtime owner on the WS path (it is resolved
  from DB settings by the tone resolver on the extend/rewrite routes) and is
  therefore declared optional on the CHAT route (RULE-11 graceful).

Golden invariant (mock-masking lesson): both modes must compose on the REAL
composer, and all KB-blind degradation paths (no assembler wired / empty
assembly / assembly failure) must render byte-identically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from narrare.writing.ws_turn_service import WritingTurnService
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import ModelRegistry, ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.routes import resolve_prompt_route
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.models import WritingContext

_USER_ID = uuid4()
_PROJECT_ID = uuid4()
_CHAPTER_ID = uuid4()
_SESSION_ID = uuid4()

_KB_SENTINEL = "### Character: Mara\nThe lighthouse keeper with salt-grey eyes."
_OUTLINE_SENTINEL = "ACT 2: the storm door opens onto the tidal cave."
_TIMELINE_SENTINEL = "Day 5 of the siege."
_RECENT_SENTINEL = "Ch 3: Mara found the brass key."

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class FakeAssembler:
    """Fake WritingContextAssembler — canned context or canned error."""

    def __init__(
        self,
        context: WritingContext | None = None,
        error: Exception | None = None,
    ) -> None:
        # RULE-11-mirroring default: a non-raising fake always yields a
        # context (KB-blind empty when none is supplied), matching the real
        # assembler contract ``assemble() -> WritingContext``.
        self._context: WritingContext = context if context is not None else WritingContext()
        self._error = error
        self.calls: list[dict[str, object]] = []

    async def assemble(self, **kwargs: object) -> WritingContext:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._context


def _capturing_registry() -> tuple[Mock, dict[str, str]]:
    """Mock ModelRegistry whose stream captures the composed prompts."""
    captured: dict[str, str] = {}

    async def fake_stream(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
        captured["system"] = str(kwargs["system_prompt"])
        captured["user"] = str(kwargs["user_prompt"])
        yield StreamChunk(text="ok", is_final=True, usage=TokenUsage(1, 2, 3))

    registry = Mock()
    registry.stream = Mock(side_effect=fake_stream)
    return registry, captured


def _make_service(
    context_assembler: WritingContextAssembler | FakeAssembler | None = None,
) -> tuple[WritingTurnService, dict[str, str]]:
    """Build a WritingTurnService with a REAL composer + capturing stream."""
    composer = PromptComposer(PromptRegistry())
    registry, captured = _capturing_registry()
    service = WritingTurnService(
        composer=composer,
        invocation_pipeline=InvocationPipeline(),
        registry=registry,
        config=ResolvedModelConfig(
            provider_name="test",
            model_id="test-model",
            temperature=0.7,
            max_tokens=2000,
        ),
        run_limit_resolver=DefaultRunLimitResolver(),
        # ADR-085 seam cast: FakeAssembler is duck-type-conformant
        # (async assemble(...) -> WritingContext) but not a nominal subclass.
        context_assembler=cast("WritingContextAssembler | None", context_assembler),
    )
    return service, captured


async def _run_turn(service: WritingTurnService, session_mode: str) -> list[StreamChunk]:
    return [
        chunk
        async for chunk in service.stream_turn(
            content="Continue the scene: Mara opens the lighthouse door.",
            session_mode=session_mode,
            user_id=_USER_ID,
            project_id=_PROJECT_ID,
            chapter_id=_CHAPTER_ID,
            session_id=_SESSION_ID,
        )
    ]


class TestWsTurnComposesOnRealComposer:
    """Both WS session modes must compose on the real composer (defect fix)."""

    async def test_interactive_session_turn_composes(self) -> None:
        """interactive_session (WRITE) streams without PromptVariableError."""
        service, captured = _make_service()
        chunks = await _run_turn(service, "interactive_session")
        assert any(c.text for c in chunks)
        assert len(captured["system"]) > 0
        assert captured["user"] == ("Continue the scene: Mara opens the lighthouse door.")

    async def test_interview_turn_composes(self) -> None:
        """interview_assisted (CHAT → interview template) streams cleanly."""
        service, captured = _make_service()
        chunks = await _run_turn(service, "interview_assisted")
        assert any(c.text for c in chunks)
        assert len(captured["system"]) > 0

    async def test_populated_context_renders_sentinels(self) -> None:
        """Assembled KB data reaches the composed system prompt."""
        context = WritingContext(
            kb_characters=_KB_SENTINEL,
            chapter_outline=_OUTLINE_SENTINEL,
            timeline_position=_TIMELINE_SENTINEL,
            recent_chapters=_RECENT_SENTINEL,
        )
        assembler = FakeAssembler(context=context)
        service, captured = _make_service(assembler)
        await _run_turn(service, "interactive_session")
        for sentinel in (
            _KB_SENTINEL,
            _OUTLINE_SENTINEL,
            _TIMELINE_SENTINEL,
            _RECENT_SENTINEL,
        ):
            assert sentinel in captured["system"], f"missing {sentinel!r}"


class TestWsTurnDegradationPaths:
    """KB-blind degradation paths render byte-identically (RULE-11)."""

    async def test_degradation_paths_byte_identical(self) -> None:
        """No assembler / empty assembly / assembly failure → same bytes."""
        service_none, captured_none = _make_service(None)
        await _run_turn(service_none, "interactive_session")

        service_empty, captured_empty = _make_service(WritingContextAssembler())
        await _run_turn(service_empty, "interactive_session")

        service_fail, captured_fail = _make_service(
            FakeAssembler(error=RuntimeError("db unavailable"))
        )
        await _run_turn(service_fail, "interactive_session")

        # Golden pin — KB-blind interactive_session system render
        # (empty WritingContext values, prompt v1.4.0), captured via the
        # service seam on the real composer: 3861 UTF-8 bytes / 3851 chars.
        golden = len(captured_none["system"].encode("utf-8"))
        assert golden == 3861
        assert captured_empty["system"] == captured_none["system"]
        assert captured_fail["system"] == captured_none["system"]

    async def test_assembly_failure_does_not_block_turn(self) -> None:
        """A raising assembler degrades to KB-blind — the turn proceeds."""
        assembler = FakeAssembler(error=RuntimeError("db unavailable"))
        service, _ = _make_service(assembler)
        chunks = await _run_turn(service, "interview_assisted")
        assert any(c.text for c in chunks)

    async def test_assembler_receives_turn_identifiers(self) -> None:
        """The assembler is called with the turn's project/chapter ids."""
        assembler = FakeAssembler(context=WritingContext())
        service, _ = _make_service(assembler)
        await _run_turn(service, "interactive_session")
        assert len(assembler.calls) == 1
        call = assembler.calls[0]
        assert call["project_id"] == _PROJECT_ID
        assert call["chapter_id"] == _CHAPTER_ID


class TestWsTurnWordTargetConditional:
    """word_target is demanded only by interactive_session (probe-proven)."""

    async def test_word_target_renders_for_interactive_session(self) -> None:
        context = WritingContext(word_target=1200)
        service, captured = _make_service(FakeAssembler(context=context))
        await _run_turn(service, "interactive_session")
        assert "1200" in captured["system"]

    async def test_interview_renders_without_word_target(self) -> None:
        """interview template has no {{word_target}} slot — supply is absent
        and the compose still succeeds."""
        context = WritingContext(word_target=1200)
        service, captured = _make_service(FakeAssembler(context=context))
        chunks = await _run_turn(service, "interview_assisted")
        assert any(c.text for c in chunks)
        assert "1200" not in captured["system"]


class TestChatRouteInterviewOptional:
    """CHAT route declares the ownerless interview slot optional."""

    def test_chat_route_declares_tone_instructions_optional(self) -> None:
        """tone_instructions has no WS-path runtime owner → CHAT route
        renders it as "" instead of raising PromptVariableError."""
        route = resolve_prompt_route(LLMIntent.CHAT, "interview")
        assert "tone_instructions" in route.optional_variables


class TestProductionWiring:
    """FO-4: both production construction sites wire a real assembler.

    The core ``WritingContextAssembler`` is a pure data transformation —
    the wiring pin therefore asserts the API-layer data-fetching subclass
    (``WsWritingContextAssembler``), not just ``is not None``.
    """

    def test_deps_ws_wires_real_context_assembler(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_writing_turn_service constructs the fetching assembler."""
        from narrare.writing.deps_ws import get_writing_turn_service
        from narrare.writing.ws_context_assembler import WsWritingContextAssembler

        monkeypatch.setattr(
            "narrare.writing.deps_ws.get_composer",
            lambda: MagicMock(spec=PromptComposer),
        )
        monkeypatch.setattr(
            "narrare.writing.deps_ws.get_invocation_pipeline",
            lambda: MagicMock(spec=InvocationPipeline),
        )
        monkeypatch.setattr(
            "narrare.writing.deps_ws.get_model_registry",
            lambda: MagicMock(spec=ModelRegistry),
        )
        config = ResolvedModelConfig(
            provider_name="test",
            model_id="test-model",
            temperature=0.7,
            max_tokens=2000,
        )

        service = get_writing_turn_service(config)

        assert isinstance(service._context_assembler, WsWritingContextAssembler)

    def test_ws_factory_wires_real_context_assembler(self) -> None:
        """build_writing_session_handler hands the fetching assembler to
        the turn service shared by dispatcher and message router."""
        from narrare.writing._ws_cache import InMemorySessionCache
        from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
        from narrare.writing.ws_context_assembler import WsWritingContextAssembler
        from narrare.writing.ws_factory import build_writing_session_handler
        from narrare.writing.ws_session_control_service import (
            WritingSessionControlService,
        )
        from narrare_core.writing.session_manager import SessionManager
        from narrare_core.writing.session_turn_state import SessionTurnStateStore

        cache = InMemorySessionCache()
        session_manager = SessionManager(cache=cache)
        turn_state = SessionTurnStateStore()
        active_registry = ActiveTurnRegistry()
        control_service = WritingSessionControlService(
            session_manager=session_manager,
            turn_state=turn_state,
            registry=active_registry,
        )

        handler = build_writing_session_handler(
            session_manager=session_manager,
            registry=active_registry,
            turn_state=turn_state,
            control_service=control_service,
            model_registry=MagicMock(spec=ModelRegistry),
            composer=MagicMock(spec=PromptComposer),
            config=ResolvedModelConfig(
                provider_name="test",
                model_id="test-model",
                temperature=0.7,
                max_tokens=2000,
            ),
            invocation_pipeline=MagicMock(spec=InvocationPipeline),
            run_limit_resolver=DefaultRunLimitResolver(),
        )

        turn_service = handler._message_router._direction_dispatcher._turn_service
        assert isinstance(turn_service._context_assembler, WsWritingContextAssembler)


@pytest.mark.parametrize("session_mode", ["interactive_session", "interview_assisted"])
async def test_both_modes_compose_without_assembler(session_mode: str) -> None:
    """Backward-compat pin: no assembler wired → graceful KB-blind turn."""
    service, _ = _make_service(None)
    chunks = await _run_turn(service, session_mode)
    assert any(c.text for c in chunks)
