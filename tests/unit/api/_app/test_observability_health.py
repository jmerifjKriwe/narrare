"""Unit tests for OTel health-severity state tracking (AUFG-05-14).

Tests T1-T5 from the OTel Health-Severity Policy section 7.5:

- T1: No OTEL_EXPORTER_OTLP_ENDPOINT -> state=not_configured, severity=healthy
- T2: Endpoint set, exporter import fails -> state=configured_failed,
  severity=degraded, failure_reason non-empty, setup did not raise
- T3: Endpoint set, successful config -> state=configured_ok, severity=healthy
- T4: Production + no NARRARE_OTEL_INCLUDE_CONTENT -> _include_ai_content() False
- T5: Package unavailable -> state=package_unavailable, severity=degraded
"""

from __future__ import annotations

import builtins
from types import ModuleType
from typing import Any, cast

import pytest

import narrare._app.observability as _obs_mod
import narrare._app.telemetry as _tel_mod

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_state() -> None:
    """Reset module-level cached state between tests."""
    with _obs_mod._state_lock:
        cast("Any", _obs_mod)._otel_available = None
        cast("Any", _obs_mod)._failure_reason = ""
        cast("Any", _obs_mod)._warning_emitted = False
        cast("Any", _obs_mod)._otel_state = None
        cast("Any", _obs_mod)._endpoint_configured = False


def _make_fake_otel_trace() -> ModuleType:
    """Build a fake ``opentelemetry.trace`` module."""
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
    """Context manager that blocks ``opentelemetry`` imports."""

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
                self._original_import(name, globals, locals, fromlist, level),
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
# T1: No endpoint → not_configured → healthy
# ---------------------------------------------------------------------------


class TestT1NoEndpoint:
    """When no OTLP endpoint is set, state is ``not_configured``."""

    def test_t1_state_and_severity(self) -> None:
        """After recording no-endpoint outcome, state/severity are correct."""
        _obs_mod.record_otel_setup_outcome(
            endpoint_configured=False,
            succeeded=True,
        )

        status = _obs_mod.get_observability_status()
        assert status["state"] == "not_configured"
        assert status["severity"] == "healthy"
        assert status["available"] is True
        assert status["endpoint_configured"] is False

    def test_t1_no_endpoint_via_telemetry(self) -> None:
        """``setup_telemetry`` without endpoint produces not_configured."""
        fake_trace = _make_fake_otel_trace()
        with _RedirectOtelImports(fake_trace):
            _tel_mod.setup_telemetry(object())  # type: ignore[arg-type]

        status = _obs_mod.get_observability_status()
        assert status["state"] == "not_configured"
        assert status["severity"] == "healthy"
        assert status["endpoint_configured"] is False


# ---------------------------------------------------------------------------
# T2: Endpoint set, exporter import fails → configured_failed → degraded
# ---------------------------------------------------------------------------


class TestT2ConfiguredFailed:
    """When endpoint is set but exporter setup fails."""

    def test_t2_record_outcome_directly(self) -> None:
        """``record_otel_setup_outcome`` with failed setup produces correct state."""
        _obs_mod.record_otel_setup_outcome(
            endpoint_configured=True,
            succeeded=False,
            failure_reason="OTLP exporter setup raised: ImportError: blocked",
        )

        status = _obs_mod.get_observability_status()
        assert status["state"] == "configured_failed"
        assert status["severity"] == "degraded"
        assert status["available"] is False
        assert status["endpoint_configured"] is True
        assert status["failure_reason"] != ""

    def test_t2_via_telemetry_exception_path(self, monkeypatch: Any) -> None:
        """``setup_telemetry`` with exporter import failure records degraded state."""
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel:4317")

        # Force an ImportError when the exporter would be imported
        original_import = __import__

        def _failing_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if "trace_exporter" in name:
                raise ImportError("blocked for testing")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", _failing_import)

        # Should not raise — setup_telemetry catches the exception
        _tel_mod.setup_telemetry(object())  # type: ignore[arg-type]

        status = _obs_mod.get_observability_status()
        assert status["state"] == "configured_failed"
        assert status["severity"] == "degraded"
        assert status["available"] is False
        assert status["endpoint_configured"] is True
        assert status["failure_reason"] != ""


# ---------------------------------------------------------------------------
# T3: Endpoint set, successful configuration → configured_ok → healthy
# ---------------------------------------------------------------------------


class TestT3ConfiguredOk:
    """When endpoint is set and exporter setup succeeds."""

    def test_t3_record_outcome_directly(self) -> None:
        """``record_otel_setup_outcome`` with successful setup produces correct state."""
        _obs_mod.record_otel_setup_outcome(
            endpoint_configured=True,
            succeeded=True,
        )

        status = _obs_mod.get_observability_status()
        assert status["state"] == "configured_ok"
        assert status["severity"] == "healthy"
        assert status["available"] is True
        assert status["endpoint_configured"] is True

    def test_t3_via_telemetry(self, monkeypatch: Any) -> None:
        """``setup_telemetry`` with successful config produces configured_ok."""
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "narrare-test")

        # Use fakes for OTel internals
        from opentelemetry.exporter.otlp.proto.grpc import trace_exporter
        from opentelemetry.instrumentation import fastapi
        from opentelemetry.sdk.trace import export

        class _FakeExporter:
            def __init__(self, *, endpoint: str, insecure: bool) -> None:
                self.endpoint = endpoint
                self.insecure = insecure

        class _FakeSpanProcessor:
            def __init__(self, exporter: _FakeExporter) -> None:
                self.exporter = exporter

            def on_start(self, span: object, parent_context: object | None = None) -> None:
                return None

            def on_end(self, span: object) -> None:
                return None

            def shutdown(self) -> None:
                return None

            def force_flush(self, timeout_millis: int = 30000) -> bool:
                return True

        monkeypatch.setattr(trace_exporter, "OTLPSpanExporter", _FakeExporter)
        monkeypatch.setattr(export, "BatchSpanProcessor", _FakeSpanProcessor)

        def _noop_instrument_app(app: object) -> None:
            pass

        monkeypatch.setattr(fastapi.FastAPIInstrumentor, "instrument_app", _noop_instrument_app)

        def _noop_configure_ai(**kwargs: object) -> None:
            pass

        monkeypatch.setattr(_tel_mod, "configure_pydantic_ai_instrumentation", _noop_configure_ai)

        _tel_mod.setup_telemetry(object())  # type: ignore[arg-type]

        status = _obs_mod.get_observability_status()
        assert status["state"] == "configured_ok"
        assert status["severity"] == "healthy"
        assert status["endpoint_configured"] is True


# ---------------------------------------------------------------------------
# T4: Production → NARRARE_OTEL_INCLUDE_CONTENT defaults false
# ---------------------------------------------------------------------------


class TestT4ProductionContentDefault:
    """Production-safe default for AI span content capture."""

    def test_t4_production_default_is_false(self, monkeypatch: Any) -> None:
        """In production, content capture defaults to False (privacy invariant)."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("NARRARE_OTEL_INCLUDE_CONTENT", raising=False)

        assert _tel_mod._include_ai_content() is False


# ---------------------------------------------------------------------------
# T5: Package unavailable → package_unavailable → degraded
# ---------------------------------------------------------------------------


class TestT5PackageUnavailable:
    """When the OTel package is not importable."""

    def test_t5_state_and_severity(self) -> None:
        """Blocked OTel imports produce package_unavailable state."""
        with _BlockOtelImports():
            _obs_mod._probe_once()

        status = _obs_mod.get_observability_status()
        assert status["state"] == "package_unavailable"
        assert status["severity"] == "degraded"
        assert status["available"] is False

    def test_t5_package_unavailable_takes_priority(self) -> None:
        """``package_unavailable`` is not overwritten by later outcome recording."""
        with _BlockOtelImports():
            _obs_mod._probe_once()

        # Even if we record a successful outcome, package_unavailable should persist
        _obs_mod.record_otel_setup_outcome(
            endpoint_configured=True,
            succeeded=True,
        )

        status = _obs_mod.get_observability_status()
        assert status["state"] == "package_unavailable"
        assert status["severity"] == "degraded"

    def test_t5_via_mark_unavailable(self) -> None:
        """``_mark_unavailable`` also transitions to package_unavailable."""
        fake_trace = _make_fake_otel_trace()
        with _RedirectOtelImports(fake_trace):
            _obs_mod._probe_once()

        # Now simulate runtime degradation
        with _BlockOtelImports():
            # get_tracer triggers _mark_unavailable when import fails after probe
            _obs_mod.get_tracer("narrare.test")

        status = _obs_mod.get_observability_status()
        assert status["state"] == "package_unavailable"
        assert status["severity"] == "degraded"


# ---------------------------------------------------------------------------
# Additional: get_observability_status return shape
# ---------------------------------------------------------------------------


class TestReturnShape:
    """Verify the enhanced return shape contains all required keys."""

    def test_has_all_new_keys(self) -> None:
        """Status dict contains state, severity, endpoint_configured in addition to old keys."""
        status = _obs_mod.get_observability_status()
        assert "state" in status
        assert "severity" in status
        assert "endpoint_configured" in status
        assert "available" in status
        assert "failure_reason" in status
        assert "warning_emitted" in status

    def test_severity_is_valid(self) -> None:
        """Severity is always one of the allowed values."""
        # Healthy path
        _obs_mod.record_otel_setup_outcome(endpoint_configured=False, succeeded=True)
        assert _obs_mod.get_observability_status()["severity"] in (
            "healthy",
            "degraded",
            "critical",
        )

    def test_state_is_valid(self) -> None:
        """State is always one of the allowed values."""
        valid_states = {
            "not_configured",
            "configured_ok",
            "configured_failed",
            "package_unavailable",
        }
        _obs_mod.record_otel_setup_outcome(endpoint_configured=False, succeeded=True)
        assert _obs_mod.get_observability_status()["state"] in valid_states
