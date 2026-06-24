"""Tests for KBSuggestedContextEnricher — formatting and structured data injection.

Split from ``test_kb_suggested_enrich.py`` to respect RULE-04 (file size limit).

Covers: formatted text output, structured result injection, multiple entities,
and the _format_entities format contract.

See: ADR-048 Q3, CONSTRAINTS.md RULE-04/RULE-10.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare_core.ai_invocation._enums import KBSuggestedRequirement
from narrare_core.ai_invocation.enrichers.kb_suggested import (
    KB_SOURCE_KEY,
    KB_STRUCTURED_KEY,
    KBSuggestedContextEnricher,
    KBSuggestedEntity,
    KBSuggestionResult,
)
from narrare_core.ai_invocation.models import AdoptionPolicy, PromptInvocationContext
from narrare_core.llm.intents import LLMIntent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity(**overrides: object) -> KBSuggestedEntity:
    """Create a valid KBSuggestedEntity with sensible defaults."""
    defaults: dict[str, object] = {
        "entity_id": "char-001",
        "name": "John Doe",
        "entity_type": "character",
        "summary": "A mysterious wanderer.",
        "relevance_score": 0.85,
        "token_count": 120,
        "provenance": "kb_repository",
    }
    defaults.update(overrides)
    return KBSuggestedEntity(**defaults)  # type: ignore[arg-type]


def _make_result(
    entities: tuple[KBSuggestedEntity, ...] | None = None,
    **overrides: object,
) -> KBSuggestionResult:
    """Create a KBSuggestionResult with sensible defaults."""
    if entities is None:
        entities = (_make_entity(),)
    total = sum(e.token_count for e in entities)
    defaults: dict[str, object] = {
        "entities": entities,
        "total_token_count": total,
        "source": "kb_repository",
    }
    defaults.update(overrides)
    return KBSuggestionResult(**defaults)  # type: ignore[arg-type]


def _make_context(
    *,
    kb_requirement: KBSuggestedRequirement | None = KBSuggestedRequirement.PROVIDED,
    **overrides: object,
) -> PromptInvocationContext:
    """Create a minimal PromptInvocationContext for tests."""
    defaults: dict[str, object] = {
        "feature_id": "test/feature",
        "intent": LLMIntent.WRITE,
        "user_id": uuid4(),
        "project_id": uuid4(),
    }
    defaults.update(overrides)

    if "adoption_policy" not in defaults and kb_requirement is not None:
        defaults["adoption_policy"] = AdoptionPolicy(
            kb_suggested_requirement=kb_requirement,
        )
    elif "adoption_policy" not in defaults:
        defaults["adoption_policy"] = None

    if "dynamic_inputs" not in defaults:
        defaults["dynamic_inputs"] = {}

    return PromptInvocationContext(**defaults)  # type: ignore[arg-type]


class FakeKBSuggestedProvider:
    """Async fake KBSuggestedProvider for testing."""

    def __init__(
        self,
        result: KBSuggestionResult | None = None,
        *,
        raises: Exception | None = None,
    ) -> None:
        self._result = result if result is not None else _make_result()
        self._raises = raises
        self.calls: list[dict[str, object]] = []

    async def get_suggested_context(
        self,
        *,
        user_id: object | None = None,
        project_id: object | None = None,
        intent: str | None = None,
        mode: str | None = None,
    ) -> KBSuggestionResult:
        self.calls.append(
            {
                "user_id": user_id,
                "project_id": project_id,
                "intent": intent,
                "mode": mode,
            },
        )
        if self._raises is not None:
            raise self._raises
        return self._result


# ---------------------------------------------------------------------------
# Formatted text output
# ---------------------------------------------------------------------------


class TestFormattedTextOutput:
    """_format_entities produces backward-compatible prompt text."""

    @pytest.mark.asyncio
    async def test_formatted_text_matches_expected_format(self) -> None:
        """Formatted text uses the _format_entities format."""
        entity = _make_entity(name="Alice", entity_type="location", relevance_score=0.5)
        provider = FakeKBSuggestedProvider(result=_make_result(entities=(entity,)))
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[KB_SOURCE_KEY] == "Alice (location), relevance: 0.50"

    @pytest.mark.asyncio
    async def test_multiple_entities_formatted(self) -> None:
        """Multiple entities are formatted as separate lines."""
        e1 = _make_entity(entity_id="1", name="Alice", entity_type="location")
        e2 = _make_entity(entity_id="2", name="Bob", entity_type="character")
        provider = FakeKBSuggestedProvider(result=_make_result(entities=(e1, e2)))
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        text = result.dynamic_inputs[KB_SOURCE_KEY]
        assert "Alice (location)" in text
        assert "Bob (character)" in text
        assert text.count("\n") == 1  # two lines, one newline

    @pytest.mark.asyncio
    async def test_relevance_score_formatted_to_two_decimals(self) -> None:
        """Relevance score is formatted to 2 decimal places."""
        entity = _make_entity(relevance_score=0.123456)
        provider = FakeKBSuggestedProvider(result=_make_result(entities=(entity,)))
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert "relevance: 0.12" in result.dynamic_inputs[KB_SOURCE_KEY]


# ---------------------------------------------------------------------------
# Structured result injection
# ---------------------------------------------------------------------------


class TestStructuredResultInjection:
    """kb_suggested_structured carries the KBSuggestionResult for budget/evidence."""

    @pytest.mark.asyncio
    async def test_writes_structured_result(self) -> None:
        """Enricher injects the structured KBSuggestionResult alongside text."""
        provider = FakeKBSuggestedProvider()
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert KB_STRUCTURED_KEY in result.dynamic_inputs
        structured = result.dynamic_inputs[KB_STRUCTURED_KEY]
        assert isinstance(structured, KBSuggestionResult)
        assert len(structured.entities) == 1
        assert structured.entities[0].name == "John Doe"

    @pytest.mark.asyncio
    async def test_structured_result_carries_token_counts(self) -> None:
        """Structured result carries per-entity token counts for budget resolver."""
        e1 = _make_entity(entity_id="1", token_count=100)
        e2 = _make_entity(entity_id="2", token_count=200)
        provider = FakeKBSuggestedProvider(result=_make_result(entities=(e1, e2)))
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        structured = result.dynamic_inputs[KB_STRUCTURED_KEY]
        assert isinstance(structured, KBSuggestionResult)
        assert structured.entities[0].token_count == 100
        assert structured.entities[1].token_count == 200
        assert structured.total_token_count == 300

    @pytest.mark.asyncio
    async def test_structured_result_carries_provenance(self) -> None:
        """Structured result carries provenance for evidence correlation."""
        entity = _make_entity(provenance="wiki_cache")
        provider = FakeKBSuggestedProvider(result=_make_result(entities=(entity,)))
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        structured = result.dynamic_inputs[KB_STRUCTURED_KEY]
        assert isinstance(structured, KBSuggestionResult)
        assert structured.entities[0].provenance == "wiki_cache"

    @pytest.mark.asyncio
    async def test_both_keys_populated_together(self) -> None:
        """Both kb_suggested (text) and kb_suggested_structured (data) are set."""
        provider = FakeKBSuggestedProvider()
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert KB_SOURCE_KEY in result.dynamic_inputs
        assert KB_STRUCTURED_KEY in result.dynamic_inputs
        assert isinstance(result.dynamic_inputs[KB_SOURCE_KEY], str)
        assert isinstance(result.dynamic_inputs[KB_STRUCTURED_KEY], KBSuggestionResult)
