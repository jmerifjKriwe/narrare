"""Tests for PreferenceContextEnricherImpl.

Covers: happy path, null provider, missing IDs, provider exceptions,
empty profiles, protocol conformance, and immutability.

See: ADR-038, INFRA-013, CONSTRAINTS.md RULE-10.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare_core.ai_invocation.enrichers.preferences import (
    PREFERENCE_KEY,
    PreferenceContextEnricherImpl,
)
from narrare_core.ai_invocation.models import PromptInvocationContext
from narrare_core.llm.intents import LLMIntent
from narrare_core.memory.models import PreferenceProfile

if TYPE_CHECKING:
    from narrare_core.ai_invocation.contracts import PreferenceContextEnricher

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(**overrides: object) -> PromptInvocationContext:
    """Create a minimal PromptInvocationContext for tests."""
    defaults: dict[str, object] = {
        "feature_id": "test/feature",
        "intent": LLMIntent.WRITE,
        "user_id": uuid4(),
        "project_id": uuid4(),
    }
    defaults.update(overrides)
    return PromptInvocationContext(**defaults)  # type: ignore[arg-type]


def _make_profile(**overrides: object) -> PreferenceProfile:
    """Create a PreferenceProfile for tests."""
    defaults: dict[str, object] = {
        "user_id": uuid4(),
        "project_id": uuid4(),
        "event_count": 5,
        "confidence": 0.8,
        "style": {"short_sentences": "Preferred"},
        "content": {"dialogue_heavy": "Likes dialogue"},
        "constraints": ["No excessive description"],
        "last_updated": datetime.now(UTC),
    }
    defaults.update(overrides)
    return PreferenceProfile(**defaults)  # type: ignore[arg-type]


class FakePreferenceProvider:
    """Async fake PreferenceProvider for testing.

    Using a real async method avoids the ``AsyncMock(spec=...)`` pitfall
    where spec'd attributes become plain ``MagicMock`` objects that cannot
    be awaited. The ``calls`` list records invocations for assertions.
    """

    def __init__(
        self,
        profile: PreferenceProfile | None = None,
        *,
        raises: Exception | None = None,
    ) -> None:
        self._profile = profile or _make_profile()
        self._raises = raises
        self.calls: list[tuple[object, object]] = []

    async def get_preferences(self, user_id: object, project_id: object) -> PreferenceProfile:
        self.calls.append((user_id, project_id))
        if self._raises is not None:
            raise self._raises
        return self._profile

    async def reset(self, user_id: object, project_id: object) -> None:
        pass


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Enricher writes preference text into dynamic_inputs."""

    @pytest.mark.asyncio
    async def test_writes_preference_text(self) -> None:
        """Provider returns profile, enricher writes to dynamic_inputs."""
        profile = _make_profile()
        provider = FakePreferenceProvider(profile)
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context(user_id=profile.user_id, project_id=profile.project_id)

        result = await enricher.enrich(ctx)

        assert PREFERENCE_KEY in result.dynamic_inputs
        assert result.dynamic_inputs[PREFERENCE_KEY] == profile.to_prompt_text()

    @pytest.mark.asyncio
    async def test_preserves_existing_dynamic_inputs(self) -> None:
        """Enricher does not overwrite existing dynamic_inputs."""
        profile = _make_profile()
        provider = FakePreferenceProvider(profile)
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context(
            dynamic_inputs={"existing_key": "existing_value"},
            user_id=profile.user_id,
            project_id=profile.project_id,
        )

        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs["existing_key"] == "existing_value"
        assert PREFERENCE_KEY in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_overwrites_previous_preference(self) -> None:
        """If dynamic_inputs already has user_preferences, it is overwritten."""
        profile = _make_profile()
        provider = FakePreferenceProvider(profile)
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context(
            dynamic_inputs={"user_preferences": "old_value"},
            user_id=profile.user_id,
            project_id=profile.project_id,
        )

        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[PREFERENCE_KEY] == profile.to_prompt_text()

    @pytest.mark.asyncio
    async def test_provider_called_with_correct_ids(self) -> None:
        """Provider receives the user_id and project_id from context."""
        profile = _make_profile()
        provider = FakePreferenceProvider(profile)
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        user_id = uuid4()
        project_id = uuid4()
        ctx = _make_context(user_id=user_id, project_id=project_id)

        await enricher.enrich(ctx)

        assert len(provider.calls) == 1
        assert provider.calls[0] == (user_id, project_id)


# ---------------------------------------------------------------------------
# 2. Null provider (no-op)
# ---------------------------------------------------------------------------


class TestNullProvider:
    """Enricher with None provider returns context unchanged."""

    @pytest.mark.asyncio
    async def test_noop_returns_original_context(self) -> None:
        """When provider is None, enricher returns context unchanged."""
        enricher = PreferenceContextEnricherImpl(preference_provider=None)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result is ctx

    @pytest.mark.asyncio
    async def test_noop_does_not_add_to_dynamic_inputs(self) -> None:
        """When provider is None, dynamic_inputs is not modified."""
        enricher = PreferenceContextEnricherImpl(preference_provider=None)
        ctx = _make_context(dynamic_inputs={})

        result = await enricher.enrich(ctx)

        assert PREFERENCE_KEY not in result.dynamic_inputs
        assert result.dynamic_inputs == {}


# ---------------------------------------------------------------------------
# 3. Missing user_id / project_id
# ---------------------------------------------------------------------------


class TestMissingIds:
    """Enricher returns context unchanged when IDs are missing."""

    @pytest.mark.asyncio
    async def test_missing_user_id(self) -> None:
        """When user_id is None, enricher returns context unchanged."""
        provider = FakePreferenceProvider()
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context(user_id=None)

        result = await enricher.enrich(ctx)

        assert result is ctx
        assert len(provider.calls) == 0

    @pytest.mark.asyncio
    async def test_missing_project_id(self) -> None:
        """When project_id is None, enricher returns context unchanged."""
        provider = FakePreferenceProvider()
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context(project_id=None)

        result = await enricher.enrich(ctx)

        assert result is ctx
        assert len(provider.calls) == 0

    @pytest.mark.asyncio
    async def test_both_ids_missing(self) -> None:
        """When both user_id and project_id are None, enricher is no-op."""
        provider = FakePreferenceProvider()
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context(user_id=None, project_id=None)

        result = await enricher.enrich(ctx)

        assert result is ctx
        assert len(provider.calls) == 0


# ---------------------------------------------------------------------------
# 4. Provider exception
# ---------------------------------------------------------------------------


class TestProviderException:
    """Enricher gracefully handles provider exceptions."""

    @pytest.mark.asyncio
    async def test_provider_raises_runtime_error(self) -> None:
        """When provider raises, enricher returns context unchanged."""
        provider = FakePreferenceProvider(raises=RuntimeError("mem0 down"))
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result is ctx
        assert PREFERENCE_KEY not in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_provider_raises_connection_error(self) -> None:
        """When provider raises ConnectionError, enricher returns unchanged."""
        provider = FakePreferenceProvider(raises=ConnectionError("network failure"))
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result is ctx

    @pytest.mark.asyncio
    async def test_provider_raises_value_error(self) -> None:
        """When provider raises ValueError, enricher returns unchanged."""
        provider = FakePreferenceProvider(raises=ValueError("bad data"))
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result is ctx


# ---------------------------------------------------------------------------
# 5. Empty profile
# ---------------------------------------------------------------------------


class TestEmptyProfile:
    """Enricher still writes when profile has no data."""

    @pytest.mark.asyncio
    async def test_empty_profile_writes_empty_string(self) -> None:
        """Profile with event_count=0 yields empty string (downstream decides)."""
        profile = _make_profile(event_count=0, style={}, content={}, constraints=[])
        assert profile.to_prompt_text() == ""

        provider = FakePreferenceProvider(profile)
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context(user_id=profile.user_id, project_id=profile.project_id)

        result = await enricher.enrich(ctx)

        assert PREFERENCE_KEY in result.dynamic_inputs
        assert result.dynamic_inputs[PREFERENCE_KEY] == ""

    @pytest.mark.asyncio
    async def test_profile_with_only_style(self) -> None:
        """Profile with style data but no content/constraints still writes."""
        profile = _make_profile(
            content={},
            constraints=[],
        )
        provider = FakePreferenceProvider(profile)
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context(user_id=profile.user_id, project_id=profile.project_id)

        result = await enricher.enrich(ctx)

        assert PREFERENCE_KEY in result.dynamic_inputs
        assert "Style preferences" in result.dynamic_inputs[PREFERENCE_KEY]


# ---------------------------------------------------------------------------
# 6. Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """PreferenceContextEnricherImpl satisfies PreferenceContextEnricher."""

    def test_has_enrich_method(self) -> None:
        """Enricher has the required async enrich method."""
        enricher = PreferenceContextEnricherImpl(preference_provider=None)
        assert hasattr(enricher, "enrich")
        assert callable(enricher.enrich)

    @pytest.mark.asyncio
    async def test_enrich_signature_matches_protocol(self) -> None:
        """Enricher enrich method accepts and returns correct types."""
        enricher = PreferenceContextEnricherImpl(preference_provider=None)
        ctx = _make_context()
        result = await enricher.enrich(ctx)
        assert isinstance(result, PromptInvocationContext)

    def test_satisfies_protocol_structurally(self) -> None:
        """PreferenceContextEnricherImpl is structurally compatible with Protocol.

        This test verifies the class can be used wherever a
        PreferenceContextEnricher is expected.
        """

        def _accepts_enricher(enricher: PreferenceContextEnricher) -> None:
            pass

        # Should not raise a type error at runtime
        _accepts_enricher(PreferenceContextEnricherImpl(preference_provider=None))


# ---------------------------------------------------------------------------
# 7. Immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    """Original context is never mutated."""

    @pytest.mark.asyncio
    async def test_original_context_not_mutated(self) -> None:
        """Enricher returns a new context, original stays unchanged."""
        profile = _make_profile()
        provider = FakePreferenceProvider(profile)
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context(
            user_id=profile.user_id,
            project_id=profile.project_id,
            dynamic_inputs={},
        )

        original_inputs = dict(ctx.dynamic_inputs)
        result = await enricher.enrich(ctx)

        # Original context is unchanged
        assert ctx.dynamic_inputs == original_inputs
        assert PREFERENCE_KEY not in ctx.dynamic_inputs
        # Result is a new object with the enriched data
        assert result is not ctx
        assert PREFERENCE_KEY in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_result_is_separate_object(self) -> None:
        """Enricher always returns a new PromptInvocationContext instance."""
        profile = _make_profile()
        provider = FakePreferenceProvider(profile)
        enricher = PreferenceContextEnricherImpl(preference_provider=provider)
        ctx = _make_context(
            user_id=profile.user_id,
            project_id=profile.project_id,
        )

        result = await enricher.enrich(ctx)

        # model_copy creates a new instance with different identity
        assert result is not ctx
        # But the feature_id is preserved
        assert result.feature_id == ctx.feature_id
        assert result.intent == ctx.intent
