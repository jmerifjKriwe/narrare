"""Interview-draft novel title/genre supply tests (#10 re-slice).

Finding (from the #10 wave): ``InterviewDraftGenerator`` built a bare
``PromptContext`` — the governed ``new_chapter`` template rendered
``- Project:`` / ``- Genre:`` empty on the WS interview-draft path,
unlike the HTTP generation supply (b2faa851) and the WS-turn seam
(#10, ``_ws_turn_support``).

Probe-corrected premise: on the REAL composer the bare context does not
merely render empty metadata — composition RAISES ``PromptVariableError``
(required extras ``chapter_outline`` / ``kb_characters`` /
``kb_locations`` / ``word_target_line`` are unsupplied); the unit
suite's stub composers masked it.

R3 supplied the route-required extras as empty degrades plus an
ownership-resolved title/genre fetch at the dispatch seam. The
WS-draft-KB slice replaced that standalone fetch with the production
``WsWritingContextAssembler`` (chapter-optional; novel metadata comes
from the assembled ``WritingContext``, exactly like the WS-turn seam),
so the metadata now threads via ``writing_context`` and the dispatch
fetch runs through the assembler doubles.

Pinned at three levels:

1. Seam level — ``stream_draft`` threads the supplied ``WritingContext``
   metadata into the first-class ``PromptContext`` fields; the default
   degrades to empty.
2. Real-composer render — populated/degraded label lines render through
   the genuine composer cascade (no stub masking).
3. Production wiring — ``dispatch_interview_draft`` assembles the
   context and feeds the generator; a missing novel row and a session
   failure both degrade to empty metadata with the draft still
   completing (RULE-11).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import Mock

from narrare.writing._interview_draft import InterviewDraftGenerator
from narrare.writing._ws_cache import InMemorySessionCache
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.writing.models import WritingContext
from narrare_core.writing.session_manager import SessionManager
from tests.unit.api.writing._interview_draft_fakes import (
    RecordingComposer,
    identifiers,
    install_ws_fetch,
    make_config,
    make_generator,
    make_ws_novel,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from types import SimpleNamespace
    from uuid import UUID

    import pytest

    from narrare.writing.ws_streaming import StreamSender

_NOVEL_TITLE = "Codex of Tides"


async def _dispatch_stream(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
    """Stream stub for dispatch-level tests: text chunk then final chunk."""
    yield StreamChunk(text="A draft. ")
    yield StreamChunk(text="The end.", is_final=True, usage=TokenUsage(1, 2, 3))


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _CaptureSocket:
    """Minimal ``StreamSender`` double capturing sent frames."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_json(self, data: dict[str, object]) -> None:
        self.sent.append(data)


def _install_novel_fetch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    novel: SimpleNamespace | None,
    session_fails: bool = False,
) -> None:
    """Patch the WS assembler fetch bundle (WS-draft-KB seam).

    Kept as the import-compat name for ``test_ws_draft_regression``;
    the mechanics moved to the assembler doubles when the dispatch
    fetch site switched to ``WsWritingContextAssembler``.
    """
    install_ws_fetch(monkeypatch, novel=novel, session_fails=session_fails)


def _capturing_gateway() -> tuple[Mock, dict[str, str]]:
    """Gateway mock recording the ``system_prompt`` kwarg of ``stream``."""
    captured: dict[str, str] = {}

    async def fake_stream(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
        captured["system"] = str(kwargs["system_prompt"])
        yield StreamChunk(text="ok", is_final=True, usage=TokenUsage(1, 2, 3))

    gateway = Mock()
    gateway.stream = Mock(side_effect=fake_stream)
    return gateway, captured


def _real_composer_generator(
    gateway: Mock,
) -> tuple[InterviewDraftGenerator, SessionManager]:
    """Generator wired with the REAL composer + pipeline (no stub masking)."""
    session_manager = SessionManager(cache=InMemorySessionCache())
    generator = InterviewDraftGenerator(
        session_manager=session_manager,
        registry=gateway,
        composer=cast("PromptComposer", PromptComposer(PromptRegistry())),
        config=make_config(),
        invocation_pipeline=InvocationPipeline(),
        run_limit_resolver=DefaultRunLimitResolver(),
    )
    return generator, session_manager


async def _seeded_session(
    session_manager: SessionManager,
    user_id: UUID,
    project_id: UUID,
    chapter_id: UUID,
) -> UUID:
    """Create a session with a minimal interview transcript."""
    session_id = await session_manager.create_session(chapter_id, project_id, user_id)
    await session_manager.add_message(session_id, "user", "A story about tides")
    await session_manager.add_message(session_id, "assistant", "What happens?")
    return session_id


# ---------------------------------------------------------------------------
# 1. Seam level — metadata threading
# ---------------------------------------------------------------------------


class TestStreamDraftMetadataThreading:
    """stream_draft carries supplied metadata into the PromptContext."""

    async def test_stream_draft_threads_populated_novel_metadata(self) -> None:
        """Supplied title/genre land in the first-class PromptContext fields."""
        generator, session_manager, _, composer = make_generator()
        chapter_id, user_id, project_id = identifiers()
        session_id = await _seeded_session(session_manager, user_id, project_id, chapter_id)

        _ = [
            c
            async for c in generator.stream_draft(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
                writing_context=WritingContext(project_title=_NOVEL_TITLE, genre="fantasy"),
            )
        ]

        assert composer.last_context is not None
        assert composer.last_context.project_title == _NOVEL_TITLE
        assert composer.last_context.genre == "fantasy"
        assert composer.last_context.mode == "new_chapter"

    async def test_stream_draft_defaults_degrade_to_empty_metadata(self) -> None:
        """No metadata args → empty first-class fields (pre-existing shape)."""
        generator, session_manager, _, composer = make_generator()
        chapter_id, user_id, project_id = identifiers()
        session_id = await _seeded_session(session_manager, user_id, project_id, chapter_id)

        _ = [
            c
            async for c in generator.stream_draft(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
            )
        ]

        assert composer.last_context is not None
        assert composer.last_context.project_title == ""
        assert composer.last_context.genre == ""


# ---------------------------------------------------------------------------
# 2. Real-composer render (no stub masking)
# ---------------------------------------------------------------------------


class TestDraftRenderOnRealComposer:
    """The draft prompt renders on the genuine composer cascade."""

    async def test_populated_metadata_renders_label_lines(self) -> None:
        """Real composer renders `- Project:` / `- Genre:` populated."""
        gateway, captured = _capturing_gateway()
        generator, session_manager = _real_composer_generator(gateway)
        chapter_id, user_id, project_id = identifiers()
        session_id = await _seeded_session(session_manager, user_id, project_id, chapter_id)

        _ = [
            c
            async for c in generator.stream_draft(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
                writing_context=WritingContext(project_title=_NOVEL_TITLE, genre="fantasy"),
            )
        ]

        assert f"- Project: {_NOVEL_TITLE}" in captured["system"]
        assert "- Genre: fantasy" in captured["system"]

    async def test_missing_metadata_renders_empty_labels(self) -> None:
        """Degraded metadata → empty label lines (RULE-11), render succeeds."""
        gateway, captured = _capturing_gateway()
        generator, session_manager = _real_composer_generator(gateway)
        chapter_id, user_id, project_id = identifiers()
        session_id = await _seeded_session(session_manager, user_id, project_id, chapter_id)

        _ = [
            c
            async for c in generator.stream_draft(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
            )
        ]

        assert "- Project: \n" in captured["system"]
        assert "- Genre: \n" in captured["system"]


# ---------------------------------------------------------------------------
# 3. Production wiring — dispatch context assembly
# ---------------------------------------------------------------------------


class TestDispatchNovelSupply:
    """dispatch_interview_draft assembles and feeds the novel metadata."""

    @staticmethod
    async def _run_dispatch(
        monkeypatch: pytest.MonkeyPatch,
        *,
        novel: SimpleNamespace | None,
        session_fails: bool = False,
    ) -> tuple[_CaptureSocket, RecordingComposer]:
        """Run the dispatch against fakes; return (socket, recording composer)."""
        from narrare.writing._ws_draft_dispatch import dispatch_interview_draft

        _install_novel_fetch(monkeypatch, novel=novel, session_fails=session_fails)
        session_manager = SessionManager(cache=InMemorySessionCache())
        chapter_id, user_id, project_id = identifiers()
        session_id = await _seeded_session(session_manager, user_id, project_id, chapter_id)
        gateway = Mock()
        gateway.stream = Mock(side_effect=_dispatch_stream)
        composer = RecordingComposer()
        socket = _CaptureSocket()

        await dispatch_interview_draft(
            websocket=cast("StreamSender", socket),
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            chapter_id=chapter_id,
            session_manager=session_manager,
            registry=gateway,
            composer=cast("PromptComposer", composer),
            config=make_config(),
            invocation_pipeline=InvocationPipeline(),
            run_limit_resolver=DefaultRunLimitResolver(),
        )
        return socket, composer

    async def test_dispatch_supplies_novel_metadata_from_handshake_scope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Novel row present → populated metadata reaches the composer."""
        socket, composer = await self._run_dispatch(
            monkeypatch,
            novel=make_ws_novel(title=_NOVEL_TITLE, genre="fantasy"),
        )
        assert any(m["type"] == "draft_done" for m in socket.sent)
        assert composer.last_context is not None
        assert composer.last_context.project_title == _NOVEL_TITLE
        assert composer.last_context.genre == "fantasy"

    async def test_dispatch_without_novel_row_degrades_to_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing novel row → empty metadata, draft still completes."""
        socket, composer = await self._run_dispatch(monkeypatch, novel=None)
        assert any(m["type"] == "draft_done" for m in socket.sent)
        assert composer.last_context is not None
        assert composer.last_context.project_title == ""
        assert composer.last_context.genre == ""

    async def test_dispatch_session_failure_degrades_to_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Session acquisition failure → RULE-11 degrade, draft completes."""
        socket, composer = await self._run_dispatch(monkeypatch, novel=None, session_fails=True)
        assert any(m["type"] == "draft_done" for m in socket.sent)
        assert composer.last_context is not None
        assert composer.last_context.project_title == ""
        assert composer.last_context.genre == ""
