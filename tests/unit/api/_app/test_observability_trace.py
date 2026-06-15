"""Unit tests for ``narrare._app.observability`` — trace context & enrichment.

Tests:
- ``get_current_trace_context()`` graceful degradation preserved
- ``_mark_unavailable()`` runtime degradation transition
- ``enrich_sse_data()`` unchanged behavior

Split from the original test file to comply with RULE-04 (400-line limit).
State tracking and probe tests are in ``test_observability.py``.
"""

from __future__ import annotations

import builtins
from types import ModuleType
from typing import Any, cast
from unittest.mock import patch

import pytest

import narrare._app.observability as _obs_mod

# ---------------------------------------------------------------------------
# Helpers (duplicated from test_observability.py to keep each file standalone)
# ---------------------------------------------------------------------------


def _reset_state() -> None:
    """Reset module-level cached state between tests."""
    with _obs_mod._state_lock:
        cast("Any", _obs_mod)._otel_available = None
        cast("Any", _obs_mod)._failure_reason = ""
        cast("Any", _obs_mod)._warning_emitted = False
        cast("Any", _obs_mod)._otel_state = None
        cast("Any", _obs_mod)._endpoint_configured = False


def _make_fake_otel_trace(
    *,
    recording: bool = True,
    trace_id: int = 0xFF,
    span_id: int = 0xEE,
) -> ModuleType:
    """Build a fake ``opentelemetry.trace`` module."""
    fake_trace = ModuleType("opentelemetry.trace")

    class FakeSpanContext:
        def __init__(self) -> None:
            self.trace_id = trace_id
            self.span_id = span_id

    class FakeSpan:
        def __init__(self) -> None:
            self._recording = recording

        def is_recording(self) -> bool:
            return self._recording

        def get_span_context(self) -> FakeSpanContext:
            return FakeSpanContext()

    class FakeTracer:
        pass

    cast("Any", fake_trace).get_current_span = lambda: FakeSpan()
    cast("Any", fake_trace).get_tracer = lambda _name: FakeTracer()
    return fake_trace


class _BlockOtelImports:
    """Context manager that blocks ``opentelemetry`` imports."""

    def __enter__(self) -> _BlockOtelImports:
        self._original_import = builtins.__import__

        def _blocking_import(
            name: str,
            *args: Any,
            **kwargs: Any,
        ) -> ModuleType:
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError(f"blocked for testing: {name}")
            return self._original_import(name, *args, **kwargs)

        cast("Any", builtins).__import__ = _blocking_import
        return self

    def __exit__(self, *args: Any) -> None:
        cast("Any", builtins).__import__ = self._original_import


class _RedirectOtelImports:
    """Context manager that redirects ``opentelemetry.trace`` to a fake."""

    def __init__(self, fake_trace: ModuleType) -> None:
        self._fake_trace = fake_trace
        self._stub_parent = ModuleType("opentelemetry")
        cast("Any", self._stub_parent).trace = fake_trace

    def __enter__(self) -> _RedirectOtelImports:
        self._original_import = builtins.__import__
        fake = self._fake_trace
        parent = self._stub_parent

        def _redirecting_import(
            name: str,
            globals: dict[str, Any] | None = None,
            locals: dict[str, Any] | None = None,
            fromlist: tuple[str, ...] | None = None,
            level: int = 0,
        ) -> ModuleType:
            if name == "opentelemetry":
                return parent
            if name == "opentelemetry.trace":
                if fromlist:
                    return fake
                return parent
            if name.startswith("opentelemetry."):
                raise ImportError(f"blocked for testing: {name}")
            return cast(
                "ModuleType",
                self._original_import(
                    name,
                    globals,
                    locals,
                    fromlist,
                    level,
                ),
            )

        cast("Any", builtins).__import__ = _redirecting_import
        return self

    def __exit__(self, *args: Any) -> None:
        cast("Any", builtins).__import__ = self._original_import


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_observability_state() -> Any:  # pyright: ignore[reportUnusedFunction]
    _reset_state()
    yield
    _reset_state()


# ---------------------------------------------------------------------------
# Test: get_current_trace_context (graceful degradation preserved)
# ---------------------------------------------------------------------------


class TestGetCurrentTraceContext:
    """Tests for trace context extraction with state caching."""

    def test_returns_empty_dict_when_unavailable(self) -> None:
        """When OTel is unavailable, returns {} without re-probing."""
        with _BlockOtelImports():
            result1 = _obs_mod.get_current_trace_context()
            result2 = _obs_mod.get_current_trace_context()

        assert result1 == {}
        assert result2 == {}

    def test_returns_trace_context_when_available(self) -> None:
        """When OTel is available and span is recording, returns context."""
        fake_trace = _make_fake_otel_trace(
            recording=True,
            trace_id=0xAABB,
            span_id=0xCCDD,
        )

        with _RedirectOtelImports(fake_trace):
            result = _obs_mod.get_current_trace_context()

        assert "x_trace_id" in result
        assert "x_span_id" in result
        assert result["x_trace_id"] == format(0xAABB, "032x")
        assert result["x_span_id"] == format(0xCCDD, "016x")

    def test_returns_empty_when_span_not_recording(self) -> None:
        """When span exists but is not recording, returns {}."""
        fake_trace = _make_fake_otel_trace(recording=False)

        with _RedirectOtelImports(fake_trace):
            result = _obs_mod.get_current_trace_context()

        assert result == {}

    def test_no_log_spam_on_repeated_calls(self) -> None:
        """Repeated calls after unavailability do not re-log warnings."""
        with (
            _BlockOtelImports(),
            patch.object(_obs_mod.logger, "warning") as mock_warning,
        ):
            for _ in range(10):
                _obs_mod.get_current_trace_context()

        assert mock_warning.call_count == 1


# ---------------------------------------------------------------------------
# Test: _mark_unavailable
# ---------------------------------------------------------------------------


class TestMarkUnavailable:
    """Tests for runtime degradation transition."""

    def test_marks_unavailable_from_available_state(self) -> None:
        """Transitions from available to unavailable emit warning."""
        fake_trace = _make_fake_otel_trace()

        with _RedirectOtelImports(fake_trace):
            _obs_mod._probe_once()

        assert _obs_mod.get_observability_status()["available"] is True

        with patch.object(_obs_mod.logger, "warning") as mock_warning:
            _obs_mod._mark_unavailable("runtime failure")

        status = _obs_mod.get_observability_status()
        assert status["available"] is False
        assert status["failure_reason"] == "runtime failure"
        mock_warning.assert_called_once()
        assert mock_warning.call_args[0][0] == "otel_degraded"

    def test_no_duplicate_warning_when_already_unavailable(self) -> None:
        """Calling _mark_unavailable when already unavailable is a no-op."""
        with _BlockOtelImports():
            _obs_mod._probe_once()

        with patch.object(_obs_mod.logger, "warning") as mock_warning:
            _obs_mod._mark_unavailable("another failure")

        assert mock_warning.call_count == 0


# ---------------------------------------------------------------------------
# Test: enrich_sse_data (preserved behavior)
# ---------------------------------------------------------------------------


class TestEnrichSseData:
    """Tests that enrich_sse_data behavior is preserved."""

    def test_returns_original_when_no_context(self) -> None:
        """Without OTel, returns the original dict unchanged."""
        with _BlockOtelImports():
            data: dict[str, Any] = {"text": "hello", "is_final": False}
            result = _obs_mod.enrich_sse_data(data)

        assert result is data  # Same object

    def test_returns_new_dict_with_context(self) -> None:
        """With OTel context, returns a new enriched dict."""
        fake_trace = _make_fake_otel_trace()

        with _RedirectOtelImports(fake_trace):
            data = {"text": "hello"}
            result = _obs_mod.enrich_sse_data(data)

        assert result is not data
        assert result["text"] == "hello"
        assert "x_trace_id" in result
        assert "x_span_id" in result

    def test_preserves_existing_keys(self) -> None:
        """Existing data keys are not overwritten."""
        fake_trace = _make_fake_otel_trace()

        with _RedirectOtelImports(fake_trace):
            data = {"text": "hello", "is_final": True}
            result = _obs_mod.enrich_sse_data(data)

        assert result["text"] == "hello"
        assert result["is_final"] is True
