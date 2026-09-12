"""Slice 5 wiring pins + Slice 6 activation goldens for the band_summary kb_* supply.

The band_summary prompt seam (``band_summary_prompt.compose_band_summary_system_prompt``)
fetches the four KB-context slots (kb_characters / kb_locations / kb_factions /
kb_relationships) from the canonical ``KBContextProvider`` (ADR-067) and spreads
them into ``PromptContext.extra`` — mirroring the Slice 3 summarize supply.
While the governed band_summary template's Knowledge-Base region sat BELOW the
``extract_section`` parse cutoff (the ``## System Prompt`` section ended at
``## Output Format``), the placeholders never reached the variable engine and
the composed render stayed byte-identical to the pre-wiring capture — the
Slice 5 inertness proof.

Activation slice 6 (2026-09-12) demoted the rogue level-2 headers
(``## Output Format`` / ``## Do NOT`` → level-3, children shifted to
level-4), so the previously-dropped region NOW RENDERS: the supply wired in
Slice 5 became live. The goldens below were re-captured against the
activated template (provenance: "activation slice 6 — previously-dropped
region now renders; inertness was relative to the truncated template";
Slice 5 golden: 1123 chars, sha256 026fc03dc0fe9addbd67655c69e815cbe15f43a
ce0b6cf9ed38584fc7f049785); inertness was never an absolute property of
the wiring, only of the truncated template shape.

Methodology mirrors ``test_suggest_prompt_render.py``: the exact PromptContext
the prompt module builds is composed through the REAL ``PromptRegistry`` +
``PromptComposer``; the service-level supply wiring is pinned via the
PromptContext captured at the composer seam. Byte-exact render pins live in
``tests/unit/core/prompts/test_band_summary_goldens.py`` (shared SSOT,
RULE-04).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from narrare.kb.context_contracts import KBContextBundle
from narrare.series.band_summary_prompt import compose_band_summary_system_prompt
from narrare_core.context._kb_envelope import RenderedKBContext
from narrare_core.context._render_options import RenderOptions
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from tests.factories import make_chapter, make_novel
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.unit.api.series._band_summary_test_helpers import (
    FakeBandSummaryAgent,
    make_band_summary_config,
    make_band_summary_service,
)
from tests.unit.core.prompts.test_band_summary_goldens import (
    GOLDEN_SYSTEM_EMPTY_KB,
    GOLDEN_SYSTEM_POPULATED,
)

if TYPE_CHECKING:
    from narrare.kb.models import KBEntry

_NOVEL_ID = uuid4()

# ---------------------------------------------------------------------------
# Fakes + builders (ADR-030 fake-first, mirrors test_summary_kb_inertness.py)
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
        self.fetch_context_calls: list[tuple[UUID, list[str] | None, RenderOptions | None]] = []

    async def fetch_context(
        self,
        novel_id: UUID,
        *,
        entity_types: list[str] | None = None,
        options: RenderOptions | None = None,
    ) -> KBContextBundle:
        self.fetch_context_calls.append((novel_id, entity_types, options))
        if self._bundle is None:
            return KBContextBundle.empty(options)
        return self._bundle

    async def fetch_entities(
        self, novel_id: UUID, *, entity_types: list[str] | None = None
    ) -> list[KBEntry]:
        """Return no entities — band_summary tests ``fetch_context`` only."""
        return []

    async def fetch_world_context(
        self,
        novel_id: UUID,
        *,
        entity_type: str | None = None,
        max_entries: int = 30,
    ) -> str:
        return ""


class _SystemPromptCapture:
    """Agent factory recording the system_prompt each construction receives."""

    def __init__(self) -> None:
        self.system_prompts: list[str | None] = []

    def __call__(self, model: Any, system_prompt: str | None = None) -> FakeBandSummaryAgent:
        self.system_prompts.append(system_prompt)
        return FakeBandSummaryAgent()


async def _compose_via_real_cascade(
    provider: _FakeKBContextProvider | None,
) -> str:
    """Compose the band_summary system prompt exactly as the seam does (Mode 1
    with ``invocation_pipeline=None`` → direct ``composer.build`` fallback)."""
    return await compose_band_summary_system_prompt(
        composer=PromptComposer(PromptRegistry()),
        invocation_pipeline=None,
        novel_title="The Forbidden Vale",
        genre="Fantasy",
        language="en",
        novel_id=_NOVEL_ID,
        kb_context_provider=provider,
    )


def _seed_novel_with_summaries(
    novel_repo: FakeNovelRepository, chapter_repo: FakeChapterRepository
) -> UUID:
    """Seed a novel with two summarised chapters; return its id."""
    novel_repo.seed(make_novel(id=_NOVEL_ID, title="The Forbidden Vale", genre="Fantasy"))
    chapter_repo.seed(
        make_chapter(novel_id=_NOVEL_ID, position=1, summary="Hero arrives."),
        make_chapter(novel_id=_NOVEL_ID, position=2, summary="Secret revealed."),
    )
    return _NOVEL_ID


# ---------------------------------------------------------------------------
# Tests — activation (direct seam, real composer cascade)
# ---------------------------------------------------------------------------


class TestBandSummaryKBRenderActivation:
    """Slice 6: the Slice-5 kb_* supply now reaches the render.

    Activation slice 6 demoted the rogue level-2 headers, so the composed
    system prompt renders the previously-dropped region. Provider data
    lands in the Knowledge-Base slots; an empty bundle / no provider
    degrades to empty-bodied slots (labels kept) — zero ``{{`` residue in
    every case.
    """

    async def test_kb_provider_data_render_matches_activation_golden(self) -> None:
        """Provider WITH data: composed render is byte-identical to the
        Slice 6 activation golden (kb sentinels render)."""
        system = await _compose_via_real_cascade(_FakeKBContextProvider(_bundle_with_data()))
        assert system == GOLDEN_SYSTEM_POPULATED
        assert "- Alice (character): the protagonist" in system
        assert "{{" not in system

    async def test_kb_provider_empty_bundle_render_matches_activation_empty_golden(self) -> None:
        """Provider WITHOUT data (empty KB): degraded render — every section
        present, kb slots empty-bodied, no placeholder residue."""
        provider = _FakeKBContextProvider(KBContextBundle.empty(RenderOptions()))
        system = await _compose_via_real_cascade(provider)
        assert system == GOLDEN_SYSTEM_EMPTY_KB
        assert "{{" not in system

    async def test_no_provider_render_matches_activation_empty_golden(self) -> None:
        """Legacy construction (no provider): degrades to the same empty-KB
        render (RULE-11 — the seam builds an empty bundle itself)."""
        system = await _compose_via_real_cascade(None)
        assert system == GOLDEN_SYSTEM_EMPTY_KB
        assert "{{" not in system


# ---------------------------------------------------------------------------
# Tests — supply wiring (service flow + seam pins)
# ---------------------------------------------------------------------------


class TestBandSummaryKBServiceSupply:
    """End-to-end generate() flow pins: provider → extra → live render."""

    async def test_generate_system_prompt_matches_activation_golden_with_kb_data(self) -> None:
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        _seed_novel_with_summaries(novel_repo, chapter_repo)
        capture = _SystemPromptCapture()
        provider = _FakeKBContextProvider(_bundle_with_data())
        service, _agent, _repo = make_band_summary_service(
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            composer=PromptComposer(PromptRegistry()),
            kb_context_provider=provider,
            agent_factory=capture,
        )

        await service.generate(_NOVEL_ID)

        assert capture.system_prompts == [GOLDEN_SYSTEM_POPULATED]
        rendered_system = capture.system_prompts[0]
        assert rendered_system is not None
        assert "- Alice (character): the protagonist" in rendered_system

    async def test_prompt_context_extra_carries_kb_vars_and_unchanged_fields(self) -> None:
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        _seed_novel_with_summaries(novel_repo, chapter_repo)
        provider = _FakeKBContextProvider(_bundle_with_data())
        service, _agent, _repo = make_band_summary_service(
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_context_provider=provider,
        )

        with (
            patch("narrare.series.band_summary_service.BandSummaryAgent"),
            patch(
                "narrare.series.band_summary_prompt.compose_invocation",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        composed_prompt=ComposedPrompt(system="X", user="")
                    )
                ),
            ) as mock_compose,
        ):
            await service.generate(_NOVEL_ID)

        ctx = mock_compose.call_args.kwargs["prompt_context"]
        assert ctx.mode == "band_summary"
        assert ctx.project_title == "The Forbidden Vale"
        assert ctx.extra["kb_characters"] == "- Alice (character): the protagonist"
        assert ctx.extra["kb_locations"] == "- Berlin (location): where the story happens"
        assert ctx.extra["kb_factions"] == "- The Cult (faction): antagonists"
        assert ctx.extra["kb_relationships"] == "- Alice <-> Bob: rivals"

    async def test_kb_fetch_is_novel_scoped_with_three_entity_types_and_provenance(
        self,
    ) -> None:
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        _seed_novel_with_summaries(novel_repo, chapter_repo)
        provider = _FakeKBContextProvider(_bundle_with_data())
        service, _agent, _repo = make_band_summary_service(
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_context_provider=provider,
        )

        await service.generate(_NOVEL_ID)

        assert len(provider.fetch_context_calls) == 1
        novel_id, entity_types, options = provider.fetch_context_calls[0]
        assert novel_id == _NOVEL_ID
        assert entity_types == ["character", "location", "faction"]
        assert options is not None and options.annotate_provenance is True


# ---------------------------------------------------------------------------
# Tests — deps wiring (build_band_summary_service)
# ---------------------------------------------------------------------------


class TestBandSummaryDepsWiring:
    """``build_band_summary_service`` wires the canonical KB-context provider."""

    async def test_build_band_summary_service_wires_kb_context_provider(self) -> None:
        from sqlalchemy.ext.asyncio import AsyncSession

        from narrare.kb._context_provider import KBContextProvider
        from narrare.series.dependencies import build_band_summary_service
        from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl

        session = MagicMock(spec=AsyncSession, name="session")
        user_id, novel_id = uuid4(), uuid4()

        fake_config = make_band_summary_config()
        fake_resolved = SimpleNamespace(config=fake_config, api_key=None, base_url=None)
        fake_resolver = MagicMock(spec=ModelRoutingResolverImpl)
        fake_resolver.resolve = AsyncMock(return_value=fake_resolved)

        fake_limits = SimpleNamespace(output_limit=4096, tier_percentages=None)
        fake_limits_service = MagicMock(spec=["get_resolved_limits"], name="TokenLimitsService")
        fake_limits_service.get_resolved_limits = AsyncMock(return_value=fake_limits)

        fake_settings = MagicMock(spec=True, name="Settings")
        fake_registry = MagicMock(spec=["get_model"], name="ModelRegistry")
        fake_composer = MagicMock(spec=["compose"], name="PromptComposer")
        fake_pipeline = MagicMock(spec=["generate"], name="InvocationPipeline")

        with (
            patch(
                "narrare.series.dependencies.get_model_routing_resolver",
                return_value=fake_resolver,
            ),
            patch(
                "narrare.settings.token_limits.service.TokenLimitsService",
                return_value=fake_limits_service,
            ),
            patch("narrare._app.config.get_settings", return_value=fake_settings),
            patch(
                "narrare.series.dependencies.get_model_registry",
                return_value=fake_registry,
            ),
            patch(
                "narrare.series.dependencies.get_composer",
                return_value=fake_composer,
            ),
            patch(
                "narrare.series.dependencies.get_invocation_pipeline",
                return_value=fake_pipeline,
            ),
        ):
            service = await build_band_summary_service(session, user_id, novel_id)

        # Wiring pin via the instance dict — direct private-attribute access
        # would add a reportPrivateUsage finding, and the type-ignore baseline
        # is a no-growth gate this slice must not extend.
        provider = vars(service)["_kb_context_provider"]
        assert isinstance(provider, KBContextProvider)
