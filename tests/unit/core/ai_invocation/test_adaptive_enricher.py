"""Tests for AdaptiveContextEnricher — the single canonical writer of
all four adaptive prompt variables.

Covers: success path, no provider, missing IDs, provider failure,
disabled settings, no signal, all 4 variables written, immutability.

See: ADR-069 Decision 1, ADR-038 D7 (graceful degradation),
CONSTRAINTS.md RULE-03/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

import pytest

from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveSettings,
    AdaptiveWeights,
)
from narrare_core.ai_invocation.enrichers._keys import (
    AVOIDANCE_PATTERNS_KEY,
    CHARACTER_VOICE_PROFILES_KEY,
    STYLE_CONSTRAINTS_KEY,
    USER_PREFERENCES_KEY,
)
from narrare_core.ai_invocation.enrichers.adaptive import AdaptiveContextEnricher
from narrare_core.ai_invocation.models import PromptInvocationContext
from narrare_core.llm.intents import LLMIntent


class FakeAdaptiveProvider:
    """Async fake AdaptiveContextProvider with programmable results.

    Mirrors the FakePreferenceProvider pattern — real async methods
    avoid the AsyncMock(spec=...) pitfall. Records calls for assertions.
    """

    def __init__(
        self,
        *,
        context: AdaptiveContext | None = None,
        settings: AdaptiveSettings | None = None,
        context_raises: Exception | None = None,
        settings_raises: Exception | None = None,
    ) -> None:
        self._context = context
        self._settings = settings
        self._context_raises = context_raises
        self._settings_raises = settings_raises
        self.context_calls: list[tuple[object, object]] = []
        self.settings_calls: list[tuple[object, object]] = []

    async def get_context(self, user_id: object, project_id: object) -> AdaptiveContext:
        self.context_calls.append((user_id, project_id))
        if self._context_raises is not None:
            raise self._context_raises
        return self._context or AdaptiveContext(
            user_id=cast("UUID", user_id),
            project_id=cast("UUID", project_id),
        )

    async def get_settings(self, user_id: object, project_id: object) -> AdaptiveSettings:
        self.settings_calls.append((user_id, project_id))
        if self._settings_raises is not None:
            raise self._settings_raises
        return self._settings or AdaptiveSettings()


def _make_context(**overrides: object) -> PromptInvocationContext:
    defaults: dict[str, object] = {
        "feature_id": "test/feature",
        "intent": LLMIntent.WRITE,
        "user_id": uuid4(),
        "project_id": uuid4(),
    }
    defaults.update(overrides)
    return PromptInvocationContext(**defaults)  # type: ignore[arg-type]


def _full_adaptive_context(user_id: object, project_id: object) -> AdaptiveContext:
    return AdaptiveContext(
        user_id=cast("UUID", user_id),
        project_id=cast("UUID", project_id),
        preference_text="prefers dark prose",
        voice_profiles_text="**Alice**: terse",
        style_constraints_text="- Short sentences",
        avoidance_patterns_text="- No passive voice",
        weights=AdaptiveWeights(),
        source_summary="3 voices, 12 preference events",
    )


class TestAdaptiveEnricherSuccess:
    """Happy path: provider returns full context; all 4 variables written."""

    @pytest.mark.asyncio
    async def test_all_four_variables_written(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=_full_adaptive_context(user_id, project_id),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)

        ctx = _make_context(user_id=user_id, project_id=project_id)
        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[USER_PREFERENCES_KEY] == "prefers dark prose"
        assert result.dynamic_inputs[STYLE_CONSTRAINTS_KEY] == "- Short sentences"
        assert result.dynamic_inputs[AVOIDANCE_PATTERNS_KEY] == "- No passive voice"
        assert result.dynamic_inputs[CHARACTER_VOICE_PROFILES_KEY] == "**Alice**: terse"

    @pytest.mark.asyncio
    async def test_provider_called_once_with_context_ids(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=_full_adaptive_context(user_id, project_id),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)

        await enricher.enrich(_make_context(user_id=user_id, project_id=project_id))

        assert len(provider.context_calls) == 1
        assert provider.context_calls[0] == (user_id, project_id)
        assert len(provider.settings_calls) == 1


class TestAdaptiveEnricherNoProvider:
    """No provider wired — graceful no-op (ADR-038 D7)."""

    @pytest.mark.asyncio
    async def test_none_provider_returns_context_unchanged(self) -> None:
        enricher = AdaptiveContextEnricher(adaptive_provider=None)
        ctx = _make_context()
        result = await enricher.enrich(ctx)
        assert result is ctx  # unchanged
        assert result.dynamic_inputs == {}


class TestAdaptiveEnricherMissingIds:
    """user_id or project_id missing — graceful no-op with warning."""

    @pytest.mark.asyncio
    async def test_missing_user_id_returns_unchanged(self) -> None:
        provider = FakeAdaptiveProvider()
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=None, project_id=uuid4())
        result = await enricher.enrich(ctx)
        assert result is ctx
        assert provider.context_calls == []

    @pytest.mark.asyncio
    async def test_missing_project_id_returns_unchanged(self) -> None:
        provider = FakeAdaptiveProvider()
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=uuid4(), project_id=None)
        result = await enricher.enrich(ctx)
        assert result is ctx
        assert provider.context_calls == []


class TestAdaptiveEnricherProviderFailure:
    """Provider raises — graceful no-op with warning (RULE-11)."""

    @pytest.mark.asyncio
    async def test_context_provider_raises_returns_unchanged(self) -> None:
        provider = FakeAdaptiveProvider(
            context_raises=RuntimeError("mem0 down"),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context()
        result = await enricher.enrich(ctx)
        assert result is ctx
        assert result.dynamic_inputs == {}

    @pytest.mark.asyncio
    async def test_settings_provider_raises_returns_unchanged(self) -> None:
        """If settings fail to load, the enricher skips entirely —
        safer than running with default-enabled when user disabled."""
        provider = FakeAdaptiveProvider(
            context=_full_adaptive_context(uuid4(), uuid4()),
            settings_raises=RuntimeError("settings repo down"),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context()
        result = await enricher.enrich(ctx)
        assert result is ctx
        assert result.dynamic_inputs == {}


class TestAdaptiveEnricherDisabled:
    """AdaptiveSettings.enabled=False — graceful no-op."""

    @pytest.mark.asyncio
    async def test_disabled_settings_skips_injection(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=_full_adaptive_context(user_id, project_id),
            settings=AdaptiveSettings(enabled=False),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=user_id, project_id=project_id)
        result = await enricher.enrich(ctx)
        assert result is ctx
        assert result.dynamic_inputs == {}


class TestAdaptiveEnricherNoSignal:
    """AdaptiveContext.has_any_signal=False — write empty strings.

    Even though no signal is present, the enricher writes the four keys
    with empty values so the variable engine resolves them (RULE-11
    graceful degradation — empty strings, not KeyError).
    """

    @pytest.mark.asyncio
    async def test_empty_context_writes_empty_strings(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=AdaptiveContext(user_id=user_id, project_id=project_id),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=user_id, project_id=project_id)
        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[USER_PREFERENCES_KEY] == ""
        assert result.dynamic_inputs[STYLE_CONSTRAINTS_KEY] == ""
        assert result.dynamic_inputs[AVOIDANCE_PATTERNS_KEY] == ""
        assert result.dynamic_inputs[CHARACTER_VOICE_PROFILES_KEY] == ""


class TestAdaptiveEnricherPartialSignal:
    """Only some signals present — only those keys get non-empty values."""

    @pytest.mark.asyncio
    async def test_only_preference_present(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=AdaptiveContext(
                user_id=user_id,
                project_id=project_id,
                preference_text="prefers dark prose",
            ),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=user_id, project_id=project_id)
        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[USER_PREFERENCES_KEY] == "prefers dark prose"
        assert result.dynamic_inputs[STYLE_CONSTRAINTS_KEY] == ""
        assert result.dynamic_inputs[AVOIDANCE_PATTERNS_KEY] == ""
        assert result.dynamic_inputs[CHARACTER_VOICE_PROFILES_KEY] == ""


class TestAdaptiveEnricherImmutability:
    """The original context is NOT mutated (RULE-03 immutable value flow)."""

    @pytest.mark.asyncio
    async def test_returns_new_instance(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=_full_adaptive_context(user_id, project_id),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=user_id, project_id=project_id)
        original_dynamic_inputs = dict(ctx.dynamic_inputs)
        result = await enricher.enrich(ctx)

        assert result is not ctx
        # Original unchanged:
        assert ctx.dynamic_inputs == original_dynamic_inputs

    @pytest.mark.asyncio
    async def test_preserves_existing_dynamic_inputs(self) -> None:
        """Existing dynamic_inputs (e.g., from other enrichers) survive."""
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=_full_adaptive_context(user_id, project_id),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=user_id, project_id=project_id)
        ctx = ctx.model_copy(update={"dynamic_inputs": {"existing_key": "kept"}})
        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs["existing_key"] == "kept"
        assert USER_PREFERENCES_KEY in result.dynamic_inputs


class TestAdaptiveEnricherProtocolConformance:
    """The enricher satisfies the ContextEnricher Protocol."""

    @pytest.mark.asyncio
    async def test_enrich_method_signature(self) -> None:
        enricher = AdaptiveContextEnricher(adaptive_provider=None)
        ctx = _make_context()
        result = await enricher.enrich(ctx)
        assert isinstance(result, PromptInvocationContext)


class TestPreferenceContextEnricherImplRemoved:
    """After ADR-069 Phase 2 Task 10, the legacy enricher class is deleted.

    The Protocols in ``contracts.py`` stay (ContextEnricher base +
    PreferenceContextEnricher specialised marker — still useful for typed
    DI). Only the concrete ``PreferenceContextEnricherImpl`` is removed;
    ``AdaptiveContextEnricher`` is the single canonical writer.
    """

    def test_legacy_impl_import_fails(self) -> None:
        """Importing PreferenceContextEnricherImpl MUST fail after deletion."""
        with pytest.raises(ImportError):
            from narrare_core.ai_invocation.enrichers.preferences import (  # noqa: F401
                PreferenceContextEnricherImpl,
            )

    def test_legacy_impl_not_reexported_from_package(self) -> None:
        """The package __init__ MUST NOT re-export PreferenceContextEnricherImpl."""
        import narrare_core.ai_invocation.enrichers as enrichers_pkg

        assert not hasattr(enrichers_pkg, "PreferenceContextEnricherImpl"), (
            "enrichers.__init__ must not re-export PreferenceContextEnricherImpl "
            "after ADR-069 Phase 2 Task 10."
        )

    def test_preference_context_enricher_protocol_stays(self) -> None:
        """The PreferenceContextEnricher Protocol in contracts.py stays."""
        from narrare_core.ai_invocation.contracts import PreferenceContextEnricher

        assert PreferenceContextEnricher is not None

    def test_context_enricher_protocol_stays(self) -> None:
        """The base ContextEnricher Protocol stays."""
        from narrare_core.ai_invocation.contracts import ContextEnricher

        assert ContextEnricher is not None

    def test_adaptive_enricher_remains_importable_from_package(self) -> None:
        """The new enricher remains the only adaptive enricher."""
        from narrare_core.ai_invocation.enrichers import AdaptiveContextEnricher

        assert AdaptiveContextEnricher is not None
