"""Regression: GHSA-4x9p-g9wm-8q7f — no content in spans when include_content=False.

pydantic-ai < 2.44 leaked exceptions, error statuses, instructions and
output templates into OpenTelemetry spans even with
``include_content=False``. Narrare defaults content OFF in production
(``NARRARE_OTEL_INCLUDE_CONTENT``, apps/api/narrare/_app/telemetry.py),
applied via ``configure_pydantic_ai_instrumentation`` in
packages/core/narrare_core/agents/instrumentation.py.

The test runs a real agent (TestModel) under a private in-memory tracer
provider and asserts:

1. include_content=False -> no prompt / instruction / output content in
   any span attribute, event, or error-status description (the security
   property).
2. include_content=True  -> content IS captured (negative control: the
   test can detect content, so absence in (1) is meaningful).
3. Non-content telemetry (gen_ai request/usage attributes) is still
   present with include_content=False (no MORE and no LESS than before).

Deliberate adaptations to the pydantic-ai 2.52 API surface (intent
preserved from the original brief):

- Per-agent instrumentation uses the ``Agent.instrument`` *property
  setter* on 2.52 (``agent.instrument = settings``) instead of a
  ``agent.instrument(settings)`` call. This keeps instrumentation
  scoped to this test's agent — the brief's preferred "no global
  state" approach. The global helper
  ``configure_pydantic_ai_instrumentation`` is intentionally NOT used
  here because it mutates class-level state (``Agent.instrument_all``)
  that would leak onto every other agent in the suite.
- With a structured ``output_type``, 2.52's TestModel requires
  ``custom_output_args`` (``custom_output_text`` is rejected in tool
  output mode), so the output marker is carried in a structured field
  value — output rendering is still exercised.
- The error-path companion uses TestModel's genuine failure mode
  (structured output args that fail validation -> retries exhausted ->
  ``UnexpectedModelBehavior``) instead of a non-string prompt, because
  a string prompt does not raise on 2.52. No artificial failure path
  is invented.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from pydantic import BaseModel
from pydantic_ai import Agent, InstrumentationSettings
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models.test import TestModel

if TYPE_CHECKING:
    from collections.abc import Sequence

    from opentelemetry.sdk.trace import ReadableSpan

SECRET_INSTRUCTION = "SECRET-INSTRUCTION-MARKER-7f3a"
SECRET_PROMPT = "SECRET-USER-PROMPT-MARKER-b81c"
SECRET_OUTPUT = "SECRET-OUTPUT-MARKER-4d29"

_MARKERS = (SECRET_INSTRUCTION, SECRET_PROMPT, SECRET_OUTPUT)


class _LeakProbeOutput(BaseModel):
    """Structured output so output-template rendering is also exercised."""

    verdict: str
    reason: str


def _instrumented_agent(
    model: TestModel,
    provider: TracerProvider,
    *,
    include_content: bool,
) -> Agent[None, _LeakProbeOutput]:
    agent: Agent[None, _LeakProbeOutput] = Agent(
        model,
        instructions=SECRET_INSTRUCTION,
        output_type=_LeakProbeOutput,
    )
    agent.instrument = InstrumentationSettings(
        tracer_provider=provider,
        include_content=include_content,
        include_binary_content=False,
    )
    return agent


def _spans_for_run(include_content: bool) -> Sequence[ReadableSpan]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    agent = _instrumented_agent(
        TestModel(custom_output_args={"verdict": SECRET_OUTPUT, "reason": "probe"}),
        provider,
        include_content=include_content,
    )
    agent.run_sync(SECRET_PROMPT)
    provider.force_flush()
    return exporter.get_finished_spans()


def _all_attribute_values(spans: Sequence[ReadableSpan]) -> list[str]:
    """Every string the advisory's leak vectors can carry content in.

    Covers span attributes, event attributes, and error-status
    descriptions (the exception/status vector from GHSA-4x9p-g9wm-8q7f).
    """
    values: list[str] = []
    for span in spans:
        values.extend(str(v) for v in (span.attributes or {}).values())
        if span.status.description is not None:
            values.append(str(span.status.description))
        for event in span.events:
            values.extend(str(v) for v in (event.attributes or {}).values())
    return values


def test_include_content_false_leaks_no_content() -> None:
    spans = _spans_for_run(include_content=False)
    assert spans, "expected at least one pydantic-ai span"
    joined = "\n".join(_all_attribute_values(spans))
    for marker in _MARKERS:
        assert marker not in joined, f"content leak: {marker} found in span data"


def test_include_content_true_captures_content_negative_control() -> None:
    spans = _spans_for_run(include_content=True)
    joined = "\n".join(_all_attribute_values(spans))
    assert SECRET_PROMPT in joined or SECRET_INSTRUCTION in joined, (
        "negative control failed: include_content=True must capture content"
    )


def test_include_content_false_still_emits_non_content_telemetry() -> None:
    spans = _spans_for_run(include_content=False)
    attr_names: set[str] = set()
    for span in spans:
        attr_names.update((span.attributes or {}).keys())
    assert any(name.startswith("gen_ai") or "pydantic_ai" in name for name in attr_names), (
        "expected gen_ai/pydantic_ai telemetry attributes to survive include_content=False"
    )


@pytest.mark.parametrize("include_content", [False, True])
def test_no_span_exceptions_or_errors_leak(include_content: bool) -> None:
    """Error-status/exception redaction companion (same advisory family).

    Drives a genuine failure path: the structured output args fail
    validation, retries are exhausted, and the run raises
    ``UnexpectedModelBehavior`` — exactly the error path whose status
    description and exception event leaked content in pydantic-ai < 2.44.

    include_content=False must carry no content (security property, plus
    a redacted error-status description); include_content=True must
    carry content (negative control for this error path).
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    agent = _instrumented_agent(
        # Ints fail the str fields of _LeakProbeOutput by design -> ValidationError
        # -> retries exhausted -> UnexpectedModelBehavior (the error path).
        TestModel(custom_output_args={"verdict": 123, "reason": 456}),
        provider,
        include_content=include_content,
    )
    with pytest.raises(UnexpectedModelBehavior):
        agent.run_sync(SECRET_PROMPT)
    provider.force_flush()
    spans = exporter.get_finished_spans()
    joined = "\n".join(_all_attribute_values(spans))
    if include_content:
        assert SECRET_INSTRUCTION in joined or SECRET_PROMPT in joined, (
            "negative control failed: include_content=True must capture "
            "content on the error path too"
        )
        return
    for marker in _MARKERS:
        assert marker not in joined, f"content leak on error path: {marker} found in span data"
    error_spans = [s for s in spans if s.status.status_code.name == "ERROR"]
    assert error_spans, "expected the failed run to produce an ERROR-status span"
    assert all(s.status.description is None for s in error_spans), (
        "error-status description must be redacted when include_content=False"
    )
