"""Unit tests for KBSuggestedProviderImpl — structured return and error handling.

Tests the concrete KB-backed implementation of KBSuggestedProvider.
Patches the ``_get_kb_entries`` method to avoid DB dependencies.

The provider returns :class:`KBSuggestionResult` (structured data) per
ADR-048 Q3. The enricher formats it into prompt text.

Edge cases live in ``test_kb_suggested_provider_edge_cases.py`` (split per
RULE-04).

See:
    ADR-038, ADR-039, ADR-045, ADR-048 Q3,
    CONSTRAINTS.md RULE-03/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from narrare.kb.kb_suggested_provider import (
    KBSuggestedProviderImpl,
    _resolve_novel_id,
)
from narrare_core.ai_invocation.enrichers.kb_suggested import (
    KBSuggestedEntity,
    KBSuggestionResult,
)

if TYPE_CHECKING:
    from narrare_core.ai_invocation.enrichers.kb_suggested import KBSuggestedProvider

# ---------------------------------------------------------------------------
# Helper: minimal KBEntry factory
# ---------------------------------------------------------------------------


def _make_entry(
    name: str = "Aria",
    entity_type: str = "character",
    usage_count: int = 0,
    body: str = "",
    entry_id: object | None = None,
) -> object:
    """Create a minimal KBEntry-like object for testing.

    Returns a dataclass-like object instead of a real DB model to avoid
    SQLAlchemy model constraints in unit tests.
    """
    from dataclasses import dataclass

    @dataclass
    class _FakeEntry:
        id: object
        name: str
        entity_type: str
        usage_count: int
        body: str

    return _FakeEntry(
        id=entry_id if entry_id is not None else uuid4(),
        name=name,
        entity_type=entity_type,
        usage_count=usage_count,
        body=body,
    )


def _make_provider() -> KBSuggestedProviderImpl:
    """Create a KBSuggestedProviderImpl with a dummy session factory.

    The ``_get_kb_entries`` method is patched in each test to return
    controlled data, so the session factory is never actually invoked.
    """
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import async_sessionmaker

    return KBSuggestedProviderImpl(
        session_factory=MagicMock(spec=async_sessionmaker),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResolveNovelId:
    """_resolve_novel_id handles various input types correctly."""

    def test_none_returns_none(self) -> None:
        assert _resolve_novel_id(None) is None

    def test_uuid_passthrough(self) -> None:
        uid = uuid4()
        assert _resolve_novel_id(uid) == uid

    def test_valid_uuid_string(self) -> None:
        uid = uuid4()
        assert _resolve_novel_id(str(uid)) == uid

    def test_invalid_string_returns_none(self) -> None:
        assert _resolve_novel_id("not-a-uuid") is None

    def test_empty_string_returns_none(self) -> None:
        assert _resolve_novel_id("") is None

    def test_integer_returns_none(self) -> None:
        assert _resolve_novel_id(42) is None


class TestKBSuggestedProviderProtocol:
    """KBSuggestedProviderImpl satisfies KBSuggestedProvider Protocol."""

    def test_structural_conformance(self) -> None:
        """Provider can be used where a KBSuggestedProvider is expected."""

        def _accepts_provider(p: KBSuggestedProvider) -> None:
            pass

        provider = _make_provider()
        _accepts_provider(provider)


class TestGetSuggestedContext:
    """Happy path: provider returns KBSuggestionResult for known project."""

    @pytest.mark.asyncio
    async def test_returns_kbsuggestionresult(self) -> None:
        """Provider returns a KBSuggestionResult, not a string."""
        entries = [
            _make_entry("Aria", "character", 10, body="A brave warrior."),
            _make_entry("Eldoria", "location", 5, body="A misty kingdom."),
        ]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 2))):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert isinstance(result, KBSuggestionResult)
        assert len(result.entities) == 2
        assert result.source == "kb_repository"

    @pytest.mark.asyncio
    async def test_entity_fields_populated_correctly(self) -> None:
        """KBSuggestedEntity fields are populated from KB entries."""
        entry_id = uuid4()
        entries = [_make_entry("Aria", "character", 10, body="A brave warrior.", entry_id=entry_id)]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 1))):
            result = await provider.get_suggested_context(project_id=uuid4())

        entity = result.entities[0]
        assert isinstance(entity, KBSuggestedEntity)
        assert entity.entity_id == str(entry_id)
        assert entity.name == "Aria"
        assert entity.entity_type == "character"
        assert entity.summary == "A brave warrior."
        assert entity.relevance_score == 1.0  # max usage → relevance 1.0
        assert entity.token_count == len("A brave warrior.") // 4
        assert entity.provenance == "kb_repository"

    @pytest.mark.asyncio
    async def test_limits_to_top_five_entries(self) -> None:
        """At most 5 entries are returned, sorted by usage_count desc."""
        entries = [_make_entry(f"Entity-{i}", usage_count=i * 10) for i in range(10)]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 10))):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert len(result.entities) == 5
        # Top entry: Entity-9 (usage_count=90) → relevance 1.0
        assert result.entities[0].name == "Entity-9"
        assert result.entities[0].relevance_score == 1.0
        # Bottom entry: Entity-5 (usage_count=50) → relevance 50/90
        assert result.entities[-1].name == "Entity-5"

    @pytest.mark.asyncio
    async def test_sorts_by_relevance_score_descending(self) -> None:
        """Entities are sorted by relevance_score from highest to lowest."""
        entries = [
            _make_entry("Low", usage_count=1),
            _make_entry("High", usage_count=100),
            _make_entry("Medium", usage_count=50),
        ]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 3))):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert len(result.entities) == 3
        assert result.entities[0].name == "High"
        assert result.entities[1].name == "Medium"
        assert result.entities[2].name == "Low"
        # Verify descending relevance
        scores = [e.relevance_score for e in result.entities]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_normalizes_relevance_to_max(self) -> None:
        """Relevance scores are normalized against the max usage_count."""
        entries = [
            _make_entry("Top", usage_count=80),
            _make_entry("Mid", usage_count=40),
            _make_entry("Bot", usage_count=20),
        ]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 3))):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert result.entities[0].relevance_score == 1.0  # 80/80
        assert result.entities[1].relevance_score == 0.5  # 40/80
        assert result.entities[2].relevance_score == 0.25  # 20/80

    @pytest.mark.asyncio
    async def test_handles_all_zero_usage(self) -> None:
        """When all entries have usage_count=0, relevance is 1.0 (no div by zero)."""
        entries = [_make_entry("Aria", usage_count=0), _make_entry("Borin", usage_count=0)]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 2))):
            result = await provider.get_suggested_context(project_id=uuid4())

        for entity in result.entities:
            assert entity.relevance_score == 1.0

    @pytest.mark.asyncio
    async def test_total_token_count_is_sum_of_entity_tokens(self) -> None:
        """total_token_count equals the sum of all entity token_counts."""
        entries = [
            _make_entry("A", usage_count=10, body="A" * 40),  # 40//4 = 10 tokens
            _make_entry("B", usage_count=5, body="B" * 20),  # 20//4 = 5 tokens
        ]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 2))):
            result = await provider.get_suggested_context(project_id=uuid4())

        expected_total = sum(e.token_count for e in result.entities)
        assert result.total_token_count == expected_total
        assert result.total_token_count == 15  # 10 + 5

    @pytest.mark.asyncio
    async def test_query_metadata_contains_useful_info(self) -> None:
        """query_metadata contains total_entries_found and query_intent."""
        entries = [_make_entry("Aria")]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 42))):
            result = await provider.get_suggested_context(
                project_id=uuid4(),
                intent="write",
            )

        assert result.query_metadata["total_entries_found"] == "42"
        assert result.query_metadata["query_intent"] == "write"

    @pytest.mark.asyncio
    async def test_query_metadata_defaults_intent_to_unknown(self) -> None:
        """query_intent defaults to 'unknown' when intent is None."""
        entries = [_make_entry("Aria")]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 1))):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert result.query_metadata["query_intent"] == "unknown"

    @pytest.mark.asyncio
    async def test_passes_novel_id_to_repo(self) -> None:
        """The resolved novel_id is passed to _get_kb_entries."""
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=([], 0))) as mock:
            novel_id = uuid4()
            await provider.get_suggested_context(project_id=novel_id)

            mock.assert_awaited_once_with(novel_id)


class TestEmptyKB:
    """No KB entries → returns empty KBSuggestionResult."""

    @pytest.mark.asyncio
    async def test_empty_kb_returns_empty_result(self) -> None:
        """When no entries exist, provider returns empty KBSuggestionResult."""
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=([], 0))):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert isinstance(result, KBSuggestionResult)
        assert result.entities == ()
        assert result.total_token_count == 0
        assert result.source == "kb_repository"


class TestNoneProjectId:
    """None project_id → returns empty result (no DB query)."""

    @pytest.mark.asyncio
    async def test_none_project_id_returns_empty_result(self) -> None:
        """When project_id is None, provider returns empty result without querying."""
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock()) as mock:
            result = await provider.get_suggested_context(
                user_id=uuid4(),
                project_id=None,
                intent="write",
                mode="extend",
            )

        assert isinstance(result, KBSuggestionResult)
        assert result.entities == ()
        assert result.total_token_count == 0
        mock.assert_not_called()


class TestStringProjectId:
    """String project_id is resolved correctly."""

    @pytest.mark.asyncio
    async def test_valid_uuid_string_resolved(self) -> None:
        """A valid UUID string is resolved and passed to _get_kb_entries."""
        entries = [_make_entry("Aria")]
        provider = _make_provider()

        with patch.object(
            provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 1))
        ) as mock:
            novel_id = uuid4()
            result = await provider.get_suggested_context(project_id=str(novel_id))

        assert isinstance(result, KBSuggestionResult)
        assert result.entities[0].name == "Aria"
        mock.assert_awaited_once_with(novel_id)

    @pytest.mark.asyncio
    async def test_invalid_string_returns_empty_result(self) -> None:
        """An invalid UUID string returns empty result without querying."""
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock()) as mock:
            result = await provider.get_suggested_context(project_id="not-a-uuid")

        assert isinstance(result, KBSuggestionResult)
        assert result.entities == ()
        mock.assert_not_called()


class TestGracefulDegradation:
    """Provider handles errors gracefully (RULE-11)."""

    @pytest.mark.asyncio
    async def test_repo_exception_returns_empty_result(self) -> None:
        """When _get_kb_entries raises, provider returns empty KBSuggestionResult."""
        provider = _make_provider()

        with patch.object(
            provider, "_get_kb_entries", new=AsyncMock(side_effect=RuntimeError("DB down"))
        ):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert isinstance(result, KBSuggestionResult)
        assert result.entities == ()
        assert result.total_token_count == 0
        assert result.source == "kb_repository"
