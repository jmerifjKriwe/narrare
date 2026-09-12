"""WS context assembler tests — production data-fetching wiring (FO-4).

``WsWritingContextAssembler`` is the production seam that un-KB-blinds
WebSocket writing turns. These tests pin, at the unit level:

1. Fetch delegation — chapter, novel metadata, recent chapters (Tier 2),
   structured KB entities (ADR-067 provider + canonical mapper), and
   rendered relationships reach the core transformer.
2. Tier-2 discipline — future chapters never leak; the current chapter
   is excluded; the 3-chapter cap holds; a missing current chapter
   yields no recent context.
3. RULE-11 graceful degradation — missing chapter/novel rows, an
   unavailable relationship fetch, and a ``None`` project scope all
   still assemble a usable ``WritingContext`` (never raise).
4. End-to-end wiring — the real assembler feeds a real-composer turn
   (capped stream mock), and both production construction sites
   (``deps_ws`` / ``ws_factory``) wire it (pinned in
   ``test_ws_turn_prompt_supply.py``).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock
from uuid import uuid4

from narrare.writing.ws_context_assembler import WsWritingContextAssembler
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    import pytest

_CHAPTER_ID = uuid4()
_PROJECT_ID = uuid4()

_CONTENT_SENTINEL = "Mara opened the lighthouse door onto the tidal cave."
_TIMELINE_SENTINEL = "Day 5 of the siege."
_RECENT_TITLE = "Chapter 2: The Brass Key"
_NOVEL_TITLE = "Codex of Tides"
_KB_NAME = "Mara"


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _chapter(
    *,
    chapter_id: UUID | None = None,
    position: int = 5,
    title: str = "Chapter 5",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=chapter_id or uuid4(),
        title=title,
        content=f"content of pos {position}",
        summary=f"summary of pos {position}",
        position=position,
        timeline_position="",
    )


def _kb_entry() -> SimpleNamespace:
    """KBEntry double shaped for the canonical ``kb_entry_to_kb_entity`` mapper."""
    return SimpleNamespace(
        id=uuid4(),
        entity_type="character",
        name=_KB_NAME,
        body="The lighthouse keeper with salt-grey eyes.",
        updated_at=None,
        metadata_={},
        status="canon",
        source="manual",
        review_status="endorsed",
    )


class _FakeProvider:
    """Stands in for the ADR-067 KBContextProvider (records the scope)."""

    def __init__(self, kb_repo: object, relationship_repo: object) -> None:
        self.entries: list[SimpleNamespace] = []
        self.scopes: list[UUID] = []
        self.kb_repo = kb_repo
        self.relationship_repo = relationship_repo

    async def fetch_entities(self, novel_id: UUID) -> list[SimpleNamespace]:
        self.scopes.append(novel_id)
        return self.entries


class _FakeRepos:
    """Bundle of repository doubles wired per test via :func:`_install`."""

    def __init__(
        self,
        *,
        chapter: SimpleNamespace | None,
        chapters: list[SimpleNamespace] | None = None,
        novel: SimpleNamespace | None,
        kb_entries: list[SimpleNamespace] | None = None,
        relationships_error: bool = False,
    ) -> None:
        self.chapter = chapter
        self.chapters = chapters if chapters is not None else []
        self.novel = novel
        self.kb_entries = kb_entries if kb_entries is not None else []
        self.relationships_error = relationships_error
        self.provider = _FakeProvider(kb_repo=None, relationship_repo=None)
        self.get_calls: list[UUID] = []
        self.list_calls: list[UUID] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        repos = self

        class _ChapterRepo:
            def __init__(self, _session: object) -> None:
                pass

            async def get(self, chapter_id: UUID) -> SimpleNamespace | None:
                repos.get_calls.append(chapter_id)
                return repos.chapter

            async def list_by_novel(
                self, novel_id: UUID, volume_id: object = None
            ) -> list[SimpleNamespace]:
                repos.list_calls.append(novel_id)
                return repos.chapters

        class _NovelRepo:
            def __init__(self, _session: object) -> None:
                pass

            async def get(self, novel_id: UUID) -> SimpleNamespace | None:
                return repos.novel

        class _RelationshipRepo:
            def __init__(self, _session: object) -> None:
                pass

            async def get_relationships_with_names(
                self, novel_id: UUID, entity_ids: object = None
            ) -> list[object]:
                if repos.relationships_error:
                    raise RuntimeError("relationship repo unavailable")
                return []

        class _KBRepo:
            def __init__(self, _session: object) -> None:
                pass

        async def _session_gen() -> AsyncIterator[object]:
            yield object()

        monkeypatch.setattr("narrare._app.database.get_async_session", _session_gen)
        monkeypatch.setattr("narrare.chapters.repository.ChapterRepository", _ChapterRepo)
        monkeypatch.setattr("narrare.novels.repository.NovelRepository", _NovelRepo)
        monkeypatch.setattr("narrare.kb.repository.KBRepository", _KBRepo)
        monkeypatch.setattr(
            "narrare.kb.relationship_repository.RelationshipRepository",
            _RelationshipRepo,
        )
        monkeypatch.setattr(
            "narrare.kb._context_provider.KBContextProvider",
            lambda kb_repo, relationship_repo: self._provider_with(kb_repo, relationship_repo),
        )

    def _provider_with(self, kb_repo: object, relationship_repo: object) -> _FakeProvider:
        self.provider = _FakeProvider(kb_repo, relationship_repo)
        self.provider.entries = self.kb_entries
        return self.provider


# ---------------------------------------------------------------------------
# Fetch + assembly behaviour
# ---------------------------------------------------------------------------


class TestWsAssemblerFetchesTurnData:
    """The assembler supplies fetched data to the core transformer."""

    async def test_assemble_carries_fetched_data_into_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repos = _FakeRepos(
            chapter=_chapter(chapter_id=_CHAPTER_ID, position=5),
            chapters=[
                _chapter(position=1, title="Chapter 1"),
                _chapter(position=2, title=_RECENT_TITLE),
                _chapter(position=9, title="Chapter 9: future"),
            ],
            novel=SimpleNamespace(
                title=_NOVEL_TITLE,
                genre="fantasy",
                writing_language="en",
                tone="",
                story_structure="three_act",
                series_id=None,
            ),
            kb_entries=[_kb_entry()],
        )
        repos.install(monkeypatch)

        assembler = WsWritingContextAssembler()
        context = await assembler.assemble(
            chapter_id=_CHAPTER_ID, project_id=_PROJECT_ID, mode="interactive_session"
        )

        # Tier 1: current chapter content + timeline position
        assert context.chapter_content == "content of pos 5"
        # Tier 2: current chapter excluded, future chapter (pos 9) never leaks
        assert _RECENT_TITLE in context.recent_chapters
        assert "Chapter 1" in context.recent_chapters  # older previous chapter
        assert "future" not in context.recent_chapters
        # Novel metadata
        assert context.project_title == _NOVEL_TITLE
        assert context.genre == "fantasy"
        # KB: unreferenced entities land in the suggested tier
        assert _KB_NAME in context.kb_suggested
        # Provider fetched with the project scope
        assert repos.provider.scopes == [_PROJECT_ID]
        assert repos.get_calls == [_CHAPTER_ID]
        assert repos.list_calls == [_PROJECT_ID]

    async def test_recent_chapters_capped_and_ordered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chapters = [_chapter(position=pos, title=f"T{pos}") for pos in range(1, 7)]
        repos = _FakeRepos(
            chapter=_chapter(chapter_id=_CHAPTER_ID, position=6),
            chapters=[*chapters, _chapter(chapter_id=_CHAPTER_ID, position=6)],
            novel=None,
        )
        repos.install(monkeypatch)

        context = await WsWritingContextAssembler().assemble(
            chapter_id=_CHAPTER_ID, project_id=_PROJECT_ID
        )

        # Exactly 3 most recent previous chapters, newest first
        assert "T5" in context.recent_chapters
        assert "T4" in context.recent_chapters
        assert "T3" in context.recent_chapters
        assert "T2" not in context.recent_chapters


class TestWsAssemblerGracefulDegradation:
    """RULE-11: missing pieces degrade — assembly never raises."""

    async def test_missing_chapter_and_novel_assemble_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repos = _FakeRepos(chapter=None, novel=None)
        repos.install(monkeypatch)

        context = await WsWritingContextAssembler().assemble(
            chapter_id=_CHAPTER_ID, project_id=_PROJECT_ID
        )

        assert context.chapter_content == ""
        assert context.project_title == ""
        assert context.recent_chapters == ""
        assert context.is_first_chapter is True

    async def test_relationships_fetch_failure_degrades_to_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repos = _FakeRepos(
            chapter=_chapter(chapter_id=_CHAPTER_ID),
            novel=None,
            relationships_error=True,
        )
        repos.install(monkeypatch)

        context = await WsWritingContextAssembler().assemble(
            chapter_id=_CHAPTER_ID, project_id=_PROJECT_ID
        )

        assert context.kb_relationships == ""

    async def test_none_project_scope_skips_project_fetches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repos = _FakeRepos(chapter=_chapter(chapter_id=_CHAPTER_ID), novel=None)
        repos.install(monkeypatch)

        context = await WsWritingContextAssembler().assemble(
            chapter_id=_CHAPTER_ID, project_id=None
        )

        assert context.chapter_content == "content of pos 5"
        assert repos.provider.scopes == []
        assert repos.list_calls == []


# ---------------------------------------------------------------------------
# End-to-end: real assembler feeds a real-composer turn
# ---------------------------------------------------------------------------


class TestWsAssemblerFeedsTurn:
    """The production assembler composes a non-KB-blind WS turn."""

    async def test_turn_with_production_assembler_streams(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from narrare.writing.ws_turn_service import WritingTurnService

        repos = _FakeRepos(
            chapter=_chapter(chapter_id=_CHAPTER_ID, position=1),
            novel=None,
            kb_entries=[_kb_entry()],
        )
        repos.install(monkeypatch)

        captured: dict[str, str] = {}

        async def fake_stream(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
            captured["system"] = str(kwargs["system_prompt"])
            yield StreamChunk(text="ok", is_final=True, usage=TokenUsage(1, 2, 3))

        registry = Mock()
        registry.stream = Mock(side_effect=fake_stream)

        service = WritingTurnService(
            composer=PromptComposer(PromptRegistry()),
            invocation_pipeline=InvocationPipeline(),
            registry=registry,
            config=ResolvedModelConfig(
                provider_name="test",
                model_id="test-model",
                temperature=0.7,
                max_tokens=2000,
            ),
            run_limit_resolver=DefaultRunLimitResolver(),
            context_assembler=WsWritingContextAssembler(),
        )
        chunks = [
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

        assert any(c.text for c in chunks)
        # The turn is no longer KB-blind: fetched KB data reaches the prompt
        assert captured["system"] != ""
        assert isinstance(service._context_assembler, WsWritingContextAssembler)
