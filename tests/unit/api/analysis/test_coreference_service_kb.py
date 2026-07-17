"""KB-context population tests for CoreferenceService (ANAL-005, W4a §7).

Verifies that ``CoreferenceService.analyze`` populates the
``kb_characters`` / ``kb_locations`` / ``kb_factions`` variables in the
``PromptContext.extra`` dict with real KB data flowing through the canonical
KB-context provider (:class:`narrare.kb._context_provider.KBContextProvider`,
ADR-067), so the coreference model can map pronouns → characters and use
location/faction context for disambiguation. This closes the last two §7
stub-gaps (``kb_locations`` / ``kb_factions`` were previously literal ``""``).

The provider wires the real fetch+render path (``list_entities`` /
``format_entities``); only the repositories are faked, so this proves the
genuine service → provider → ``PromptContext.extra`` chain (no proxy padding).

Covers:

- ``kb_characters`` / ``kb_locations`` / ``kb_factions`` are NON-EMPTY at
  runtime when the KB has those entities (§7 enforcement: genuinely fed
  context, not a stub).
- All four KB-context vars are EMPTY-BUT-VALID (no exception) when no
  provider is wired — graceful degradation (RULE-11).
- All four degrade to empty when the KB fetch raises (RULE-11: the provider
  swallows repository failures and never propagates them).
- The constructor accepts and stores ``kb_context_provider``.

See:
    ADR-067 — Reusable KB-Context Provider.
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    CONSTRAINTS.md RULE-11 (graceful degradation).
    architectural-discipline.md §7 (documented ≠ implemented).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.kb._context_provider import KBContextProvider
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._coreference_test_helpers import (
    FakeComposer,
    consume,
    make_agent_output,
    make_chapter,
    make_kb_entry,
    make_novel,
    make_service,
    patch_mode1,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


def _make_kb_repo(entries: list[MagicMock]) -> AsyncMock:
    """Fake KBRepository whose paginated ``list_entries`` yields *entries*.

    ``list_entities`` calls ``list_entries(novel_id=..., page=..., page_size=100)``
    and stops once a batch is shorter than the page size, so a single page
    holding every entry terminates the pagination.
    """
    repo = AsyncMock()
    repo.list_entries.return_value = (entries, len(entries))
    return repo


def _provider_with(entries: list[MagicMock]) -> KBContextProvider:
    """Build a real ``KBContextProvider`` over a faked KB repo (no rel repo).

    ``relationship_repo=None`` makes the ``kb_relationships`` slot degrade to
    empty (RULE-11); the entity slots still render — isolating the §7
    character/location/faction chain.
    """
    return KBContextProvider(kb_repo=_make_kb_repo(entries), relationship_repo=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# §7 enforcement: kb_characters / kb_locations / kb_factions fed at runtime
# ---------------------------------------------------------------------------


class TestKBContextPopulation:
    """All three entity slots are fed from the real provider at runtime (§7)."""

    @pytest.mark.asyncio
    async def test_kb_entity_slots_nonempty_when_kb_has_entities(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """§7: ``kb_characters`` / ``kb_locations`` / ``kb_factions`` are
        NON-EMPTY at runtime when the KB has those entities — genuinely fed
        through the provider, not literal stubs."""
        entries = [
            make_kb_entry(entity_type="character", name="Alice", body="A brave hero."),
            make_kb_entry(entity_type="character", name="Bob", body="A mysterious stranger."),
            make_kb_entry(entity_type="location", name="Castle", body="A tall keep."),
            make_kb_entry(entity_type="faction", name="Thieves Guild", body="A shadowy syndicate."),
            # Non-slot entity types are fetched-but-ignored by the provider.
            make_kb_entry(entity_type="item", name="Sword", body="A sharp blade."),
        ]

        service = make_service(composer, config, kb_context_provider=_provider_with(entries))
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (_MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            _MockAgent.return_value = mock_agent

            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None, "prompt_context must be supplied to compose_invocation."
        kb_chars = ctx.extra["kb_characters"]
        kb_locs = ctx.extra["kb_locations"]
        kb_facs = ctx.extra["kb_factions"]
        # All three slots genuinely fed (§7): the entity names appear.
        assert "Alice" in kb_chars and "Bob" in kb_chars, (
            "kb_characters must list the Alice and Bob characters."
        )
        assert "Castle" in kb_locs, "kb_locations must list the Castle location."
        assert "Thieves Guild" in kb_facs, "kb_factions must list the Thieves Guild faction."
        # Non-slot entity types do NOT leak into the three slots.
        assert "Sword" not in kb_chars, "kb_characters must exclude non-character entities."
        assert "Sword" not in kb_locs, "kb_locations must exclude non-location entities."
        assert "Sword" not in kb_facs, "kb_factions must exclude non-faction entities."

    @pytest.mark.asyncio
    async def test_kb_entity_slots_empty_when_provider_is_none(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """kb_context_provider=None → graceful degradation (RULE-11).

        The service falls back to ``KBContextBundle.empty()`` so every kb_*
        slot is an empty string and the template's variable substitution
        still succeeds without an exception (backward-compat: callers that
        omit the provider keep working).
        """
        service = make_service(composer, config)  # provider omitted → None
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (_MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            _MockAgent.return_value = mock_agent

            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None
        assert ctx.extra["kb_characters"] == "", (
            "kb_characters must be empty when no provider is wired (RULE-11)."
        )
        assert ctx.extra["kb_locations"] == "", (
            "kb_locations must be empty when no provider is wired (RULE-11)."
        )
        assert ctx.extra["kb_factions"] == "", (
            "kb_factions must be empty when no provider is wired (RULE-11)."
        )
        assert ctx.extra["kb_relationships"] == "", (
            "kb_relationships must be empty when no provider is wired (RULE-11)."
        )

    @pytest.mark.asyncio
    async def test_kb_entity_slots_empty_when_kb_fetch_raises(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """RULE-11: a KB fetch failure degrades to empty (provider swallows it).

        The provider catches repository failures and returns an empty bundle
        rather than propagating the exception; coreference can still run,
        just less accurately. The error must NOT reach the caller.
        """
        kb_repo = AsyncMock()
        kb_repo.list_entries.side_effect = RuntimeError("DB connection lost")
        provider = KBContextProvider(kb_repo=kb_repo, relationship_repo=None)  # type: ignore[arg-type]

        service = make_service(composer, config, kb_context_provider=provider)
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (_MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            _MockAgent.return_value = mock_agent

            # Must NOT raise — the KB failure is swallowed by the provider (RULE-11).
            events = await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        # Analysis still completes (result + done events).
        assert len(events) == 2
        assert events[1].event == "done"

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None
        assert ctx.extra["kb_characters"] == "", (
            "kb_characters must be empty when the KB fetch raises (RULE-11)."
        )
        assert ctx.extra["kb_locations"] == "", (
            "kb_locations must be empty when the KB fetch raises (RULE-11)."
        )
        assert ctx.extra["kb_factions"] == "", (
            "kb_factions must be empty when the KB fetch raises (RULE-11)."
        )


# ---------------------------------------------------------------------------
# Constructor wiring
# ---------------------------------------------------------------------------


class TestCoreferenceServiceConstructor:
    """The constructor accepts and stores the optional ``kb_context_provider``."""

    def test_constructor_stores_kb_context_provider(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare.analysis.coreference_service import CoreferenceService
        from tests.unit.api.analysis._coreference_test_helpers import FakeModelRegistry

        provider = KBContextProvider(kb_repo=None, relationship_repo=None)

        service = CoreferenceService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_config=config,
            composer=composer,  # type: ignore[arg-type]
            kb_context_provider=provider,
        )

        assert service._kb_context_provider is provider, (
            "Constructor must store kb_context_provider."
        )

    def test_constructor_defaults_kb_context_provider_to_none(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare.analysis.coreference_service import CoreferenceService
        from tests.unit.api.analysis._coreference_test_helpers import FakeModelRegistry

        service = CoreferenceService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_config=config,
            composer=composer,  # type: ignore[arg-type]
        )

        assert service._kb_context_provider is None, (
            "kb_context_provider must default to None (graceful degradation)."
        )
