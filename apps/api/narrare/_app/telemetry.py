"""OpenTelemetry setup for Narrare API.

Configures tracing and metrics. Gracefully degrades if OTel is not configured.

Environment variables:
  OTEL_EXPORTER_OTLP_ENDPOINT — OTel Collector endpoint (e.g. "http://localhost:4317")
  OTEL_SERVICE_NAME — Service name (default: "narrare-api")
  OTEL_TRACES_ENABLED — Enable tracing (default: "false" for dev)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = structlog.get_logger(__name__)


def setup_telemetry(app: FastAPI) -> None:
    """Configure OpenTelemetry for the FastAPI app.

    No-op if OTEL_EXPORTER_OTLP_ENDPOINT is not set.
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("otel_disabled_no_endpoint")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import (  # type: ignore[import-untyped,reportMissingTypeStubs]
            FastAPIInstrumentor,  # type: ignore[reportUnknownVariableType]
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

        FastAPIInstrumentor.instrument_app(app)  # type: ignore[attr-defined]

        logger.info("otel_configured", endpoint=endpoint, service=service_name)
    except Exception:
        logger.warning("otel_setup_failed", exc_info=True)
