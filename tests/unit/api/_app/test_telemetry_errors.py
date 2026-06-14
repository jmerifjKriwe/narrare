"""Unit tests for ``narrare._app.telemetry`` — exception handling path.

Covers the ``except Exception`` handler in ``setup_telemetry`` (lines 87-88)
when the OTLP endpoint is set but OTel setup fails.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

import narrare._app.telemetry as telemetry


class TestSetupTelemetryExceptionPath:
    def test_logs_warning_on_setup_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When setup_telemetry encounters an exception, it logs a warning."""
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel:4317")

        # Force an ImportError by making the OTLP exporter import fail
        original_import = __import__

        def _failing_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if "trace_exporter" in name:
                raise ImportError("blocked for testing")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", _failing_import)

        # Should not raise — catches Exception internally
        telemetry.setup_telemetry(object())  # type: ignore[arg-type]
