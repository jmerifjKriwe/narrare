"""Unit tests for KBSuggestedProviderImpl — formatting, edge cases, errors.

Tests the concrete KB-backed implementation of KBSuggestedProvider.
Patches the ``_get_kb_entries`` method to avoid DB dependencies.

See:
    ADR-038, ADR-039, ADR-045, CONSTRAINTS.md RULE-03/RULE-06/RULE-11.
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

if TYPE_CHECKING:
    from narrare_core.ai_invocation.enrichers.kb_suggested import KBSuggestedProvider

# ---------------------------------------------------------------------------
# Helper: minimal KBEntry factory
# ---------------------------------------------------------------------------


def _make_entry(
    name: str = "Aria",
    entity_type: str = "character",
    usage_count: int = 0,
) -> object:
    """Create a minimal KBEntry-like object for testing.

    Returns a dict-like object instead of a real DB model to avoid
    SQLAlchemy model constraints in unit tests.
    """
    from dataclasses import dataclass

    @dataclass
    class _FakeEntry:
        name: str
        entity_type: str
        usage_count: int

    return _FakeEntry(
        name=name,
        entity_type=entity_type,
        usage_count=usage_count,
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
    """Happy path: provider returns formatted string for known project."""

    @pytest.mark.asyncio
    async def test_returns_formatted_string(self) -> None:
        """Provider formats entries as 'Name (type), relevance: N.NN' lines."""
        entries = [_make_entry("Aria", "character", 10), _make_entry("Eldoria", "location", 5)]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 2))):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert "Aria (character), relevance: 1.00" in result
        assert "Eldoria (location), relevance: 0.50" in result

    @pytest.mark.asyncio
    async def test_limits_to_top_five_entries(self) -> None:
        """At most 5 entries are returned, sorted by usage_count desc."""
        entries = [_make_entry(f"Entity-{i}", usage_count=i * 10) for i in range(10)]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 10))):
            result = await provider.get_suggested_context(project_id=uuid4())

        lines = [ln for ln in result.split("\n") if ln.strip()]
        assert len(lines) == 5
        # Top entry: Entity-9 (usage_count=90)
        assert "Entity-9" in lines[0]
        assert "1.00" in lines[0]
        # Bottom entry: Entity-5 (usage_count=50)
        assert "Entity-5" in lines[-1]

    @pytest.mark.asyncio
    async def test_sorts_by_usage_count_descending(self) -> None:
        """Entries are sorted by usage_count from highest to lowest."""
        entries = [
            _make_entry("Low", usage_count=1),
            _make_entry("High", usage_count=100),
            _make_entry("Medium", usage_count=50),
        ]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 3))):
            result = await provider.get_suggested_context(project_id=uuid4())

        lines = [ln for ln in result.split("\n") if ln.strip()]
        assert len(lines) == 3
        assert "High" in lines[0]
        assert "Medium" in lines[1]
        assert "Low" in lines[2]

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

        assert "Top (character), relevance: 1.00" in result
        assert "Mid (character), relevance: 0.50" in result
        assert "Bot (character), relevance: 0.25" in result

    @pytest.mark.asyncio
    async def test_handles_all_zero_usage(self) -> None:
        """When all entries have usage_count=0, relevance is 1.00 (no div by zero)."""
        entries = [_make_entry("Aria", usage_count=0), _make_entry("Borin", usage_count=0)]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 2))):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert "relevance: 1.00" in result

    @pytest.mark.asyncio
    async def test_passes_novel_id_to_repo(self) -> None:
        """The resolved novel_id is passed to _get_kb_entries."""
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=([], 0))) as mock:
            novel_id = uuid4()
            await provider.get_suggested_context(project_id=novel_id)

            mock.assert_awaited_once_with(novel_id)


class TestEmptyKB:
    """No KB entries → returns empty string."""

    @pytest.mark.asyncio
    async def test_empty_kb_returns_empty_string(self) -> None:
        """When no entries exist, provider returns ''."""
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=([], 0))):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert result == ""


class TestNoneProjectId:
    """None project_id → returns empty string (no DB query)."""

    @pytest.mark.asyncio
    async def test_none_project_id_returns_empty(self) -> None:
        """When project_id is None, provider returns '' without querying."""
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock()) as mock:
            result = await provider.get_suggested_context(
                user_id=uuid4(),
                project_id=None,
                intent="write",
                mode="extend",
            )

            assert result == ""
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

            assert "Aria" in result
            mock.assert_awaited_once_with(novel_id)

    @pytest.mark.asyncio
    async def test_invalid_string_returns_empty(self) -> None:
        """An invalid UUID string returns '' without querying."""
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock()) as mock:
            result = await provider.get_suggested_context(project_id="not-a-uuid")

            assert result == ""
            mock.assert_not_called()


class TestGracefulDegradation:
    """Provider handles errors gracefully (RULE-11)."""

    @pytest.mark.asyncio
    async def test_repo_exception_returns_empty_string(self) -> None:
        """When _get_kb_entries raises, provider returns ''."""
        provider = _make_provider()

        with patch.object(
            provider, "_get_kb_entries", new=AsyncMock(side_effect=RuntimeError("DB down"))
        ):
            result = await provider.get_suggested_context(project_id=uuid4())

            assert result == ""


class TestKBSuggestedProviderImplEdgeCases:
    """Edge cases for the provider implementation."""

    @pytest.mark.asyncio
    async def test_single_entry_formatted_correctly(self) -> None:
        """A single entry produces one formatted line."""
        entries = [_make_entry("Aria", usage_count=7)]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 1))):
            result = await provider.get_suggested_context(project_id=uuid4())

            assert result == "Aria (character), relevance: 1.00"

    @pytest.mark.asyncio
    async def test_less_than_five_entries_returns_all(self) -> None:
        """When fewer than 5 entries exist, all are returned."""
        entries = [_make_entry(f"E{i}", usage_count=i) for i in range(3)]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 3))):
            result = await provider.get_suggested_context(project_id=uuid4())

            lines = [ln for ln in result.split("\n") if ln.strip()]
            assert len(lines) == 3

    @pytest.mark.asyncio
    async def test_protocol_conformance(self) -> None:
        """Provider can be passed as KBSuggestedProvider to enricher."""
        from narrare_core.ai_invocation.enrichers import KBSuggestedContextEnricher

        provider = _make_provider()
        enricher = KBSuggestedContextEnricher(kb_provider=provider)

        assert enricher._provider is provider
