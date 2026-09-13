"""Unit tests for ChatService project-context enrichment (FO-7 follow-up).

The chat seam (ADR-024 minimal tier) holds no novel data of its own — the
root cause of the four statically-empty FO-7 slots. What the seam CAN
obtain through its existing dependencies is the owned novel's metadata:
``ChatService.ask`` resolves the owned novel during project-link
validation (single fetch, no extra query) and threads its ``title`` /
``genre`` into the ``PromptContext`` — mirroring how analysis seams fetch
novel metadata.

Degradation paths (RULE-11 — never raise, never silent):
- project-less chat (``project_id=None``): no metadata, no lookup call.
- unwired lookup (test contexts): no check, no metadata.
- non-novel-shaped lookup result: warn + empty placeholders.

See:
    apps/api/narrare/chat/_context.py (build_prompt_context),
    apps/api/narrare/chat/chat_service.py (_resolve_owned_novel),
    narrare_core.chat.chat_service_core.build_chat_context,
    CONSTRAINTS.md RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare_core.agents.base import StreamEvent
from narrare_core.chat.chat_agent import ChatAgent
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from tests.unit.api.chat.conftest import FakeNovelLookup

    from narrare.chat.chat_service import ChatService

_SENTINEL_TITLE = "SENTINEL_NOVEL_TITLE_9d21"
_SENTINEL_GENRE = "SENTINEL_NOVEL_GENRE_4e07"

# Typed "no override" marker: keeps the ``_make_request`` random project id
# while ``project_id`` stays honestly typed ``UUID | None`` (ADR-085 seam
# cast precedent — unique object identity, zero runtime behavior change).
_UNSET = cast("UUID", object())


def _recording_agent() -> MagicMock:
    """ChatAgent stand-in streaming one done event (RULE-TEST-01 spec'd)."""

    async def _events() -> AsyncIterator[StreamEvent]:
        yield StreamEvent(type="done", text="ok", usage={}, new_messages=[])

    mock_agent = MagicMock(name="context_agent", spec=ChatAgent)
    mock_agent.run_stream.side_effect = lambda *a, **kw: _events()
    return mock_agent


async def _capture_prompt_context(
    service: ChatService,
    composer: AsyncMock,
    message: str,
    user_id: UUID,
    *,
    project_id: UUID | None = _UNSET,
) -> PromptContext:
    """Drive ``ask()`` and return the PromptContext passed to the composer.

    ``ChatService.ask`` calls ``composer.build(LLMIntent.CHAT, context,
    user_prompt=...)`` — the context is the second positional argument.
    ``project_id`` overrides the request default (``_UNSET`` keeps the
    ``_make_request`` random project id; ``None`` forces project-less).
    """
    from tests.unit.api.chat.conftest import _make_request

    request = _make_request(message=message)
    if project_id is not _UNSET:
        request.project_id = project_id
    with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=_recording_agent()):
        async for _ in await service.ask(request, user_id):
            pass

    call = composer.build.await_args
    assert call is not None, "composer.build was never awaited"
    context = call.args[1]
    assert isinstance(context, PromptContext)
    return context


class TestAskProjectContextEnrichment:
    """``ask()`` threads the owned novel's metadata into the prompt context."""

    async def test_ask_with_owned_project_supplies_novel_title_and_genre(
        self,
        service_with_novel_lookup: ChatService,
        mock_composer: AsyncMock,
        novel_lookup: FakeNovelLookup,
    ) -> None:
        """Project-linked chat carries the novel's title/genre (sentinels)."""
        user_id = uuid4()
        novel_id = uuid4()
        novel_lookup.seed_owned(
            novel_id,
            user_id,
            title=_SENTINEL_TITLE,
            genre=_SENTINEL_GENRE,
        )

        context = await _capture_prompt_context(
            service_with_novel_lookup,
            mock_composer,
            "About my novel",
            user_id,
            project_id=novel_id,
        )

        assert context.project_title == _SENTINEL_TITLE
        assert context.genre == _SENTINEL_GENRE

    async def test_ask_with_unshaped_novel_degrades_to_empty_metadata(
        self,
        service_with_novel_lookup: ChatService,
        mock_composer: AsyncMock,
        novel_lookup: FakeNovelLookup,
    ) -> None:
        """A non-novel-shaped lookup result degrades to "" — never raises.

        Unseeded ids resolve to a bare ``object()`` (the conftest fake's
        legacy shape); the seam must treat it as metadata-less, not crash
        (RULE-11).
        """
        user_id = uuid4()
        novel_id = uuid4()
        novel_lookup.seed_owned(novel_id, user_id)  # no metadata → bare object()

        context = await _capture_prompt_context(
            service_with_novel_lookup,
            mock_composer,
            "Craft question",
            user_id,
            project_id=novel_id,
        )

        assert context.project_title == ""
        assert context.genre == ""

    async def test_ask_projectless_keeps_empty_metadata_without_lookup_call(
        self,
        service_with_novel_lookup: ChatService,
        mock_composer: AsyncMock,
        novel_lookup: FakeNovelLookup,
    ) -> None:
        """Project-less chat: empty placeholders, no novel fetch (NOTES-001)."""
        with patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            return_value=_recording_agent(),
        ):
            await _capture_prompt_context(
                service_with_novel_lookup,
                mock_composer,
                "Global craft question",
                uuid4(),
                project_id=None,
            )

        assert novel_lookup.calls == []

    async def test_ask_without_lookup_wiring_keeps_empty_metadata(
        self,
        service: ChatService,
        mock_composer: AsyncMock,
    ) -> None:
        """Unwired lookup (test contexts only): skip check, empty metadata."""
        context = await _capture_prompt_context(service, mock_composer, "Hello", uuid4())

        assert context.project_title == ""
        assert context.genre == ""


class TestAskContextTierContract:
    """The FO-7 slots stay present in the production-shaped context."""

    @pytest.mark.parametrize(
        ("slot", "expected"),
        [
            ("timeline_position", ""),
            ("kb_context_warnings", ""),
            ("kb_other", ""),
            ("kb_suggested", ""),
        ],
    )
    async def test_fo7_slots_present_and_documented_empty(
        self,
        service_with_novel_lookup: ChatService,
        mock_composer: AsyncMock,
        novel_lookup: FakeNovelLookup,
        slot: str,
        expected: str,
    ) -> None:
        """Each FO-7 slot exists in ``extra`` with its degradation default.

        The slots are NOT enrichment targets of this slice (chapter-scoped
        / KB-repository-scoped — see build_chat_context docstring); this
        pins that the production seam still supplies them so compose never
        raises PromptVariableError.
        """
        user_id = uuid4()
        novel_id = uuid4()
        novel_lookup.seed_owned(
            novel_id,
            user_id,
            title=_SENTINEL_TITLE,
            genre=_SENTINEL_GENRE,
        )

        context = await _capture_prompt_context(
            service_with_novel_lookup,
            mock_composer,
            "Pacing question",
            user_id,
            project_id=novel_id,
        )

        assert context.extra[slot] == expected


__all__ = ["TestAskContextTierContract", "TestAskProjectContextEnrichment"]
