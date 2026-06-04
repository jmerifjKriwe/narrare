"""Unit tests for ``narrare._app.observability`` — state tracking.

Tests the OTel unavailable/degraded state tracking:
- Module-level cached state (available, failure_reason, warning_emitted)
- One-shot structured warning on first failure
- ``get_observability_status()`` returns queryable state

Split from the original test file to comply with RULE-04 (400-line limit).
SSE enrichment and trace context tests are in ``test_observability_trace.py``.

Strategy:
    Since ``opentelemetry`` is installed in the test environment, we
    cannot simply remove it from ``sys.modules``.  Instead, we:

    1. Reset module-level state via ``_reset_state()`` between tests.
    2. Use ``builtins.__import__`` patching to control whether
       ``opentelemetry`` raises ``ImportError`` on demand.
    3. Use fake ``opentelemetry.trace`` modules injected via
       ``sys.modules`` for "available" tests.
"""

from __future__ import annotations

import builtins
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest

import narrare._app.observability as _obs_mod

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_state() -> None:
    """Reset module-level cached state between tests."""
    with _obs_mod._state_lock:
        _obs_mod._otel_available = None  # type: ignore[attr-defined]
        _obs_mod._failure_reason = ""  # type: ignore[attr-defined]
        _obs_mod._warning_emitted = False  # type: ignore[attr-defined]


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

    fake_trace.get_current_span = lambda: FakeSpan()  # type: ignore[attr-defined]
    fake_trace.get_tracer = lambda _name: FakeTracer()  # type: ignore[attr-defined]
    return fake_trace


def _make_broken_otel_trace() -> ModuleType:
    """Build a fake ``opentelemetry.trace`` whose ``get_tracer`` raises."""
    fake_trace = ModuleType("opentelemetry.trace")

    def _broken_tracer(name: str) -> None:
        raise RuntimeError("broken")

    fake_trace.get_current_span = lambda: None  # type: ignore[attr-defined]
    fake_trace.get_tracer = _broken_tracer  # type: ignore[attr-defined]
    return fake_trace


class _BlockOtelImports:
    """Context manager that blocks ``opentelemetry`` imports.

    Patches ``builtins.__import__`` so any import of a module starting
    with ``opentelemetry`` raises ``ImportError``.  This works even when
    the package is physically installed.
    """

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

        builtins.__import__ = _blocking_import  # type: ignore[assignment]
        return self

    def __exit__(self, *args: Any) -> None:
        builtins.__import__ = self._original_import  # type: ignore[assignment]


class _RedirectOtelImports:
    """Context manager that redirects ``opentelemetry.trace`` to a fake.

    Patches ``builtins.__import__`` to return the provided ``fake_trace``
    module when ``opentelemetry.trace`` is imported.  Also returns a stub
    ``opentelemetry`` parent module so ``import opentelemetry.trace`` works.
    All other ``opentelemetry.*`` sub-modules raise ``ImportError``.
    """

    def __init__(self, fake_trace: ModuleType) -> None:
        self._fake_trace = fake_trace
        self._stub_parent = ModuleType("opentelemetry")
        self._stub_parent.trace = fake_trace  # type: ignore[attr-defined]

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
            return self._original_import(  # type: ignore[no-any-return]
                name,
                globals,
                locals,
                fromlist,
                level,
            )

        builtins.__import__ = _redirecting_import  # type: ignore[assignment]
        return self

    def __exit__(self, *args: Any) -> None:
        builtins.__import__ = self._original_import  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_observability_state() -> Any:  # pyright: ignore[reportUnusedFunction]
    _reset_state()
    yield
    _reset_state()


# ---------------------------------------------------------------------------
# Test: _probe_once
# ---------------------------------------------------------------------------


class TestProbeOnce:
    """Tests for the module-level OTel probe."""

    def test_probe_marks_available_when_otel_importable(self) -> None:
        """When opentelemetry.trace imports successfully, available=True."""
        fake_trace = _make_fake_otel_trace()

        with _RedirectOtelImports(fake_trace):
            _obs_mod._probe_once()

        status = _obs_mod.get_observability_status()
        assert status["available"] is True
        assert status["failure_reason"] == ""

    def test_probe_marks_unavailable_on_import_error(self) -> None:
        """When opentelemetry cannot import, available=False."""
        with _BlockOtelImports():
            _obs_mod._probe_once()

        status = _obs_mod.get_observability_status()
        assert status["available"] is False
        assert "ImportError" in status["failure_reason"]

    def test_probe_only_runs_once(self) -> None:
        """Subsequent calls to _probe_once are a no-op."""
        fake_trace = _make_fake_otel_trace()

        with _RedirectOtelImports(fake_trace):
            _obs_mod._probe_once()
            _obs_mod._probe_once()

        status = _obs_mod.get_observability_status()
        assert status["available"] is True
        assert status["failure_reason"] == ""
        assert status["warning_emitted"] is False

    def test_status_triggers_probe_if_not_yet_probed(self) -> None:
        """Calling get_observability_status triggers probe automatically."""
        fake_trace = _make_fake_otel_trace()

        with _RedirectOtelImports(fake_trace):
            status = _obs_mod.get_observability_status()

        assert status["available"] is True

    def test_probe_captures_unexpected_exception(self) -> None:
        """Non-ImportError exceptions are captured and stored."""
        fake_trace = _make_broken_otel_trace()

        with _RedirectOtelImports(fake_trace):
            _obs_mod._probe_once()

        status = _obs_mod.get_observability_status()
        assert status["available"] is False
        assert "RuntimeError" in status["failure_reason"]


# ---------------------------------------------------------------------------
# Test: one-shot warning
# ---------------------------------------------------------------------------


class TestOneShotWarning:
    """Tests for the one-shot structured warning on OTel unavailability."""

    def test_warning_emitted_once_on_import_error(self) -> None:
        """Exactly one warning is emitted when OTel is unavailable."""
        with (
            _BlockOtelImports(),
            patch.object(_obs_mod.logger, "warning") as mock_warning,
        ):
            _obs_mod._probe_once()
            _obs_mod._probe_once()

        assert mock_warning.call_count == 1
        call_args = mock_warning.call_args
        assert call_args[0][0] == "otel_unavailable"

    def test_warning_not_emitted_when_available(self) -> None:
        """No warning when OTel imports successfully."""
        fake_trace = _make_fake_otel_trace()

        with (
            _RedirectOtelImports(fake_trace),
            patch.object(_obs_mod.logger, "warning") as mock_warning,
        ):
            _obs_mod._probe_once()

        mock_warning.assert_not_called()


# ---------------------------------------------------------------------------
# Test: get_observability_status
# ---------------------------------------------------------------------------


class TestGetObservabilityStatus:
    """Tests for the status query function."""

    def test_returns_dict_with_required_keys(self) -> None:
        """Status dict contains available, failure_reason, warning_emitted."""
        status = _obs_mod.get_observability_status()
        assert "available" in status
        assert "failure_reason" in status
        assert "warning_emitted" in status

    def test_status_reflects_unavailable_state(self) -> None:
        """When OTel is missing, status shows unavailable with reason."""
        with _BlockOtelImports():
            _obs_mod._probe_once()

        status = _obs_mod.get_observability_status()
        assert status["available"] is False
        assert status["failure_reason"] != ""
        assert status["warning_emitted"] is True

    def test_status_reflects_available_state(self) -> None:
        """When OTel is present, status shows available."""
        fake_trace = _make_fake_otel_trace()

        with _RedirectOtelImports(fake_trace):
            _obs_mod._probe_once()

        status = _obs_mod.get_observability_status()
        assert status["available"] is True


# ---------------------------------------------------------------------------
# Test: get_tracer
# ---------------------------------------------------------------------------


class TestGetTracer:
    """Tests for centralized tracer lookup."""

    def test_returns_otel_tracer_when_available(self) -> None:
        """When OTel is available, get_tracer delegates to trace.get_tracer."""
        fake_trace = _make_fake_otel_trace()

        with _RedirectOtelImports(fake_trace):
            tracer = _obs_mod.get_tracer("narrare.test")

        assert tracer.__class__.__name__ == "FakeTracer"

    def test_returns_noop_tracer_when_unavailable(self) -> None:
        """When OTel is unavailable, get_tracer returns a safe no-op tracer."""
        with _BlockOtelImports():
            tracer = _obs_mod.get_tracer("narrare.test")

        with tracer.start_as_current_span("unit-test") as span:
            span.set_attribute("key", "value")

        status = _obs_mod.get_observability_status()
        assert status["available"] is False
