"""Unit tests for KBSuggestedProviderImpl — edge cases.

Split from test_kb_suggested_provider.py per RULE-04 (file size limit).

Tests:
- Single entry produces one correctly-structured KBSuggestedEntity
- Fewer than five entries returns all of them
- Empty body yields a zero token_count
- Provider conforms to the KBSuggestedProvider Protocol (enricher integration)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from narrare.kb.kb_suggested_provider import KBSuggestedProviderImpl

# ---------------------------------------------------------------------------
# Helpers: minimal KBEntry factory + provider factory (self-contained per the
# test_extraction_service_edge_cases.py convention).
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
    return KBSuggestedProviderImpl(
        session_factory=MagicMock(spec=async_sessionmaker),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestKBSuggestedProviderImplEdgeCases:
    """Edge cases for the provider implementation."""

    @pytest.mark.asyncio
    async def test_single_entry_structured_correctly(self) -> None:
        """A single entry produces one KBSuggestedEntity."""
        entry_id = uuid4()
        entries = [_make_entry("Aria", usage_count=7, body="A hero.", entry_id=entry_id)]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 1))):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert len(result.entities) == 1
        entity = result.entities[0]
        assert entity.entity_id == str(entry_id)
        assert entity.name == "Aria"
        assert entity.relevance_score == 1.0
        assert entity.token_count == len("A hero.") // 4

    @pytest.mark.asyncio
    async def test_less_than_five_entries_returns_all(self) -> None:
        """When fewer than 5 entries exist, all are returned."""
        entries = [_make_entry(f"E{i}", usage_count=i) for i in range(3)]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 3))):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert len(result.entities) == 3

    @pytest.mark.asyncio
    async def test_empty_body_yields_zero_token_count(self) -> None:
        """When body is empty, token_count is 0."""
        entries = [_make_entry("NoBody", usage_count=5, body="")]
        provider = _make_provider()

        with patch.object(provider, "_get_kb_entries", new=AsyncMock(return_value=(entries, 1))):
            result = await provider.get_suggested_context(project_id=uuid4())

        assert result.entities[0].token_count == 0
        assert result.total_token_count == 0

    @pytest.mark.asyncio
    async def test_protocol_conformance(self) -> None:
        """Provider can be passed as KBSuggestedProvider to enricher."""
        from narrare_core.ai_invocation.enrichers import KBSuggestedContextEnricher

        provider = _make_provider()
        enricher = KBSuggestedContextEnricher(kb_provider=provider)

        assert enricher._provider is provider
