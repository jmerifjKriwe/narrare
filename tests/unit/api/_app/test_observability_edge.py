"""Unit tests for ``narrare._app.observability`` — additional edge cases.

Covers lines not exercised by ``test_observability.py`` or
``test_observability_trace.py``:
- ``_NoOpTracer.start_span`` — no-op span creation
- ``get_tracer`` ImportError after successful probe (lines 138-142)
- ``get_current_trace_context`` ImportError after successful probe (lines 170-174)
"""

from __future__ import annotations

import builtins
from types import ModuleType
from typing import Any, cast
from unittest.mock import patch

import pytest

import narrare._app.observability as _obs_mod

# ---------------------------------------------------------------------------
# Helpers (standalone — no cross-file dependency)
# ---------------------------------------------------------------------------


def _reset_state() -> None:
    with _obs_mod._state_lock:
        cast("Any", _obs_mod)._otel_available = None
        cast("Any", _obs_mod)._failure_reason = ""
        cast("Any", _obs_mod)._warning_emitted = False


def _make_fake_otel_trace() -> ModuleType:
    fake_trace = ModuleType("opentelemetry.trace")

    class FakeSpanContext:
        trace_id = 0xFF
        span_id = 0xEE

    class FakeSpan:
        def is_recording(self) -> bool:
            return True

        def get_span_context(self) -> FakeSpanContext:
            return FakeSpanContext()

    class FakeTracer:
        pass

    cast("Any", fake_trace).get_current_span = lambda: FakeSpan()
    cast("Any", fake_trace).get_tracer = lambda _name: FakeTracer()
    return fake_trace


class _BlockOtelImports:
    def __enter__(self) -> _BlockOtelImports:
        self._original_import = builtins.__import__

        def _blocking_import(name: str, *args: Any, **kwargs: Any) -> ModuleType:
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError(f"blocked for testing: {name}")
            return self._original_import(name, *args, **kwargs)

        cast("Any", builtins).__import__ = _blocking_import
        return self

    def __exit__(self, *args: Any) -> None:
        cast("Any", builtins).__import__ = self._original_import


class _RedirectOtelImports:
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
                self._original_import(name, globals, locals, fromlist, level),
            )

        cast("Any", builtins).__import__ = _redirecting_import
        return self

    def __exit__(self, *args: Any) -> None:
        cast("Any", builtins).__import__ = self._original_import


@pytest.fixture(autouse=True)
def _reset() -> Any:  # pyright: ignore[reportUnusedFunction]
    _reset_state()
    yield
    _reset_state()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoOpTracerStartSpan:
    def test_start_span_returns_noop_span(self) -> None:
        """``_NoOpTracer.start_span`` returns a usable no-op span."""
        with _BlockOtelImports():
            tracer = _obs_mod.get_tracer("narrare.test")

        span = tracer.start_span("unit-test")
        assert isinstance(span, _obs_mod._NoOpSpan)
        # Should be usable as context manager and accept attributes
        span.set_attribute("key", "value")


class TestGetTracerImportErrorAfterProbe:
    def test_returns_noop_when_import_fails_after_successful_probe(self) -> None:
        """When probe succeeded but import fails in get_tracer, degrades."""
        fake_trace = _make_fake_otel_trace()

        # Probe succeeds — marks OTel as available
        with _RedirectOtelImports(fake_trace):
            _obs_mod._probe_once()

        assert _obs_mod.get_observability_status()["available"] is True

        # Now import fails during get_tracer
        with _BlockOtelImports(), patch.object(_obs_mod.logger, "warning") as mock_warning:
            tracer = _obs_mod.get_tracer("narrare.test")

        assert isinstance(tracer, _obs_mod._NoOpTracer)
        assert mock_warning.called


class TestGetCurrentTraceContextImportErrorAfterProbe:
    def test_returns_empty_when_import_fails_after_successful_probe(self) -> None:
        """When probe succeeded but import fails in context extraction."""
        fake_trace = _make_fake_otel_trace()

        with _RedirectOtelImports(fake_trace):
            _obs_mod._probe_once()

        assert _obs_mod.get_observability_status()["available"] is True

        with _BlockOtelImports():
            result = _obs_mod.get_current_trace_context()

        assert result == {}
