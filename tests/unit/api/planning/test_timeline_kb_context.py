"""§7 integration test: timeline KB-context slots are FED, not stubbed (ADR-067).

Architectural-discipline §7 distinguishes "the template declares a slot" from
"the runtime actually feeds it". This test closes that gap for the three
timeline §7 stubs that Wave 2 rewired through the canonical KB-context
provider: it asserts that when ``TimelineAnalysisService`` runs for a novel
whose KB contains characters/locations/factions, the composed
``PromptContext.extra["kb_characters"]`` / ``["kb_locations"]`` /
``["kb_factions"]`` are **NON-EMPTY at runtime** — the model genuinely
receives the data, not a literal ``""``.

The real provider + real render path (``list_entities`` /
``format_entities``) is exercised end-to-end; only the repositories are
faked, so this is the genuine service → provider → ``PromptContext`` proof
(no proxy padding). RULE-11 is covered by the empty/None-provider cases: no
exception, all slots degrade to empty strings.

See:
    .opencode/context/narrare-dev/standards/architectural-discipline.md §7
    ADR-067 — Reusable KB-Context Provider
    ADR-050 — KB Envelope (render contract)
    CONSTRAINTS.md RULE-11 (graceful degradation)
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.kb._context_provider import KBContextProvider
from narrare.planning.timeline_analysis_service import TimelineAnalysisService
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.planning._timeline_test_helpers import (
    FakeComposer,
    make_chapter,
    make_mock_agent,
    make_novel_model,
)

# ---------------------------------------------------------------------------
# Test doubles — only the repositories are faked; the render path is real.
# ---------------------------------------------------------------------------


def _entry(
    name: str,
    entity_type: str,
    *,
    body: str = "",
) -> SimpleNamespace:
    """Lightweight ``KBEntry`` stand-in (only the attributes the provider reads)."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        entity_type=entity_type,
        name=name,
        body=body,
        updated_at=None,
        metadata_={},
        status="canon",
        source="manual",
        review_status="approved",
    )


class _FakeKBRepo:
    """Fake ``KBRepositoryProtocol`` — only ``list_entries`` is exercised."""

    def __init__(self, entries: list[SimpleNamespace]) -> None:
        self.list_entries = AsyncMock(return_value=(entries, len(entries)))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def novel_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_novel_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_chapter_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_registry() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def model_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


def _wire_common(
    mock_novel_repo: AsyncMock,
    mock_chapter_repo: AsyncMock,
    mock_registry: AsyncMock,
    novel_id: uuid.UUID,
) -> None:
    """Wire the novel/chapter/registry mocks shared by every generate_timeline run."""
    mock_novel_repo.get_by_id.return_value = make_novel_model(
        id=novel_id, title="My Epic", genre="fantasy"
    )
    mock_chapter_repo.list_by_novel.return_value = [make_chapter(position=0, title="Ch 1")]
    mock_registry.get_model.return_value = MagicMock(spec=[])


# ---------------------------------------------------------------------------
# §7 proof: kb_characters / kb_locations / kb_factions NON-EMPTY at runtime
# ---------------------------------------------------------------------------


class TestTimelineKbContextFedAtRuntime:
    """The three §7 timeline slots are genuinely fed (non-empty) when the KB
    has those entity types — the documented≠implemented gap is closed."""

    @pytest.mark.asyncio
    async def test_kb_slots_non_empty_when_kb_populated(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
        model_config: ResolvedModelConfig,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """A populated KB (character + location + faction) renders into
        non-empty ``kb_characters`` / ``kb_locations`` / ``kb_factions`` in
        the composed ``PromptContext.extra`` — the model receives the data."""
        entries = [
            _entry("Elara Vance", "character", body="A gifted storm-caller."),
            _entry("The Shimmering Keep", "location", body="An ancient fortress."),
            _entry("Night Watch", "faction", body="An order of wardens."),
        ]
        # Real provider; only the KB repo is faked (no relationship repo →
        # kb_relationships degrades to empty, which is out of scope here).
        kb_context_provider = KBContextProvider(
            kb_repo=_FakeKBRepo(entries),  # type: ignore[arg-type]
            relationship_repo=None,
        )

        _wire_common(mock_novel_repo, mock_chapter_repo, mock_registry, novel_id)
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_config=model_config,
            composer=composer,  # type: ignore[arg-type]
            kb_context_provider=kb_context_provider,  # type: ignore[arg-type]
        )

        with (
            patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent,
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            MockAgent.return_value = make_mock_agent()
            await service.generate_timeline(novel_id, user_id)

        ctx = composer.last_context
        assert ctx is not None, "PromptComposer.build must receive a context."
        extra = getattr(ctx, "extra", {})

        # §7: each slot is FED (non-empty) and carries its entity name — the
        # literal "" stubs are gone, replaced by real provider output.
        assert extra["kb_characters"] != "", (
            "kb_characters must be non-empty at runtime (§7: fed, not stubbed)."
        )
        assert "Elara Vance" in extra["kb_characters"]
        assert extra["kb_locations"] != "", (
            "kb_locations must be non-empty at runtime (§7: fed, not stubbed)."
        )
        assert "Shimmering Keep" in extra["kb_locations"]
        assert extra["kb_factions"] != "", (
            "kb_factions must be non-empty at runtime (§7: fed, not stubbed)."
        )
        assert "Night Watch" in extra["kb_factions"]
        # The spread also keys kb_relationships (degraded to "" here).
        assert extra["kb_relationships"] == ""


# ---------------------------------------------------------------------------
# RULE-11: empty-but-valid (no exception) when the KB is empty / no provider
# ---------------------------------------------------------------------------


class TestTimelineKbContextGracefulDegradation:
    """RULE-11: an empty KB or an absent provider never raises; every kb_*
    slot degrades to an empty string so the template still composes."""

    @pytest.mark.asyncio
    async def test_empty_kb_with_provider_yields_empty_slots(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
        model_config: ResolvedModelConfig,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """A provider wired against an empty KB returns empty slots — no crash."""
        kb_context_provider = KBContextProvider(
            kb_repo=_FakeKBRepo([]),  # type: ignore[arg-type]
            relationship_repo=None,
        )

        _wire_common(mock_novel_repo, mock_chapter_repo, mock_registry, novel_id)
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_config=model_config,
            composer=composer,  # type: ignore[arg-type]
            kb_context_provider=kb_context_provider,  # type: ignore[arg-type]
        )

        with (
            patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent,
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            MockAgent.return_value = make_mock_agent()
            # Must not raise.
            await service.generate_timeline(novel_id, user_id)

        extra = getattr(composer.last_context, "extra", {})
        assert extra["kb_characters"] == ""
        assert extra["kb_locations"] == ""
        assert extra["kb_factions"] == ""
        assert extra["kb_relationships"] == ""

    @pytest.mark.asyncio
    async def test_no_provider_yields_empty_slots(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
        model_config: ResolvedModelConfig,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """kb_context_provider=None → the service uses KBContextBundle.empty();
        every kb_* slot is "" and generate_timeline still completes."""
        _wire_common(mock_novel_repo, mock_chapter_repo, mock_registry, novel_id)
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_config=model_config,
            composer=composer,  # type: ignore[arg-type]
            # kb_context_provider intentionally omitted → None (RULE-11).
        )

        with (
            patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent,
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            MockAgent.return_value = make_mock_agent()
            await service.generate_timeline(novel_id, user_id)

        extra = getattr(composer.last_context, "extra", {})
        assert extra["kb_characters"] == ""
        assert extra["kb_locations"] == ""
        assert extra["kb_factions"] == ""
        assert extra["kb_relationships"] == ""
