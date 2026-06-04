"""Global Pydantic-AI OpenTelemetry instrumentation controls.

This module stays in ``core/agents`` because it imports Pydantic-AI's
``Agent`` API. Runtime activation is controlled by the API bootstrap layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent, InstrumentationSettings

if TYPE_CHECKING:
    from opentelemetry.metrics import MeterProvider
    from opentelemetry.trace import TracerProvider


def configure_pydantic_ai_instrumentation(
    *,
    include_content: bool,
    tracer_provider: TracerProvider | None = None,
    meter_provider: MeterProvider | None = None,
) -> None:
    """Enable global native Pydantic-AI OpenTelemetry instrumentation.

    Args:
        include_content: Whether prompt/completion content may be attached to
            spans. Production should pass ``False`` to avoid content exfiltration.
        tracer_provider: Optional OpenTelemetry tracer provider configured by
            the runtime bootstrap.
        meter_provider: Optional OpenTelemetry meter provider configured by
            the runtime bootstrap.
    """
    settings = InstrumentationSettings(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        include_content=include_content,
        include_binary_content=False,
    )
    Agent.instrument_all(settings)
