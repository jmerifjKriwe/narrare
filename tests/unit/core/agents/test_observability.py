"""Tests für NarrareObservability-Capability."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from narrare_core.agents.capabilities.observability import NarrareObservability


class TestNarrareObservability:
    """NarrareObservability-Hooks feuern korrekt."""

    async def test_can_be_instantiated(self) -> None:
        """Capability kann erstellt werden."""
        obs = NarrareObservability()
        assert isinstance(obs, NarrareObservability)

    async def test_for_run_returns_fresh_instance(self) -> None:
        """for_run erzeugt frische Instanz."""
        obs = NarrareObservability()
        fresh = await obs.for_run(None)  # type: ignore[arg-type]
        assert fresh is not obs
        assert isinstance(fresh, NarrareObservability)

    async def test_before_model_request_sets_start_time(self) -> None:
        """before_model_request setzt _start_time."""
        obs = NarrareObservability()
        result = await obs.before_model_request(
            None,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
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
            FakeCtx(),  # type: ignore[arg-type]
            request_context=None,  # type: ignore[arg-type]
            response=None,  # type: ignore[arg-type]
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
                None,  # type: ignore[arg-type]
                request_context=None,  # type: ignore[arg-type]
                error=ValueError("test error"),
            )
        mock_record.assert_called_once()
