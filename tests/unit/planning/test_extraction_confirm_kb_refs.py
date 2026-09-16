"""§7 follow-up: extracted names → real KB entity refs in confirm_extracted_event.

``confirm_extracted_event`` resolves the ``character_names`` / ``location_name``
carried on an :class:`ExtractedTemporalExpression` against the novel's KB
entities and persists real ``character_refs`` / ``location_ref`` (the wire
shape the cross-feature ref-index tracks by id). This is the genuine wiring
proof (§7): the real ``KBContextProvider`` + ``list_entities`` fetch path is
exercised — only the KB repo is faked (ADR-030) — so the refs carry real KB
entity ids, not proxy padding.

RULE-11 coverage: an absent provider and a failing KB fetch both degrade to
empty refs without raising — the event is still created.

Split from ``test_extraction_confirm.py`` to respect the test-file size limit
(RULE-04). Shared value-container factories come from
``_extraction_confirm_helpers``.

See:
    .opencode/context/narrare-dev/standards/architectural-discipline.md §7
    apps/api/narrare/planning/_extracted_event_refs.py
    CONSTRAINTS.md RULE-11 (graceful degradation)
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from narrare.kb._context_provider import KBContextProvider
from narrare.planning.timeline_analysis_service import TimelineAnalysisService
from narrare_core.agents.temporal_extraction_types import ExtractedTemporalExpression
from tests.unit.planning._extraction_confirm_helpers import make_event, make_novel
from tests.unit.planning._timeline_test_helpers import make_static_resolution


def _kb_entry(name: str, entity_type: str) -> SimpleNamespace:
    """Lightweight KBEntry stand-in (only id/name/entity_type are exercised)."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        entity_type=entity_type,
        body="",
        updated_at=None,
        metadata_={},
        status="canon",
        source="manual",
        review_status="approved",
    )


class _FakeKBRepo:
    """Fake KB repository — only ``list_entries`` is exercised by the provider."""

    def __init__(self, entries: list[SimpleNamespace]) -> None:
        self.list_entries = AsyncMock(return_value=(entries, len(entries)))


class _FailingKBRepo:
    """KB repository whose ``list_entries`` always raises (RULE-11 path)."""

    def __init__(self) -> None:
        self.list_entries = AsyncMock(side_effect=RuntimeError("kb offline"))


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
def mock_event_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_registry() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def extracted_with_names() -> ExtractedTemporalExpression:
    return ExtractedTemporalExpression(
        expression="three days later",
        event_name="Arrival",
        timestamp_raw="Day 3",
        chapter_reference="Ch 1",
        character_names=["Hero", "Sage"],
        location_name="Castle",
        confidence=0.9,
        context="After three days, they reached the castle.",
    )


class TestConfirmExtractedEventKbRefs:
    """``confirm_extracted_event`` resolves extracted names against KB entities
    and passes real ``character_refs`` / ``location_ref`` to the event repo.

    The genuine ``KBContextProvider`` + ``list_entities`` fetch path is
    exercised (ADR-030 real-behavior fake — only the KB repo is faked), so this
    is the real wiring proof (§7), not proxy padding. RULE-11: an absent
    provider or a failing fetch degrades to empty refs without raising."""

    async def test_matching_names_populate_real_entity_refs(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
        extracted_with_names: ExtractedTemporalExpression,
    ) -> None:
        """character_names/location_name that match KB entities link real ids."""
        hero = _kb_entry("Hero", "character")
        sage = _kb_entry("Sage", "character")
        castle = _kb_entry("Castle", "location")
        kb_provider = KBContextProvider(
            kb_repo=_FakeKBRepo([hero, sage, castle]),  # type: ignore[arg-type]
            relationship_repo=None,
        )
        mock_novel_repo.get_by_id.return_value = make_novel(id=novel_id)
        mock_event_repo.create.return_value = make_event(novel_id=novel_id)

        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_resolution=make_static_resolution(),
            event_repo=mock_event_repo,
            kb_context_provider=kb_provider,  # type: ignore[arg-type]
        )

        await service.confirm_extracted_event(novel_id, user_id, extracted_with_names)

        call_kwargs = mock_event_repo.create.call_args.kwargs
        # Real KB entity links (id-presence is the §7 correctness proof).
        assert call_kwargs["character_refs"] == [
            {"id": str(hero.id), "name": "Hero"},
            {"id": str(sage.id), "name": "Sage"},
        ]
        assert call_kwargs["location_ref"] == {"id": str(castle.id), "name": "Castle"}

    async def test_non_matching_names_are_omitted(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
        extracted_with_names: ExtractedTemporalExpression,
    ) -> None:
        """Names with no matching KB entity are omitted (no proxy padding)."""
        # Only Hero + Castle exist; "Sage" has no entity.
        hero = _kb_entry("Hero", "character")
        castle = _kb_entry("Castle", "location")
        kb_provider = KBContextProvider(
            kb_repo=_FakeKBRepo([hero, castle]),  # type: ignore[arg-type]
            relationship_repo=None,
        )
        mock_novel_repo.get_by_id.return_value = make_novel(id=novel_id)
        mock_event_repo.create.return_value = make_event(novel_id=novel_id)

        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_resolution=make_static_resolution(),
            event_repo=mock_event_repo,
            kb_context_provider=kb_provider,  # type: ignore[arg-type]
        )

        await service.confirm_extracted_event(novel_id, user_id, extracted_with_names)

        call_kwargs = mock_event_repo.create.call_args.kwargs
        assert call_kwargs["character_refs"] == [{"id": str(hero.id), "name": "Hero"}]
        assert call_kwargs["location_ref"] == {"id": str(castle.id), "name": "Castle"}

    async def test_no_kb_provider_yields_empty_refs_event_still_created(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
        extracted_with_names: ExtractedTemporalExpression,
    ) -> None:
        """No provider wired → empty refs, event still created, no exception."""
        mock_novel_repo.get_by_id.return_value = make_novel(id=novel_id)
        mock_event_repo.create.return_value = make_event(novel_id=novel_id)
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_resolution=make_static_resolution(),
            event_repo=mock_event_repo,
        )

        await service.confirm_extracted_event(novel_id, user_id, extracted_with_names)

        call_kwargs = mock_event_repo.create.call_args.kwargs
        assert call_kwargs["character_refs"] == []
        assert call_kwargs["location_ref"] is None
        # Event creation still happened.
        assert mock_event_repo.create.await_count == 1

    async def test_failing_kb_fetch_yields_empty_refs_event_still_created(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
        extracted_with_names: ExtractedTemporalExpression,
    ) -> None:
        """RULE-11: a failing KB fetch degrades to empty refs — no exception."""
        kb_provider = KBContextProvider(
            kb_repo=_FailingKBRepo(),  # type: ignore[arg-type]
            relationship_repo=None,
        )
        mock_novel_repo.get_by_id.return_value = make_novel(id=novel_id)
        mock_event_repo.create.return_value = make_event(novel_id=novel_id)

        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_resolution=make_static_resolution(),
            event_repo=mock_event_repo,
            kb_context_provider=kb_provider,  # type: ignore[arg-type]
        )

        # Must NOT raise — the event is still created with empty refs.
        await service.confirm_extracted_event(novel_id, user_id, extracted_with_names)

        call_kwargs = mock_event_repo.create.call_args.kwargs
        assert call_kwargs["character_refs"] == []
        assert call_kwargs["location_ref"] is None
        assert mock_event_repo.create.await_count == 1
