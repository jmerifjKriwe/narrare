"""Tests for KBSuggestedContextEnricher — enrichment scenarios.

Covers: happy path with and without provider, not_applicable modes,
no adoption policy, and already populated.

See: ADR-038, ADR-039, INFRA-013, CONSTRAINTS.md RULE-10.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare_core.ai_invocation._enums import KBSuggestedRequirement
from narrare_core.ai_invocation.enrichers.kb_suggested import (
    KB_SOURCE_KEY,
    KBSuggestedContextEnricher,
)
from narrare_core.ai_invocation.models import AdoptionPolicy, PromptInvocationContext
from narrare_core.llm.intents import LLMIntent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(
    *,
    kb_requirement: KBSuggestedRequirement | None = KBSuggestedRequirement.PROVIDED,
    **overrides: object,
) -> PromptInvocationContext:
    """Create a minimal PromptInvocationContext for tests.

    Args:
        kb_requirement: The KB-suggested requirement for the adoption policy.
            ``None`` means no adoption policy is set.
        **overrides: Additional fields to override on the context.
    """
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

    # If dynamic_inputs provided, ensure it's a dict
    if "dynamic_inputs" not in defaults:
        defaults["dynamic_inputs"] = {}

    return PromptInvocationContext(**defaults)  # type: ignore[arg-type]


class FakeKBSuggestedProvider:
    """Async fake KBSuggestedProvider for testing.

    Uses a real async method to avoid the ``AsyncMock(spec=...)`` pitfall
    where spec'd attributes become plain ``MagicMock`` objects that cannot
    be awaited. The ``calls`` list records invocations for assertions.
    """

    def __init__(
        self,
        suggested_text: str = "Suggested character: John Doe, a mysterious wanderer.",
        *,
        raises: Exception | None = None,
    ) -> None:
        self._suggested_text = suggested_text
        self._raises = raises
        self.calls: list[dict[str, object]] = []

    async def get_suggested_context(
        self,
        *,
        user_id: object | None = None,
        project_id: object | None = None,
        intent: str | None = None,
        mode: str | None = None,
    ) -> str:
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
        return self._suggested_text


# ---------------------------------------------------------------------------
# 1. Happy path — with provider
# ---------------------------------------------------------------------------


class TestHappyPathWithProvider:
    """Enricher with a provider writes KB-suggested content into dynamic_inputs."""

    @pytest.mark.asyncio
    async def test_writes_kb_suggested_text(self) -> None:
        """Provider returns text, enricher writes to dynamic_inputs."""
        provider = FakeKBSuggestedProvider()
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert KB_SOURCE_KEY in result.dynamic_inputs
        assert result.dynamic_inputs[KB_SOURCE_KEY] == provider._suggested_text

    @pytest.mark.asyncio
    async def test_preserves_existing_dynamic_inputs(self) -> None:
        """Enricher does not overwrite existing dynamic_inputs keys."""
        provider = FakeKBSuggestedProvider()
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context(dynamic_inputs={"existing_key": "existing_value"})

        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs["existing_key"] == "existing_value"
        assert KB_SOURCE_KEY in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_provider_called_with_correct_ids(self) -> None:
        """Provider receives the user_id, project_id, intent, and mode from context."""
        provider = FakeKBSuggestedProvider()
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        user_id = uuid4()
        project_id = uuid4()
        ctx = _make_context(user_id=user_id, project_id=project_id, mode="draft")

        await enricher.enrich(ctx)

        assert len(provider.calls) == 1
        call = provider.calls[0]
        assert call["user_id"] == user_id
        assert call["project_id"] == project_id
        assert call["intent"] == LLMIntent.WRITE.value
        assert call["mode"] == "draft"

    @pytest.mark.asyncio
    async def test_supports_budget_rejected_requirement(self) -> None:
        """Enricher still populates kb_suggested when requirement is BUDGET_REJECTED."""
        provider = FakeKBSuggestedProvider()
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context(kb_requirement=KBSuggestedRequirement.BUDGET_REJECTED)

        result = await enricher.enrich(ctx)

        assert KB_SOURCE_KEY in result.dynamic_inputs
        assert result.dynamic_inputs[KB_SOURCE_KEY] == provider._suggested_text


# ---------------------------------------------------------------------------
# 2. No provider configured — enrichment skipped
# ---------------------------------------------------------------------------


class TestNoProviderConfigured:
    """Enricher without a provider skips enrichment gracefully."""

    @pytest.mark.asyncio
    async def test_no_provider_skips_enrichment(self) -> None:
        """When provider is None, enricher returns context unchanged."""
        enricher = KBSuggestedContextEnricher(kb_provider=None)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result is ctx
        assert KB_SOURCE_KEY not in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_no_placeholder_in_output(self) -> None:
        """When provider is None, no placeholder text appears in dynamic_inputs."""
        enricher = KBSuggestedContextEnricher(kb_provider=None)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        # Ensure no placeholder text leaked into the output
        for value in result.dynamic_inputs.values():
            assert "placeholder" not in str(value).lower()
            assert "[KB context" not in str(value)

    @pytest.mark.asyncio
    async def test_default_constructor_skips(self) -> None:
        """Default constructor (no args) works and skips enrichment."""
        enricher = KBSuggestedContextEnricher()
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result is ctx
        assert KB_SOURCE_KEY not in result.dynamic_inputs


# ---------------------------------------------------------------------------
# 2b. Provider returns empty content — enrichment skipped
# ---------------------------------------------------------------------------


class TestProviderReturnsEmpty:
    """Enricher skips enrichment when provider returns empty string."""

    @pytest.mark.asyncio
    async def test_empty_string_skips_enrichment(self) -> None:
        """When provider returns empty string, enricher skips enrichment."""
        provider = FakeKBSuggestedProvider(suggested_text="")
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result is ctx
        assert KB_SOURCE_KEY not in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_provider_was_called(self) -> None:
        """Provider is still called even when it returns empty — caller sees the call."""
        provider = FakeKBSuggestedProvider(suggested_text="")
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        await enricher.enrich(ctx)

        assert len(provider.calls) == 1


# ---------------------------------------------------------------------------
# 3. Not applicable — enricher skips
# ---------------------------------------------------------------------------


class TestNotApplicable:
    """Enricher returns context unchanged when kb_suggested is not applicable."""

    @pytest.mark.asyncio
    async def test_not_applicable_returns_original_context(self) -> None:
        """When requirement is NOT_APPLICABLE, enricher returns context unchanged."""
        enricher = KBSuggestedContextEnricher(kb_provider=FakeKBSuggestedProvider())
        ctx = _make_context(kb_requirement=KBSuggestedRequirement.NOT_APPLICABLE)

        result = await enricher.enrich(ctx)

        assert result is ctx
        assert KB_SOURCE_KEY not in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_not_applicable_no_provider_call(self) -> None:
        """When requirement is NOT_APPLICABLE, provider is never called."""
        provider = FakeKBSuggestedProvider()
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context(kb_requirement=KBSuggestedRequirement.NOT_APPLICABLE)

        await enricher.enrich(ctx)

        assert len(provider.calls) == 0


# ---------------------------------------------------------------------------
# 4. No adoption policy — enricher skips
# ---------------------------------------------------------------------------


class TestNoAdoptionPolicy:
    """Enricher returns context unchanged when there is no adoption policy."""

    @pytest.mark.asyncio
    async def test_no_policy_returns_original_context(self) -> None:
        """When adoption_policy is None, enricher returns context unchanged."""
        enricher = KBSuggestedContextEnricher(kb_provider=FakeKBSuggestedProvider())
        ctx = _make_context(kb_requirement=None)

        result = await enricher.enrich(ctx)

        assert result is ctx
        assert KB_SOURCE_KEY not in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_no_policy_no_provider_call(self) -> None:
        """When adoption_policy is None, provider is never called."""
        provider = FakeKBSuggestedProvider()
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context(kb_requirement=None)

        await enricher.enrich(ctx)

        assert len(provider.calls) == 0

    @pytest.mark.asyncio
    async def test_no_policy_does_not_add_to_dynamic_inputs(self) -> None:
        """When adoption_policy is None, dynamic_inputs is not modified."""
        enricher = KBSuggestedContextEnricher()
        ctx = _make_context(kb_requirement=None, dynamic_inputs={})

        result = await enricher.enrich(ctx)

        assert KB_SOURCE_KEY not in result.dynamic_inputs
        assert result.dynamic_inputs == {}


# ---------------------------------------------------------------------------
# 5. Already populated — enricher skips
# ---------------------------------------------------------------------------


class TestAlreadyPopulated:
    """Enricher does not overwrite existing kb_suggested in dynamic_inputs."""

    @pytest.mark.asyncio
    async def test_skips_when_already_populated(self) -> None:
        """When kb_suggested is already in dynamic_inputs, enricher skips."""
        existing_text = "Existing KB context."
        provider = FakeKBSuggestedProvider()
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context(dynamic_inputs={KB_SOURCE_KEY: existing_text})

        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[KB_SOURCE_KEY] == existing_text
        assert len(provider.calls) == 0

    @pytest.mark.asyncio
    async def test_returns_original_context_when_already_populated(self) -> None:
        """When already populated, enricher returns original context unchanged."""
        enricher = KBSuggestedContextEnricher()
        ctx = _make_context(dynamic_inputs={KB_SOURCE_KEY: "existing"})

        result = await enricher.enrich(ctx)

        assert result is ctx
