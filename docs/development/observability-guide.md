# Observability Guide — OpenTelemetry Trace Chain

> **Status:** ✅ Current for ADR-031 Phase 1
> **Date:** 2026-06-04
> **See also:** [ADR-031: Local-First OpenTelemetry Observability](../architecture/decisions/ADR-031-local-first-opentelemetry-observability.md)

Narrare uses **OpenTelemetry as the only trace standard**. API requests,
FastAPI spans, and Pydantic-AI agent/model/tool spans share the same OTel
runtime configuration when an OTLP endpoint is configured.

Langfuse has been removed from the core runtime. Logfire is not used for core
observability.

---

## 1. Current Architecture

```text
HTTP request
  → FastAPI OpenTelemetry instrumentation
  → RequestLoggingMiddleware binds request/trace context for structlog
  → Service layer runs inside the active OTel context
  → Pydantic-AI native instrumentation emits agent/model/tool spans
  → SSE helpers can add x_trace_id / x_span_id to streamed events
```

| Component | File | Purpose |
|-----------|------|---------|
| OTel setup | `apps/api/narrare/_app/telemetry.py` | Configures `TracerProvider`, OTLP exporter, FastAPI instrumentation, and Pydantic-AI instrumentation. |
| Trace helpers | `apps/api/narrare/_app/observability.py` | Provides `get_current_trace_context()`, `get_tracer(name)`, `enrich_sse_data()`, and `get_observability_status()`. |
| Agent instrumentation | `packages/core/narrare_core/agents/instrumentation.py` | Calls `Agent.instrument_all(InstrumentationSettings(...))` for native Pydantic-AI OTel spans. |
| Metrics | `packages/core/narrare_core/llm/metrics.py` | Keeps Prometheus-compatible LLM metrics for requests, tokens, cache, duration, retries, and cost estimates. |
| Logs | `apps/api/narrare/_app/logging.py` | Uses structlog for structured logs. |
| Health | `apps/api/narrare/metrics/router.py` | Exposes OTel availability in `/health`. |

---

## 2. What Changed in ADR-031 Phase 1

- `packages/core/narrare_core/llm/observability.py` was removed.
- `LLMObservability` is no longer exported from `narrare_core.llm`.
- `langfuse` was removed from core dependencies and the lockfile.
- Pydantic-AI OpenTelemetry instrumentation is enabled during API telemetry setup
  through `configure_pydantic_ai_instrumentation(...)`.
- `get_tracer(name: str)` is available as the shared tracer helper for API-side
  custom spans and returns a no-op tracer when OTel is unavailable.

Forbidden steady states from ADR-031 remain in force:

- No Langfuse runtime dependency or dormant Langfuse adapter.
- No Logfire requirement for core observability.
- No mixed trace stack where some AI spans go to Langfuse and others go to OTel.

---

## 3. Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | Enables OTel export when set, for example `http://localhost:4317`. If unset, telemetry setup is a no-op. |
| `OTEL_SERVICE_NAME` | `narrare-api` | Service name attached to exported spans. |
| `NARRARE_OTEL_INCLUDE_CONTENT` | `true` outside production, `false` in production | Controls whether Pydantic-AI spans may include prompt/completion content. |
| `ENVIRONMENT` | `development` | Used to choose the safe default for `NARRARE_OTEL_INCLUDE_CONTENT`. |
| `LOG_LEVEL` | `INFO` | Structured log level. |
| `LOG_FILE` | unset | Optional development log file path. |

Recommended production posture:

```bash
ENVIRONMENT=production
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=narrare-api
NARRARE_OTEL_INCLUDE_CONTENT=false
```

Development may leave `NARRARE_OTEL_INCLUDE_CONTENT` unset; content capture then
defaults to `true` to make local debugging easier. Production defaults to `false`
to avoid exporting prompt or completion content unless explicitly overridden.

---

## 4. Trace Context and SSE

`get_current_trace_context()` returns the active OTel IDs when a recording span is
available:

```json
{
  "x_trace_id": "ffa1b2c3d4e5f6a7b8c9d0e1f2a3b4c5",
  "x_span_id": "a1b2c3d4e5f6a7b8"
}
```

`enrich_sse_data(data)` merges those fields into SSE event payloads. When OTel is
not configured or no active span exists, the original payload is returned unchanged.

---

## 5. Failure State

Observability must degrade visibly, not silently.

- If OpenTelemetry imports or tracer lookup fail, helpers return empty trace
  context or no-op tracers instead of crashing request handling.
- The first unavailable/degraded state emits one structured warning via structlog.
- `/health` includes the current observability state:

```json
{
  "status": "ok",
  "observability": {
    "available": true,
    "failure_reason": "",
    "warning_emitted": false
  }
}
```

When OTel is unavailable:

```json
{
  "status": "ok",
  "observability": {
    "available": false,
    "failure_reason": "ImportError: No module named 'opentelemetry.trace'",
    "warning_emitted": true
  }
}
```

---

## 6. Extending Tracing in API Code

Use the shared API helper instead of importing `opentelemetry.trace` directly in
every call site:

```python
from narrare._app.observability import get_tracer

tracer = get_tracer(__name__)

async def my_operation() -> None:
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("custom.key", "value")
        await do_something()
```

`get_tracer()` returns a no-op tracer when OTel is unavailable, so the call site
does not need its own fallback path.

---

## 7. Validation Coverage

ADR-031 Phase 1 is covered by targeted unit tests for:

- API observability helpers: `tests/unit/api/_app/test_observability.py`
- API telemetry setup and content-capture defaults: `tests/unit/api/_app/test_telemetry.py`
- Core Langfuse removal regression: `tests/unit/core/llm/test_observability.py`
- Cache metrics regression: `tests/unit/core/llm/test_cache_metrics.py`

Platform validation for the migration reported targeted tests, `ruff`,
`just typecheck`, and `just check-architecture` passing.

---

## 8. Out of Scope for Phase 1

Do not document these as implemented until their own phases land:

- Pydantic Evals runtime/reporting integration.
- mem0 v3 OSS migration details.
- ProcessHistory or durable execution observability.
- Additional custom spans for memory, event bus, WebSocket messages, or background
  tasks beyond the current shared `get_tracer()` helper.
