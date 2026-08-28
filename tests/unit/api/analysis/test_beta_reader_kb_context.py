"""Beta-reader KB context flows through the canonical KBContextProvider/envelope (W4b).

Proves the §7 migration: the beta-reader KB context is rendered through the
reusable :class:`~narrare.kb.context_contracts.KBContextProvider` (ADR-067) +
the ADR-050 envelope — NOT the ad-hoc ``_fetch_kb_context`` dict path.

Contract under test:
- ``ContextAssembler`` renders KB context via ``KBContextProvider.fetch_context``
  with ``RenderOptions(annotate_provenance=True)`` (FIND-017) and
  ``entity_types=["character", "location"]``.
- The rendered ``.text`` of each per-type envelope lands on ``BetaReaderDeps``
  as ``str`` fields (decision β — boundary-rendered text; the agent consumes KB
  context as prompt text, never structurally).
- Non-empty KB → non-empty rendered text; empty KB → empty strings, NO exception
  (RULE-11 graceful degradation).
- No provider wired → empty strings, NO exception (RULE-11).

See:
    ADR-067 — Reusable KB-Context Provider
    ADR-050 — KB Envelope (render contract)
    CONSTRAINTS.md RULE-03/06/07/11/22
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from narrare.analysis.context_assembler import ContextAssembler
from narrare_core.context._kb_envelope import RenderedKBContext
from narrare_core.context._render_options import RenderOptions

if TYPE_CHECKING:
    from narrare.kb.context_contracts import KBContextBundle, KBContextProviderProtocol
    from narrare.kb.models import KBEntry

# Caller identity for the Step 0 ownership gate (IDOR S12a) — the mocked
# novel repo owns everything, so any caller passes the gate.
USER_ID = uuid4()


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeKBContextProvider:
    """Minimal fake satisfying ``KBContextProviderProtocol`` (ADR-030 fake-first)."""

    def __init__(
        self,
        bundle: KBContextBundle | None = None,
        world_context: str = "",
    ) -> None:
        self._bundle = bundle
        self._world_context = world_context
        self.fetch_context_calls: list[tuple[UUID, tuple[object, ...], dict[str, object]]] = []

    async def fetch_context(
        self,
        novel_id: UUID,
        *,
        entity_types: list[str] | None = None,
        options: RenderOptions | None = None,
    ) -> KBContextBundle:
        self.fetch_context_calls.append((novel_id, tuple(entity_types or []), {"options": options}))
        if self._bundle is None:
            from narrare.kb.context_contracts import KBContextBundle

            return KBContextBundle.empty(options)
        return self._bundle

    async def fetch_entities(
        self,
        novel_id: UUID,
        *,
        entity_types: list[str] | None = None,
    ) -> list[KBEntry]:
        """Return no entities — the beta-reader path tests ``fetch_context``,
        not entity-level ref resolution (ADR-030 honest fake)."""
        return []

    async def fetch_world_context(
        self,
        novel_id: UUID,
        *,
        entity_type: str | None = None,
        max_entries: int = 30,
    ) -> str:
        return self._world_context


def _rendered(text: str) -> RenderedKBContext:
    """Build a RenderedKBContext for tests (accounting not asserted at the Deps layer)."""
    return RenderedKBContext(
        text=text,
        preserved_fields=frozenset(),
        omitted_fields=(),
        entry_count=1,
        render_path="test._rendered",
    )


def _make_chapter(chapter_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=chapter_id or uuid4(),
        novel_id=uuid4(),
        title="Test Chapter",
        content="Test chapter content with enough words to pass validation. " * 50,
        summary="",
        position=0,
        word_count=3000,
    )


def _make_novel() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), genre="Fantasy", writing_language="en")


def _make_assembler(
    *,
    chapters: list[SimpleNamespace] | None = None,
    kb_provider: KBContextProviderProtocol | None = None,
) -> ContextAssembler:
    """Create a ContextAssembler with mocked chapter/novel repos + a KB provider."""
    chapter_repo = AsyncMock()
    chapter_repo.list_by_novel = AsyncMock(return_value=chapters or [])

    novel_repo = AsyncMock()
    novel_repo.get_by_id = AsyncMock(return_value=_make_novel())
    novel_repo.get = AsyncMock(return_value=_make_novel())

    return ContextAssembler(
        chapter_repo=chapter_repo,
        kb_context_provider=kb_provider,
        novel_repo=novel_repo,
    )


def _bundle_with_rendered(
    *,
    characters: str,
    locations: str,
    annotate_provenance: bool,
) -> KBContextBundle:
    """Build a KBContextBundle carrying explicit rendered text (W4b test helper)."""
    from narrare.kb.context_contracts import KBContextBundle

    options = RenderOptions(annotate_provenance=annotate_provenance)
    return KBContextBundle(
        characters=_rendered(characters),
        locations=_rendered(locations),
        factions=_rendered(""),
        relationships=_rendered(""),
        render_options=options,
    )


# ---------------------------------------------------------------------------
# Canonical provider path
# ---------------------------------------------------------------------------


class TestCanonicalProviderPath:
    """Beta-reader KB context is rendered through KBContextProvider (not the dict path)."""

    @pytest.mark.asyncio
    async def test_assembler_calls_provider_with_provenance_annotation(self) -> None:
        """ContextAssembler routes through provider.fetch_context with annotate_provenance=True."""
        bundle = _bundle_with_rendered(
            characters="### Character: Alice\nA brave warrior",
            locations="### Location: Castle\nAn ancient fortress",
            annotate_provenance=True,
        )
        provider = _FakeKBContextProvider(bundle=bundle)
        ch = _make_chapter()
        assembler = _make_assembler(chapters=[ch], kb_provider=provider)

        deps = await assembler.build_context(
            novel_id=ch.novel_id, chapter_ids=[ch.id], user_id=USER_ID
        )

        assert len(provider.fetch_context_calls) == 1
        called_novel_id, called_types, called_kwargs = provider.fetch_context_calls[0]
        assert called_novel_id == ch.novel_id
        assert list(called_types) == ["character", "location"]
        options = called_kwargs["options"]
        assert isinstance(options, RenderOptions)
        assert options.annotate_provenance is True, (
            "Provider must be called with RenderOptions(annotate_provenance=True) "
            "so provenance flows (FIND-017)."
        )
        # Rendered envelope text lands on Deps as str (decision β).
        assert deps.kb_characters == "### Character: Alice\nA brave warrior"
        assert deps.kb_locations == "### Location: Castle\nAn ancient fortress"
        assert isinstance(deps.kb_characters, str)

    @pytest.mark.asyncio
    async def test_provenance_accounting_flows_into_rendered_text(self) -> None:
        """When annotate_provenance=True, the rendered text carries the provenance bracket."""
        # An uncertain entry (low confidence) gets an inline provenance bracket
        # baked into the .text by format_entities (FIND-017).
        bundle = _bundle_with_rendered(
            characters="### Character: Alice [unverified]\nA brave warrior",
            locations="",
            annotate_provenance=True,
        )
        provider = _FakeKBContextProvider(bundle=bundle)
        ch = _make_chapter()
        assembler = _make_assembler(chapters=[ch], kb_provider=provider)

        deps = await assembler.build_context(
            novel_id=ch.novel_id, chapter_ids=[ch.id], user_id=USER_ID
        )

        assert "[unverified]" in deps.kb_characters, (
            "Provenance bracket from annotate_provenance=True must reach the Deps text."
        )


# ---------------------------------------------------------------------------
# RULE-11 graceful degradation
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Empty KB / no provider → empty strings, never an exception (RULE-11)."""

    @pytest.mark.asyncio
    async def test_empty_kb_yields_empty_strings(self) -> None:
        """When the provider returns an empty bundle, Deps KB fields are empty strings."""
        from narrare.kb.context_contracts import KBContextBundle

        provider = _FakeKBContextProvider(bundle=KBContextBundle.empty(RenderOptions()))
        ch = _make_chapter()
        assembler = _make_assembler(chapters=[ch], kb_provider=provider)

        deps = await assembler.build_context(
            novel_id=ch.novel_id, chapter_ids=[ch.id], user_id=USER_ID
        )

        assert deps.kb_characters == ""
        assert deps.kb_locations == ""

    @pytest.mark.asyncio
    async def test_no_provider_degrades_to_empty_strings(self) -> None:
        """When no provider is wired, Deps KB fields degrade to empty strings (RULE-11)."""
        ch = _make_chapter()
        assembler = _make_assembler(chapters=[ch], kb_provider=None)

        deps = await assembler.build_context(
            novel_id=ch.novel_id, chapter_ids=[ch.id], user_id=USER_ID
        )

        assert deps.kb_characters == ""
        assert deps.kb_locations == ""


# ---------------------------------------------------------------------------
# Behavior preserved — agent still receives KB context
# ---------------------------------------------------------------------------


class TestBehaviorPreserved:
    """The agent still receives the KB context it needs (now via the canonical path)."""

    @pytest.mark.asyncio
    async def test_budgeted_prompt_includes_rendered_kb_text(self) -> None:
        """build_budgeted_prompt consumes the rendered Deps text end-to-end."""
        from narrare.analysis.beta_reader_prompt import build_budgeted_prompt
        from narrare_core.analysis.assembler import AnalysisContextAssembler

        bundle = _bundle_with_rendered(
            characters="### Character: Alice\nA brave warrior",
            locations="### Location: Castle\nA fortress",
            annotate_provenance=True,
        )
        provider = _FakeKBContextProvider(bundle=bundle)
        ch = _make_chapter()
        assembler = _make_assembler(chapters=[ch], kb_provider=provider)

        deps = await assembler.build_context(
            novel_id=ch.novel_id, chapter_ids=[ch.id], user_id=USER_ID
        )

        prompt = await build_budgeted_prompt(deps, AnalysisContextAssembler())

        assert "Alice" in prompt
        assert "Castle" in prompt
        assert "Characters" in prompt
        assert "Locations" in prompt
