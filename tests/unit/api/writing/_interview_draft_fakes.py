"""Shared fakes for interview draft unit tests.

Kept in a separate module so ``test_interview_draft`` and
``test_interview_draft_contract`` stay under the test hard limit
(RULE-04).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import Mock
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import pytest

    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.context import PromptContext

from narrare.writing._interview_draft import InterviewDraftGenerator
from narrare.writing._ws_cache import InMemorySessionCache
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.writing.session_manager import SessionManager


class RecordingComposer:
    """Stub PromptComposer that records the context it received."""

    def __init__(self) -> None:
        self.last_context: PromptContext | None = None
        self.call_count: int = 0

    async def build(
        self,
        intent: LLMIntent,
        context: PromptContext,
        *,
        db_content: str | None = None,
        user_prompt: str = "",
    ) -> ComposedPrompt:
        self.last_context = context
        self.call_count += 1
        return ComposedPrompt(system="system-prompt", user="user-prompt")


async def fake_stream_hello(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
    """Yield text chunks then a final chunk."""
    yield StreamChunk(text="Once upon a time ")
    yield StreamChunk(text="there was a dog.", is_final=True, usage=TokenUsage(10, 20, 30))


def make_config() -> ResolvedModelConfig:
    """Create a test ResolvedModelConfig."""
    return ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=100,
    )


def make_generator(
    *,
    pipeline: InvocationPipeline | None = None,
) -> tuple[InterviewDraftGenerator, SessionManager, Mock, RecordingComposer]:
    """Create an InterviewDraftGenerator with wired invocation contract.

    By default wires a real (no-op) InvocationPipeline and a real
    DefaultRunLimitResolver so the full contract runs.
    """
    cache = InMemorySessionCache()
    session_manager = SessionManager(cache=cache)
    gateway = Mock()
    gateway.stream = Mock(side_effect=fake_stream_hello)
    composer = RecordingComposer()
    config = make_config()
    invocation_pipeline = pipeline if pipeline is not None else InvocationPipeline()

    generator = InterviewDraftGenerator(
        session_manager=session_manager,
        registry=gateway,
        composer=cast("PromptComposer", composer),
        config=config,
        invocation_pipeline=invocation_pipeline,  # type: ignore[call-arg]
        run_limit_resolver=DefaultRunLimitResolver(),  # type: ignore[call-arg]
    )
    return generator, session_manager, gateway, composer


def identifiers() -> tuple[UUID, UUID, UUID]:
    """Return (user_id, project_id, chapter_id) as fresh UUIDs."""
    return uuid4(), uuid4(), uuid4()


# ---------------------------------------------------------------------------
# WsWritingContextAssembler fetch doubles (WS-draft-KB slice)
# ---------------------------------------------------------------------------


@dataclass
class WsFetchRecorder:
    """Records the fetch scopes the assembler used (assertion surface)."""

    provider_scopes: list[UUID] = field(default_factory=list)
    get_calls: list[UUID] = field(default_factory=list)
    list_calls: list[UUID] = field(default_factory=list)


def make_ws_chapter(
    *,
    chapter_id: UUID | None = None,
    position: int = 5,
    title: str = "Chapter 5",
) -> SimpleNamespace:
    """Chapter double shaped for ``WsWritingContextAssembler``."""
    return SimpleNamespace(
        id=chapter_id or uuid4(),
        title=title,
        content=f"content of pos {position}",
        summary=f"summary of pos {position}",
        position=position,
        timeline_position="",
    )


def make_ws_novel(
    *,
    title: str = "Codex of Tides",
    genre: str = "fantasy",
) -> SimpleNamespace:
    """Novel double shaped for ``WsWritingContextAssembler``."""
    return SimpleNamespace(
        title=title,
        genre=genre,
        writing_language="en",
        tone="",
        story_structure="three_act",
        series_id=None,
    )


def make_ws_kb_entry(
    name: str = "Mara",
    body: str = "The lighthouse keeper with salt-grey eyes.",
) -> SimpleNamespace:
    """KBEntry double shaped for the canonical ``kb_entry_to_kb_entity`` mapper."""
    return SimpleNamespace(
        id=uuid4(),
        entity_type="character",
        name=name,
        body=body,
        updated_at=None,
        metadata_={},
        status="canon",
        source="manual",
        review_status="endorsed",
    )


def install_ws_fetch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    chapter: SimpleNamespace | None = None,
    chapters: list[SimpleNamespace] | None = None,
    novel: SimpleNamespace | None = None,
    kb_entries: list[SimpleNamespace] | None = None,
    edges: list[tuple[str, str, str | None, str, str]] | None = None,
    relationships_error: bool = False,
    session_fails: bool = False,
    novel_get_raises: bool = False,
) -> WsFetchRecorder:
    """Patch the WS assembler's short-lived-session fetch bundle.

    Installs doubles for the repositories ``WsWritingContextAssembler``
    resolves lazily (chapters, novel, KB provider, relationships) plus
    ``get_async_session``. Mirrors the assembler test bundle in
    ``test_ws_context_assembler.py`` for the draft-side tests.

    Returns:
        A recorder exposing the fetch scopes for assertions.
    """
    repos = WsFetchRecorder()
    repo_chapters = chapters if chapters is not None else []
    repo_kb = kb_entries if kb_entries is not None else []
    repo_edges = edges if edges is not None else []

    class _ChapterRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get(self, chapter_id: UUID) -> SimpleNamespace | None:
            repos.get_calls.append(chapter_id)
            return chapter

        async def list_by_novel(
            self, novel_id: UUID, volume_id: object = None
        ) -> list[SimpleNamespace]:
            repos.list_calls.append(novel_id)
            return repo_chapters

    class _NovelRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get(self, novel_id: UUID) -> SimpleNamespace | None:
            if novel_get_raises:
                raise RuntimeError("novel repo unavailable")
            return novel

    class _RelationshipRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_relationships_with_names(
            self, novel_id: UUID, entity_ids: object = None
        ) -> list[tuple[str, str, str | None, str, str]]:
            if relationships_error:
                raise RuntimeError("relationship repo unavailable")
            return repo_edges

    class _KBRepo:
        def __init__(self, _session: object) -> None:
            pass

    class _Provider:
        def __init__(self, kb_repo: object, relationship_repo: object) -> None:
            pass

        async def fetch_entities(self, novel_id: UUID) -> list[SimpleNamespace]:
            repos.provider_scopes.append(novel_id)
            return repo_kb

    async def _session_gen() -> AsyncIterator[object]:
        if session_fails:
            raise RuntimeError("session factory down")
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
        _Provider,
    )
    return repos
