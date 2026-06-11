"""Tests für NarrareObservability-Capability."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

from narrare_core.agents.capabilities.observability import NarrareObservability


class _FakeRunContext:
    """Minimaler RunContext-Ersatz für Tests."""

    def __init__(self, deps: object = None) -> None:
        self.deps = deps


class TestNarrareObservability:
    """NarrareObservability-Hooks feuern korrekt."""

    async def test_can_be_instantiated(self) -> None:
        """Capability kann erstellt werden."""
        obs = NarrareObservability()
        assert isinstance(obs, NarrareObservability)

    async def test_for_run_returns_fresh_instance(self) -> None:
        """for_run erzeugt frische Instanz."""
        obs = NarrareObservability()
        fresh = await obs.for_run(cast("Any", _FakeRunContext()))
        assert fresh is not obs
        assert isinstance(fresh, NarrareObservability)

    async def test_before_model_request_sets_start_time(self) -> None:
        """before_model_request setzt _start_time."""
        obs = NarrareObservability()
        result = await obs.before_model_request(
            cast("Any", None),
            cast("Any", None),
        )
        assert obs._start_time > 0
        assert result is None  # passes through

    @patch("narrare_core.agents.capabilities.observability.record_success")
    async def test_after_model_request_calls_record_success(self, mock_record: AsyncMock) -> None:
        """after_model_request ruft record_success auf."""
        obs = NarrareObservability()
        obs._start_time = 0.0

        class FakeUsage:
            input_tokens = 10
            output_tokens = 50
            total_tokens = 60

        class FakeCtx:
            usage = FakeUsage()

        await obs.after_model_request(
            cast("Any", FakeCtx()),
            request_context=cast("Any", None),
            response=cast("Any", None),
        )
        mock_record.assert_called_once()

    @patch("narrare_core.agents.capabilities.observability.record_failure")
    async def test_on_model_request_error_calls_record_failure(
        self, mock_record: AsyncMock
    ) -> None:
        """on_model_request_error ruft record_failure auf und propagiert."""
        obs = NarrareObservability()
        obs._start_time = 0.0

        with pytest.raises(ValueError, match="test error"):
            await obs.on_model_request_error(
                cast("Any", None),
                request_context=cast("Any", None),
                error=ValueError("test error"),
            )
        mock_record.assert_called_once()

    # ------------------------------------------------------------------
    # for_run — Deps-Extraktion
    # ------------------------------------------------------------------

    async def test_for_run_extracts_model_config_from_deps(self) -> None:
        """for_run extrahiert provider_name + model_id aus deps.model_config."""
        obs = NarrareObservability()

        class FakeModelConfig:
            provider_name = "test_provider"
            model_id = "test-model-v1"

        class FakeDeps:
            model_config = FakeModelConfig()

        ctx = _FakeRunContext(deps=FakeDeps())
        fresh = await obs.for_run(cast("Any", ctx))

        assert fresh._provider_name == "test_provider"
        assert fresh._model_id == "test-model-v1"

    async def test_for_run_does_not_override_explicit_values(self) -> None:
        """for_run überschreibt keine bereits gesetzten Werte.

        Da NarrareObservability() mit Defaults erzeugt wird (leere Strings),
        werden die Werte aus deps übernommen. Sollte ein Konstruktor-Parameter
        in Zukunft explizite Werte setzen, überschreibt for_run sie nicht.
        """
        obs = NarrareObservability()
        obs._provider_name = "explicit_provider"

        class FakeDepsWithoutConfig:
            pass

        ctx = _FakeRunContext(deps=FakeDepsWithoutConfig())
        fresh = await obs.for_run(cast("Any", ctx))

        # Kein model_config in deps → Werte bleiben unverändert (leer)
        assert fresh._provider_name == ""

    # ------------------------------------------------------------------
    # Cache-Extraktion (ADR-016 Phase 2.4)
    # ------------------------------------------------------------------

    @patch("narrare_core.agents.capabilities.observability.record_cache_usage")
    @patch("narrare_core.agents.capabilities.observability.record_success")
    async def test_after_model_request_extracts_cache_stats(
        self,
        mock_record_success: AsyncMock,
        mock_record_cache: AsyncMock,
    ) -> None:
        """after_model_request extrahiert cache_read/creation aus usage.details."""
        obs = NarrareObservability()
        obs._start_time = 0.0
        obs._intent = "write"
        obs._model_id = "claude-sonnet-4-5-20251020"
        obs._provider_name = "anthropic"

        class FakeUsage:
            input_tokens = 100
            output_tokens = 50
            total_tokens = 150

            def __init__(self) -> None:
                self.details: dict[str, int] = {
                    "cache_read_input_tokens": 500,
                    "cache_creation_input_tokens": 200,
                }

        class FakeCtx:
            usage = FakeUsage()

        await obs.after_model_request(
            cast("Any", FakeCtx()),
            request_context=cast("Any", None),
            response=cast("Any", None),
        )

        # record_cache_usage wurde mit extrahierten Werten aufgerufen
        mock_record_cache.assert_called_once_with(
            intent="write",
            model="claude-sonnet-4-5-20251020",
            provider="anthropic",
            cache_read_tokens=500,
            cache_creation_tokens=200,
        )

        # TokenUsage in record_success enthält Cache-Felder
        call_kwargs = mock_record_success.call_args.kwargs
        token_usage = call_kwargs["usage"]
        assert token_usage.cache_read_tokens == 500
        assert token_usage.cache_creation_tokens == 200
