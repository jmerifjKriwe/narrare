"""Slice 3 wiring pins + Slice 4 activation goldens for the summarize kb_* supply.

The service fetches the four KB-context slots (kb_characters /
kb_locations / kb_factions / kb_relationships) from the canonical
``KBContextProvider`` (ADR-067) and spreads them into ``PromptContext.extra``
(mirroring the coreference provider→extra pattern). While the governed
summarize template's Knowledge-Base region sat BELOW the ``extract_section``
parse cutoff (the ``## System Prompt`` section ended at ``## Output
Format``), the placeholders never reached the variable engine and the
composed render stayed byte-identical to the pre-wiring capture — the
Slice 3 inertness proof.

Activation slice 4 (2026-09-12) demoted the rogue level-2 headers
(``## Output Format`` / ``## Do NOT`` → level-3, children shifted to
level-4), so the previously-dropped region NOW RENDERS: the supply wired in
Slice 3 became live. The goldens below were re-captured against the
activated template (provenance: "activation slice 4 — previously-dropped
region now renders; inertness was relative to the truncated template");
inertness was never an absolute property of the wiring, only of the
truncated template shape.

Methodology mirrors ``test_suggest_prompt_render.py``: the exact PromptContext
the service builds is composed through the REAL ``PromptRegistry`` +
``PromptComposer``; the service-level supply wiring is pinned via the
PromptContext captured at the composer seam. Byte-exact render pins live in
``tests/unit/core/prompts/test_summarize_prompt_render.py`` (Slice 4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic_ai.models import Model

from narrare.kb.context_contracts import KBContextBundle
from narrare.writing.summary_service import ChapterSummaryService
from narrare_core.agents.summary_agent import ChapterSummaryAgent
from narrare_core.context._kb_envelope import RenderedKBContext
from narrare_core.context._render_options import RenderOptions
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from tests.unit.core.prompts.test_summarize_goldens import (
    GOLDEN_SYSTEM_EMPTY_KB,
    GOLDEN_SYSTEM_POPULATED,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.models import Chapter
    from narrare.kb.models import KBEntry

TEST_USER_ID = "00000000-0000-0000-0000-0000000000aa"  # novel owner in these tests

# ---------------------------------------------------------------------------
# Fakes + builders (ADR-030 fake-first)
# ---------------------------------------------------------------------------


def _rendered(text: str) -> RenderedKBContext:
    """Build a RenderedKBContext for tests (provenance not asserted here)."""
    return RenderedKBContext(
        text=text,
        preserved_fields=frozenset(),
        omitted_fields=(),
        entry_count=1,
        render_path="test._rendered",
    )


def _bundle_with_data() -> KBContextBundle:
    """A bundle whose four slots carry non-empty rendered KB context."""
    return KBContextBundle(
        characters=_rendered("- Alice (character): the protagonist"),
        locations=_rendered("- Berlin (location): where the story happens"),
        factions=_rendered("- The Cult (faction): antagonists"),
        relationships=_rendered("- Alice <-> Bob: rivals"),
        render_options=RenderOptions(annotate_provenance=True),
    )


class _FakeKBContextProvider:
    """Minimal fake satisfying ``KBContextProviderProtocol`` (ADR-030 fake-first)."""

    def __init__(self, bundle: KBContextBundle | None = None) -> None:
        self._bundle = bundle
        self.fetch_context_calls: list[tuple[UUID, list[str] | None]] = []

    async def fetch_context(
        self,
        novel_id: UUID,
        *,
        entity_types: list[str] | None = None,
        options: RenderOptions | None = None,
    ) -> KBContextBundle:
        self.fetch_context_calls.append((novel_id, entity_types))
        if self._bundle is None:
            return KBContextBundle.empty(options)
        return self._bundle

    async def fetch_entities(
        self, novel_id: UUID, *, entity_types: list[str] | None = None
    ) -> list[KBEntry]:
        """Return no entities — summarize tests ``fetch_context`` only."""
        return []

    async def fetch_world_context(
        self,
        novel_id: UUID,
        *,
        entity_type: str | None = None,
        max_entries: int = 30,
    ) -> str:
        return ""


def _config() -> ResolvedModelConfig:
    """Create a default ResolvedModelConfig for tests."""
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.3,
        max_tokens=1000,
    )


def _make_registry() -> AsyncMock:
    """Mock ModelRegistry with the prepare() assembly point (Task 6c)."""
    registry = AsyncMock()
    model_mock = MagicMock(spec=Model)
    registry.prepare = AsyncMock(
        return_value=PreparedModelCall(
            model=model_mock,
            model_settings={"max_tokens": 1000},
            usage_limits=None,
        )
    )
    return registry


def _make_repos(chapter_content: str, title: str) -> tuple[AsyncMock, AsyncMock, Chapter]:
    """Mocked repos: one persisted chapter; the ownership gate passes."""
    from tests.factories import make_chapter, make_novel

    chapter = make_chapter(content=chapter_content, title=title)
    chapter_repo = AsyncMock()
    chapter_repo.get = AsyncMock(return_value=chapter)
    chapter_repo.update_summary = AsyncMock()
    novel_repo = AsyncMock()
    novel_repo.get_by_id = AsyncMock(return_value=make_novel())
    return chapter_repo, novel_repo, chapter


def _make_service(
    composer: PromptComposer | AsyncMock,
    provider: _FakeKBContextProvider | None,
    chapter_repo: AsyncMock,
    novel_repo: AsyncMock,
) -> ChapterSummaryService:
    """Build the service under test with the real bundled prompt cascade."""
    from tests.unit.api.writing._writing_factories import make_static_summary_runtime_factory

    return ChapterSummaryService(
        registry=_make_registry(),
        # ADR-086 L38: fixed first-use runtime (render-inert — the golden
        # prompts depend on the composer + KB bundle, not the config).
        runtime_factory=make_static_summary_runtime_factory(_config()),
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        composer=composer,
        kb_context_provider=provider,
    )


def _mock_summary_agent() -> MagicMock:
    """A spec'd ChapterSummaryAgent class mock recording construction."""
    from narrare_core.agents.summary_types import SummaryOutput

    mock_agent = AsyncMock()
    mock_output = MagicMock(spec=SummaryOutput)
    mock_output.summary = "A hero begins their journey."
    mock_output.word_count = 5
    mock_output.key_points = ["Hero introduction"]
    mock_agent.run = AsyncMock(return_value=mock_output)
    return MagicMock(spec=ChapterSummaryAgent, return_value=mock_agent)


def _make_mock_composer() -> AsyncMock:
    """Mock PromptComposer recording the build() seam (ComposedPrompt)."""
    from narrare_core.prompts.composer import ComposedPrompt

    composer = AsyncMock()
    composer.build = AsyncMock(
        return_value=ComposedPrompt(
            system="You are a summarizer.",
            user="Summarize this content.",
        )
    )
    return composer


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSummarizeKBRenderActivation:
    """Slice 4: the Slice-3 kb_* supply now reaches the render.

    Activation slice 4 demoted the rogue level-2 headers, so the composed
    system prompt renders the previously-dropped region. Provider data
    lands in the Knowledge-Base slots; an empty bundle / no provider
    degrades to empty-bodied slots (labels kept) — zero ``{{`` residue in
    every case.
    """

    async def test_kb_provider_data_compose_matches_activation_golden(self) -> None:
        """Provider WITH data: composed render is byte-identical to the
        Slice 4 activation golden (kb sentinels render)."""
        chapter_repo, novel_repo, chapter = _make_repos(
            "Once upon a time in a faraway land...", "Chapter 1"
        )
        provider = _FakeKBContextProvider(bundle=_bundle_with_data())
        service = _make_service(
            PromptComposer(PromptRegistry()), provider, chapter_repo, novel_repo
        )
        agent_cls = _mock_summary_agent()

        with patch("narrare.writing._summary_invocation.ChapterSummaryAgent", agent_cls):
            await service.summarize(chapter_id=chapter.id, user_id=TEST_USER_ID)

        system_prompt = agent_cls.call_args.kwargs["system_prompt"]
        assert system_prompt == GOLDEN_SYSTEM_POPULATED
        assert "- Alice (character): the protagonist" in system_prompt
        assert "{{" not in system_prompt

    async def test_kb_provider_empty_bundle_compose_matches_activation_empty_golden(
        self,
    ) -> None:
        """Provider WITHOUT data (empty KB): degraded render — every section
        present, kb slots empty-bodied, no placeholder residue."""
        chapter_repo, novel_repo, chapter = _make_repos("Some content here...", "Chapter 1")
        provider = _FakeKBContextProvider(bundle=KBContextBundle.empty(RenderOptions()))
        service = _make_service(
            PromptComposer(PromptRegistry()), provider, chapter_repo, novel_repo
        )
        agent_cls = _mock_summary_agent()

        with patch("narrare.writing._summary_invocation.ChapterSummaryAgent", agent_cls):
            await service.summarize(chapter_id=chapter.id, user_id=TEST_USER_ID)

        system_prompt = agent_cls.call_args.kwargs["system_prompt"]
        assert system_prompt == GOLDEN_SYSTEM_EMPTY_KB
        assert "- Alice (character): the protagonist" not in system_prompt
        assert "{{" not in system_prompt

    async def test_no_provider_compose_matches_activation_empty_golden(self) -> None:
        """Legacy construction (no provider): degrades to the same empty-KB
        render (RULE-11 — the service builds an empty bundle itself)."""
        chapter_repo, novel_repo, chapter = _make_repos("Some content here...", "Chapter 1")
        service = _make_service(PromptComposer(PromptRegistry()), None, chapter_repo, novel_repo)
        agent_cls = _mock_summary_agent()

        with patch("narrare.writing._summary_invocation.ChapterSummaryAgent", agent_cls):
            await service.summarize(chapter_id=chapter.id, user_id=TEST_USER_ID)

        system_prompt = agent_cls.call_args.kwargs["system_prompt"]
        assert system_prompt == GOLDEN_SYSTEM_EMPTY_KB
        assert "{{" not in system_prompt

    async def test_prompt_context_extra_carries_kb_vars_and_max_sentences(
        self,
    ) -> None:
        """Supply-wiring pin: the PromptContext passed to the composer carries
        the four kb_* slots from the provider plus max_sentences — so the
        variables HAVE supply when the template region is re-activated."""
        chapter_repo, novel_repo, chapter = _make_repos("Some content here...", "Chapter 1")
        composer = _make_mock_composer()
        provider = _FakeKBContextProvider(bundle=_bundle_with_data())
        service = _make_service(composer, provider, chapter_repo, novel_repo)
        agent_cls = _mock_summary_agent()

        with patch("narrare.writing._summary_invocation.ChapterSummaryAgent", agent_cls):
            await service.summarize(chapter_id=chapter.id, max_sentences=3, user_id=TEST_USER_ID)

        context = composer.build.call_args[0][1]
        assert context.extra["max_sentences"] == "3"
        assert context.extra["kb_characters"] == "- Alice (character): the protagonist"
        assert context.extra["kb_locations"] == "- Berlin (location): where the story happens"
        assert context.extra["kb_factions"] == "- The Cult (faction): antagonists"
        assert context.extra["kb_relationships"] == "- Alice <-> Bob: rivals"

    async def test_kb_fetch_is_novel_scoped_with_three_entity_types(
        self,
    ) -> None:
        """Fetch-wiring pin: provider.fetch_context receives the chapter's
        novel_id and the character/location/faction type filter (ADR-067)."""
        chapter_repo, novel_repo, chapter = _make_repos("Some content here...", "Chapter 1")
        composer = _make_mock_composer()
        provider = _FakeKBContextProvider(bundle=_bundle_with_data())
        service = _make_service(composer, provider, chapter_repo, novel_repo)
        agent_cls = _mock_summary_agent()

        with patch("narrare.writing._summary_invocation.ChapterSummaryAgent", agent_cls):
            await service.summarize(chapter_id=chapter.id, user_id=TEST_USER_ID)

        assert provider.fetch_context_calls == [
            (chapter.novel_id, ["character", "location", "faction"])
        ]
