"""Tests for KBSuggestedContextEnricher — protocol, immutability, evidence.

Covers: provider exceptions, protocol conformance, KBSuggestedProvider protocol,
immutability, and evidence integration.

See: ADR-038, ADR-039, INFRA-013, CONSTRAINTS.md RULE-10.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare_core.ai_invocation._enums import KBSuggestedRequirement
from narrare_core.ai_invocation.enrichers.kb_suggested import (
    KB_SOURCE_KEY,
    KBSuggestedContextEnricher,
    KBSuggestedProvider,
)
from narrare_core.ai_invocation.models import AdoptionPolicy, PromptInvocationContext
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare_core.ai_invocation.contracts import ContextEnricher

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
# 6. Provider exception — graceful fallback
# ---------------------------------------------------------------------------


class TestProviderException:
    """Enricher gracefully handles provider exceptions."""

    @pytest.mark.asyncio
    async def test_provider_raises_runtime_error(self) -> None:
        """When provider raises RuntimeError, enricher returns context unchanged."""
        provider = FakeKBSuggestedProvider(raises=RuntimeError("KB service down"))
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result is ctx
        assert KB_SOURCE_KEY not in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_provider_raises_connection_error(self) -> None:
        """When provider raises ConnectionError, enricher returns unchanged."""
        provider = FakeKBSuggestedProvider(raises=ConnectionError("network failure"))
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result is ctx

    @pytest.mark.asyncio
    async def test_provider_raises_value_error(self) -> None:
        """When provider raises ValueError, enricher returns unchanged."""
        provider = FakeKBSuggestedProvider(raises=ValueError("bad data"))
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result is ctx

    @pytest.mark.asyncio
    async def test_provider_raises_type_error(self) -> None:
        """When provider raises TypeError, enricher returns unchanged."""
        provider = FakeKBSuggestedProvider(raises=TypeError("unexpected type"))
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result is ctx


# ---------------------------------------------------------------------------
# 7. Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """KBSuggestedContextEnricher satisfies ContextEnricher Protocol."""

    def test_has_enrich_method(self) -> None:
        """Enricher has the required async enrich method."""
        enricher = KBSuggestedContextEnricher()
        assert hasattr(enricher, "enrich")
        assert callable(enricher.enrich)

    @pytest.mark.asyncio
    async def test_enrich_signature_matches_protocol(self) -> None:
        """Enricher enrich method accepts and returns correct types."""
        enricher = KBSuggestedContextEnricher()
        ctx = _make_context()
        result = await enricher.enrich(ctx)
        assert isinstance(result, PromptInvocationContext)

    def test_satisfies_protocol_structurally(self) -> None:
        """KBSuggestedContextEnricher is structurally compatible with Protocol.

        This test verifies the class can be used wherever a
        ContextEnricher is expected.
        """

        def _accepts_enricher(enricher: ContextEnricher) -> None:
            pass

        # Should not raise a type error at runtime
        _accepts_enricher(KBSuggestedContextEnricher())


# ---------------------------------------------------------------------------
# 8. KBSuggestedProvider protocol conformance
# ---------------------------------------------------------------------------


class TestKBSuggestedProviderProtocol:
    """FakeKBSuggestedProvider satisfies KBSuggestedProvider Protocol."""

    def test_fake_provider_satisfies_protocol(self) -> None:
        """FakeKBSuggestedProvider can be used as a KBSuggestedProvider."""

        def _accepts_provider(provider: KBSuggestedProvider) -> None:
            pass

        _accepts_provider(FakeKBSuggestedProvider())


# ---------------------------------------------------------------------------
# 9. Immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    """Original context is never mutated."""

    @pytest.mark.asyncio
    async def test_original_context_not_mutated(self) -> None:
        """Enricher returns a new context, original stays unchanged."""
        provider = FakeKBSuggestedProvider()
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context(dynamic_inputs={})

        original_inputs = dict(ctx.dynamic_inputs)
        result = await enricher.enrich(ctx)

        # Original context is unchanged
        assert ctx.dynamic_inputs == original_inputs
        assert KB_SOURCE_KEY not in ctx.dynamic_inputs
        # Result is a new object with the enriched data
        assert result is not ctx
        assert KB_SOURCE_KEY in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_result_is_separate_object(self) -> None:
        """Enricher always returns a new PromptInvocationContext instance when enriching."""
        enricher = KBSuggestedContextEnricher(kb_provider=FakeKBSuggestedProvider())
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        # model_copy creates a new instance with different identity
        assert result is not ctx
        # But the feature_id is preserved
        assert result.feature_id == ctx.feature_id
        assert result.intent == ctx.intent

    @pytest.mark.asyncio
    async def test_not_applicable_returns_same_object(self) -> None:
        """When skipping (not_applicable), enricher returns the exact same object."""
        enricher = KBSuggestedContextEnricher()
        ctx = _make_context(kb_requirement=KBSuggestedRequirement.NOT_APPLICABLE)

        result = await enricher.enrich(ctx)

        # No copy is made when skipping
        assert result is ctx


# ---------------------------------------------------------------------------
# 10. Evidence integration — kb_suggested_status
# ---------------------------------------------------------------------------


class TestEvidenceIntegration:
    """The enriched context correctly feeds into evidence determination."""

    @pytest.mark.asyncio
    async def test_provided_status(self) -> None:
        """When enricher populates kb_suggested, evidence shows PROVIDED."""
        from narrare_core.ai_invocation._evidence import _determine_kb_suggested_status

        enricher = KBSuggestedContextEnricher(kb_provider=FakeKBSuggestedProvider())
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        status = _determine_kb_suggested_status(result)
        assert status.value == "provided"

    @pytest.mark.asyncio
    async def test_not_applicable_status(self) -> None:
        """When enricher skips (NOT_APPLICABLE), evidence shows NOT_APPLICABLE."""
        from narrare_core.ai_invocation._evidence import _determine_kb_suggested_status

        enricher = KBSuggestedContextEnricher()
        ctx = _make_context(kb_requirement=KBSuggestedRequirement.NOT_APPLICABLE)

        result = await enricher.enrich(ctx)

        status = _determine_kb_suggested_status(result)
        assert status.value == "not_applicable"

    @pytest.mark.asyncio
    async def test_missing_status_when_provider_fails(self) -> None:
        """When provider raises, evidence shows MISSING (no kb_suggested key)."""
        from narrare_core.ai_invocation._evidence import _determine_kb_suggested_status

        provider = FakeKBSuggestedProvider(raises=RuntimeError("down"))
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        status = _determine_kb_suggested_status(result)
        assert status.value == "missing"

    @pytest.mark.asyncio
    async def test_missing_status_when_no_provider(self) -> None:
        """When no provider is configured, enrichment is skipped and evidence shows MISSING."""
        from narrare_core.ai_invocation._evidence import _determine_kb_suggested_status

        enricher = KBSuggestedContextEnricher(kb_provider=None)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        status = _determine_kb_suggested_status(result)
        assert status.value == "missing"

    @pytest.mark.asyncio
    async def test_missing_status_when_provider_returns_empty(self) -> None:
        """When provider returns empty string, evidence shows MISSING."""
        from narrare_core.ai_invocation._evidence import _determine_kb_suggested_status

        provider = FakeKBSuggestedProvider(suggested_text="")
        enricher = KBSuggestedContextEnricher(kb_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        status = _determine_kb_suggested_status(result)
        assert status.value == "missing"

    @pytest.mark.asyncio
    async def test_budget_rejected_requirement_results_in_provided(self) -> None:
        """With BUDGET_REJECTED requirement, enriched context shows PROVIDED
        (the budget resolver later decides whether to reject)."""
        from narrare_core.ai_invocation._evidence import _determine_kb_suggested_status

        enricher = KBSuggestedContextEnricher(kb_provider=FakeKBSuggestedProvider())
        ctx = _make_context(kb_requirement=KBSuggestedRequirement.BUDGET_REJECTED)

        result = await enricher.enrich(ctx)

        status = _determine_kb_suggested_status(result)
        assert status.value == "provided"
