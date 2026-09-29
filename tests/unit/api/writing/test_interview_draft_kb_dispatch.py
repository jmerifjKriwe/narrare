"""Interview-draft KB dispatch wiring tests (WS-draft-KB slice).

Production-wiring half of the KB-context pins (RULE-04 split from
``test_interview_draft_kb_context.py``, which holds the builder and the
byte-identity floor). These tests drive
:func:`~narrare.writing._ws_draft_dispatch.dispatch_interview_draft`
against the assembler fetch doubles and pin:

1. Populated KB/novel/relationships reach the rendered draft prompt
   (real composer, end-to-end).
2. Chapter-less draft (first chapter): tier-1/tier-2 degrade empty
   while novel/KB fetches still deliver.
3. Prior chapters feed the tier-2 recent block (free ride).
4. Session-acquisition and repository failures degrade KB-blind with
   the draft still completing (RULE-11 — the R3 behavior floor).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import Mock

from narrare.writing._ws_cache import InMemorySessionCache
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.writing.session_manager import SessionManager
from tests.unit.api.writing._interview_draft_fakes import (
    RecordingComposer,
    identifiers,
    install_ws_fetch,
    make_config,
    make_ws_chapter,
    make_ws_kb_entry,
    make_ws_novel,
)
from tests.unit.api.writing.test_interview_draft_kb_context import _seeded_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import pytest

    from narrare.writing.ws_streaming import StreamSender

_NOVEL_TITLE = "Codex of Tides"
_KB_NAME = "Mara"
_RELATION_EDGE = (_KB_NAME, "ally_of", None, "Juno", "outgoing")
_RECENT_TITLE = "Chapter 2: The Brass Key"


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _CaptureSocket:
    """Minimal ``StreamSender`` double capturing sent frames."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_json(self, data: dict[str, object]) -> None:
        self.sent.append(data)


# ---------------------------------------------------------------------------
# Dispatch wiring — assembly, degrade, tier-2
# ---------------------------------------------------------------------------


class TestDispatchKbSupply:
    """dispatch_interview_draft assembles the KB context and degrades."""

    @staticmethod
    async def _run_dispatch(
        monkeypatch: pytest.MonkeyPatch,
        *,
        composer: PromptComposer | RecordingComposer,
        **fetch_kwargs: object,
    ) -> tuple[_CaptureSocket, dict[str, str]]:
        """Run the dispatch against the assembler fetch doubles.

        The gateway double captures the composed ``system_prompt`` and
        streams a two-chunk body so the completion frame is sent.
        """
        from narrare.writing._ws_draft_dispatch import dispatch_interview_draft

        install_ws_fetch(monkeypatch, **fetch_kwargs)
        session_manager = SessionManager(cache=InMemorySessionCache())
        chapter_id, user_id, project_id = identifiers()
        session_id = await _seeded_session(session_manager, user_id, project_id, chapter_id)
        captured: dict[str, str] = {}

        async def capturing_stream(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
            captured["system"] = str(kwargs["system_prompt"])
            yield StreamChunk(text="A draft. ")
            yield StreamChunk(text="The end.", is_final=True, usage=TokenUsage(1, 2, 3))

        gateway = Mock()
        gateway.stream = Mock(side_effect=capturing_stream)
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
        return socket, captured

    async def test_dispatch_delivers_kb_and_metadata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Populated KB + novel reach the rendered draft prompt (end-to-end)."""
        composer = PromptComposer(PromptRegistry())
        socket, captured = await self._run_dispatch(
            monkeypatch,
            composer=composer,
            chapter=make_ws_chapter(position=3),
            chapters=[make_ws_chapter(position=1), make_ws_chapter(position=2)],
            novel=make_ws_novel(title=_NOVEL_TITLE),
            kb_entries=[make_ws_kb_entry(_KB_NAME)],
            edges=[_RELATION_EDGE],
        )

        assert any(m["type"] == "draft_done" for m in socket.sent)
        system = captured["system"]
        assert f"- Project: {_NOVEL_TITLE}" in system
        assert _KB_NAME in system  # unreferenced entity → suggested tier
        assert "ally_of" in system  # relationship edge rendered

    async def test_dispatch_chapter_less_still_delivers_kb(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing chapter (first draft) → tier-2 empty, novel/KB delivered."""
        recording = RecordingComposer()
        socket, _ = await self._run_dispatch(
            monkeypatch,
            composer=recording,
            chapter=None,
            chapters=[],
            novel=make_ws_novel(title=_NOVEL_TITLE),
            kb_entries=[make_ws_kb_entry(_KB_NAME)],
        )

        assert any(m["type"] == "draft_done" for m in socket.sent)
        ctx = recording.last_context
        assert ctx is not None
        assert ctx.project_title == _NOVEL_TITLE
        assert _KB_NAME in ctx.extra["kb_suggested"]
        assert ctx.extra["recent_chapters"] == ""

    async def test_dispatch_prior_chapters_feed_recent_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Chapter at position N with prior chapters → tier-2 recent block."""
        recording = RecordingComposer()
        socket, _ = await self._run_dispatch(
            monkeypatch,
            composer=recording,
            chapter=make_ws_chapter(position=3),
            chapters=[
                make_ws_chapter(position=1, title="Chapter 1"),
                make_ws_chapter(position=2, title=_RECENT_TITLE),
            ],
            novel=make_ws_novel(title=_NOVEL_TITLE),
        )

        assert any(m["type"] == "draft_done" for m in socket.sent)
        ctx = recording.last_context
        assert ctx is not None
        assert _RECENT_TITLE in ctx.extra["recent_chapters"]

    async def test_dispatch_relationships_render_into_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fetched relationship edges land in the kb_relationships slot."""
        recording = RecordingComposer()
        socket, _ = await self._run_dispatch(
            monkeypatch,
            composer=recording,
            chapter=make_ws_chapter(position=1),
            novel=make_ws_novel(),
            edges=[_RELATION_EDGE],
        )

        assert any(m["type"] == "draft_done" for m in socket.sent)
        ctx = recording.last_context
        assert ctx is not None
        assert _KB_NAME in ctx.extra["kb_relationships"]
        assert "Juno" in ctx.extra["kb_relationships"]

    async def test_dispatch_session_failure_degrades_kb_blind(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Session-acquisition failure → KB-blind degrade, draft completes."""
        recording = RecordingComposer()
        socket, _ = await self._run_dispatch(
            monkeypatch,
            composer=recording,
            chapter=make_ws_chapter(position=1),
            novel=make_ws_novel(title=_NOVEL_TITLE),
            kb_entries=[make_ws_kb_entry(_KB_NAME)],
            session_fails=True,
        )

        assert any(m["type"] == "draft_done" for m in socket.sent)
        ctx = recording.last_context
        assert ctx is not None
        assert ctx.project_title == ""
        assert ctx.extra["kb_characters"] == ""
        assert ctx.extra["kb_suggested"] == ""

    async def test_dispatch_assembler_failure_degrades_kb_blind(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repository failure inside assemble → RULE-11 degrade, no crash."""
        recording = RecordingComposer()
        socket, _ = await self._run_dispatch(
            monkeypatch,
            composer=recording,
            chapter=make_ws_chapter(position=1),
            novel_get_raises=True,
        )

        assert any(m["type"] == "draft_done" for m in socket.sent)
        ctx = recording.last_context
        assert ctx is not None
        assert ctx.project_title == ""
        assert ctx.extra["kb_characters"] == ""
