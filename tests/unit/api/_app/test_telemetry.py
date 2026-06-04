"""Unit tests for API OpenTelemetry bootstrap."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import narrare._app.telemetry as telemetry


class _FakeExporter:
    """Minimal span exporter accepted by the fake span processor."""

    def __init__(self, *, endpoint: str, insecure: bool) -> None:
        self.endpoint = endpoint
        self.insecure = insecure


class _FakeSpanProcessor:
    """Minimal span processor for telemetry bootstrap tests."""

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


def test_setup_telemetry_noops_without_endpoint(monkeypatch: Any) -> None:
    """Without OTLP endpoint, telemetry setup does not instrument AI agents."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    configure = Mock()
    monkeypatch.setattr(telemetry, "configure_pydantic_ai_instrumentation", configure)

    telemetry.setup_telemetry(Mock())

    configure.assert_not_called()


def test_setup_telemetry_instruments_pydantic_ai(monkeypatch: Any) -> None:
    """With OTLP endpoint, bootstrap enables native Pydantic-AI OTel spans."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel:4317")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "narrare-test")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("NARRARE_OTEL_INCLUDE_CONTENT", raising=False)

    configured: dict[str, object] = {}

    def _configure(**kwargs: object) -> None:
        configured.update(kwargs)

    instrumented_apps: list[object] = []

    def _instrument_app(app: object) -> None:
        instrumented_apps.append(app)

    monkeypatch.setattr(telemetry, "configure_pydantic_ai_instrumentation", _configure)

    from opentelemetry.exporter.otlp.proto.grpc import trace_exporter
    from opentelemetry.instrumentation import fastapi
    from opentelemetry.sdk.trace import export

    monkeypatch.setattr(trace_exporter, "OTLPSpanExporter", _FakeExporter)
    monkeypatch.setattr(export, "BatchSpanProcessor", _FakeSpanProcessor)
    monkeypatch.setattr(fastapi.FastAPIInstrumentor, "instrument_app", _instrument_app)

    app = Mock()
    telemetry.setup_telemetry(app)

    assert instrumented_apps == [app]
    assert configured["include_content"] is True
    assert configured["tracer_provider"] is not None


def test_include_ai_content_defaults_to_false_in_production(monkeypatch: Any) -> None:
    """Production default avoids prompt/completion content exfiltration."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("NARRARE_OTEL_INCLUDE_CONTENT", raising=False)

    assert telemetry._include_ai_content() is False


def test_include_ai_content_can_be_overridden(monkeypatch: Any) -> None:
    """Explicit env setting controls AI span content capture."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("NARRARE_OTEL_INCLUDE_CONTENT", "true")

    assert telemetry._include_ai_content() is True
