"""OpenTelemetry setup for Narrare API.

Configures tracing and metrics. Gracefully degrades if OTel is not configured.

Environment variables:
  OTEL_EXPORTER_OTLP_ENDPOINT — OTel Collector endpoint (e.g. "http://localhost:4317")
  OTEL_SERVICE_NAME — Service name (default: "narrare-api")
  OTEL_TRACES_ENABLED — Enable tracing (default: "false" for dev)
  NARRARE_OTEL_INCLUDE_CONTENT — Include prompt/completion content in AI spans
      (default: true outside production, false in production)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog

from narrare._app.observability import record_otel_setup_outcome
from narrare_core.agents.instrumentation import configure_pydantic_ai_instrumentation

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = structlog.get_logger(__name__)


def _env_bool(name: str, *, default: bool) -> bool:
    """Parse a boolean environment variable using common truthy values."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _include_ai_content() -> bool:
    """Return whether Pydantic-AI spans may include prompt/completion content."""
    environment = os.environ.get("ENVIRONMENT", "development").strip().lower()
    default = environment != "production"
    return _env_bool("NARRARE_OTEL_INCLUDE_CONTENT", default=default)


def setup_telemetry(app: FastAPI) -> None:
    """Configure OpenTelemetry for the FastAPI app.

    No-op if OTEL_EXPORTER_OTLP_ENDPOINT is not set.
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("otel_disabled_no_endpoint")
        record_otel_setup_outcome(endpoint_configured=False, succeeded=True)
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import (  # type: ignore[import-untyped]  # reason: opentelemetry-instrumentation-fastapi has no type stubs
            FastAPIInstrumentor,  # type: ignore[reportUnknownVariableType]  # reason: imported from untyped opentelemetry package
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        service_name = os.environ.get("OTEL_SERVICE_NAME", "narrare-api")

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)  # type: ignore[attr-defined]  # reason: FastAPIInstrumentor from untyped opentelemetry package
        include_content = _include_ai_content()
        configure_pydantic_ai_instrumentation(
            include_content=include_content,
            tracer_provider=provider,
        )

        record_otel_setup_outcome(endpoint_configured=True, succeeded=True)
        logger.info(
            "otel_configured",
            endpoint=endpoint,
            service=service_name,
            pydantic_ai_instrumented=True,
            include_content=include_content,
        )
    except Exception as exc:
        logger.warning("otel_setup_failed", exc_info=True)
        record_otel_setup_outcome(
            endpoint_configured=True,
            succeeded=False,
            failure_reason=f"OTLP exporter setup raised: {exc}",
        )
