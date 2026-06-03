# Observability Guide — End-to-End Trace Chain

> **Status:** ✅ Documented
> **Date:** 2026-06-03
> **See also:** [ADR-010: Observability Strategy](../architecture/decisions/ADR-010-observability.md)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Correlation-ID Strategy](#2-correlation-id-strategy)
3. [Component Analysis](#3-component-analysis)
4. [Identified Gaps](#4-identified-gaps)
5. [How to Extend](#5-how-to-extend)
6. [Debugging a Production Issue](#6-debugging-a-production-issue)

---

## 1. Architecture Overview

The trace chain flows through four layers. Each layer propagates a `trace_id`
that links request, service call, LLM call, and response together.

```
┌────────────────────────────────────────────────────────────────────────┐
│  1. HTTP Client                                                        │
│     Headers: X-Request-ID, X-Trace-ID (← response)                     │
│     SSE data: x_trace_id, x_span_id (per-event)                        │
└────────────────────┬───────────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│  2. FastAPI Middleware (middleware.py)                                  │
│     • Extracts/accepts X-Request-ID from request header                │
│     • Reads OTel trace context (trace_id, span_id)                    │
│     • Binds structlog context vars: request_id, trace_id, span_id      │
│     • Sets response headers: X-Request-ID, X-Trace-ID                 │
└────────────────────┬───────────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│  3. Service Layer                                                      │
│     • Receives trace context via structlog.contextvars                │
│     • Propagates via OTel spans (auto-instrumented by FastAPI)        │
│     • Logs with trace_id automatically included                       │
│     • Publishes DomainEvents with correlation_id                      │
└────────────────────┬───────────────────────────────────────────────────┘
                     │
                     ├──────────────────────────────────┐
                     ▼                                  ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│  4a. Agent / LLM Call        │  │  4b. Memory (mem0)           │
│                              │  │                              │
│  observability.py (Langfuse) │  │  mem0_client.py              │
│  → LLM trace name:           │  │  ⚠ No OTel spans (gap)      │
│    "llm.{intent}"            │  │                              │
│                              │  │  Logs with structlog but     │
│  capabilities/observability  │  │  no explicit OTel tracing    │
│  → Prometheus metrics        │  │                              │
│    (narrare_llm_*)           │  │                              │
└──────────────────────────────┘  └──────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│  5. SSE Response / StreamingResponse                                   │
│     • HTTP headers: X-Request-ID, X-Trace-ID (from middleware)        │
│     • Per-event payload: x_trace_id, x_span_id in JSON data          │
│     • Logs: trace_id in every structlog entry                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Trace Components Summary

| Component | File | Purpose |
|-----------|------|---------|
| OTel Setup | `_app/telemetry.py` | Configure OTel SDK, exporter, FastAPI instrumentation |
| Middleware | `_app/middleware.py` | Extract trace context, bind structlog, set response headers |
| Structlog | `_app/logging.py` | Structured logging with `merge_contextvars` processor |
| Trace Helper | `_app/observability.py` | Shared `get_current_trace_context()` and `get_observability_status()` for all components |
| LLM Tracing | `core/llm/observability.py` | Langfuse integration for LLM call tracing |
| LLM Metrics | `core/llm/metrics.py` | Prometheus metrics (success/failure/tokens/cache/duration) |
| Agent Observability | `core/agents/capabilities/observability.py` | Per-agent metrics via `NarrareObservability` capability |
| Event Bus | `_app/events.py` | Redis Pub/Sub events with `correlation_id` field |
| Event Publisher | `events/publisher.py` | In-process event dispatch (no automatic trace propagation) |
| Prometheus | `metrics/router.py` | `/health` (with OTel status), `/ready`, `/metrics` endpoints |

---

## 2. Correlation-ID Strategy

### 2.1 Trace ID Generation

| Level | ID | Source | Format |
|-------|----|--------|--------|
| HTTP | `X-Request-ID` | Client header or middleware-generated UUID v4 | Standard UUID (hex) |
| OTel | `trace_id` | OpenTelemetry SDK (auto-generated per request) | 32-char hex |
| OTel | `span_id` | OpenTelemetry SDK (auto-generated per span) | 16-char hex |
| Event | `correlation_id` | Manually set in `DomainEvent` | OTel trace_id when available, else UUID |

### 2.2 Propagation Path

1. **HTTP Request Enters:**
   - Client sends `X-Request-ID` (optional — UUID generated if missing)
   - OTel `FastAPIInstrumentor` creates a root span automatically

2. **Middleware (`RequestLoggingMiddleware`):**
   - Reads `X-Request-ID` from request headers (or generates one)
   - Extracts OTel trace context via `get_current_trace_context()`
   - Binds `request_id`, `trace_id`, `span_id`, `method`, `path` to structlog context
   - All subsequent logs in this request automatically include these fields

3. **Service Layer:**
   - OTel context propagates implicitly (Python `contextvars`)
   - Any `structlog` log call includes the bound context vars
   - `NarrareObservability` capability records Prometheus metrics per LLM call

4. **SSE Response:**
   - HTTP headers carry `X-Request-ID` and `X-Trace-ID` (from middleware)
   - Each SSE event's JSON data includes `x_trace_id` and `x_span_id`
   - Frontend can access trace context from any SSE event

### 2.3 Log Record Example

With OTel enabled, structlog entries look like:

```json
{
  "event": "http_request",
  "request_id": "a1b2c3d4-...",
  "trace_id": "ffa1b2c3d4e5f6a7b8c9d0e1f2a3b4c5",
  "span_id": "a1b2c3d4e5f6a7b8",
  "method": "POST",
  "path": "/api/v1/writing/chapters/.../co-author",
  "status": 200,
  "duration_ms": 4231,
  "timestamp": "2026-06-03T12:00:00Z"
}
```

---

## 3. Component Analysis

### 3.1 `_app/telemetry.py` — OTel Setup

**What it does:**
- Initializes `TracerProvider` with `OTLPSpanExporter`
- Instruments FastAPI via `FastAPIInstrumentor.instrument_app()`
- Graceful no-op when `OTEL_EXPORTER_OTLP_ENDPOINT` is not set

**Configuration:**
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=narrare-api
```

**Limitations:**
- Only configures **tracing** (spans). No metrics via OTel SDK.
- No `BatchSpanProcessor` customisation (defaults apply).
- No OTel log correlation (uses structlog instead of OTel logging SDK).

### 3.1b `_app/observability.py` — Degradation Visibility

**What it does:**
- Probes OTel availability exactly once on first call to `get_current_trace_context()`
- Caches availability state: `_otel_available`, `_failure_reason`, `_warning_emitted`
- Emits exactly one structured warning via structlog when OTel is unavailable
- All subsequent calls return silently (no log spam)
- Thread-safe via `threading.Lock`

**Public API:**
- `get_current_trace_context()` — returns trace context dict (unchanged, but now
  short-circuits when OTel is unavailable)
- `get_observability_status()` — returns `{"available": bool, "failure_reason": str,
  "warning_emitted": bool}` for health-endpoint reporting
- `enrich_sse_data()` — unchanged

**Health endpoint integration:**
- `GET /health` now includes an `observability` field from `get_observability_status()`
- Operators can detect degraded observability without inspecting logs

**When OTel degrades at runtime:**
- If a previously-working OTel import fails during context extraction, the module
  transitions to unavailable state and emits a one-shot `"otel_degraded"` warning

### 3.2 `core/llm/observability.py` — Langfuse Integration

**What it does:**
- Wraps LLM calls with Langfuse traces
- Records prompt, response, token usage, duration, and errors
- Uses `flush_async()` to never block the response

**Configuration:**
```bash
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_HOST=http://localhost:3000
```

**Integration with OTel:**
- **Separate system.** Langfuse traces are not linked to OTel trace IDs.
- No `trace_id` propagation from OTel to Langfuse (feature gap).
- `LLMObservability` is instantiated independently in the gateway.

### 3.3 `core/llm/metrics.py` — Prometheus Metrics

**What it does:**
- Exposes `narrare_llm_*` counters and histograms
- Tracks success/failure, tokens, duration, cache stats, cost estimates
- Metrics are label-rich (intent, model, provider, status)

**Available metrics:**
| Metric | Type | Labels |
|--------|------|--------|
| `narrare_llm_requests_total` | Counter | intent, model, provider, status |
| `narrare_llm_tokens_total` | Counter | intent, model, token_type |
| `narrare_llm_request_duration_seconds` | Histogram | intent, model |
| `narrare_llm_cost_usd_total` | Counter | intent, model |
| `narrare_llm_retry_attempts_total` | Counter | intent, error_type |
| `narrare_llm_cache_*` | Counter | intent, model, provider |

### 3.4 `core/agents/capabilities/observability.py` — Agent Observability

**What it does:**
- `NarrareObservability` capability hooks into `pydantic-ai` lifecycle
- `before_model_request`: captures start time
- `after_model_request`: records success + token usage via `metrics.py`
- `on_model_request_error`: records failure via `metrics.py`

**Context extraction:**
- Extracts `model_config` from `RunContext.deps` (e.g., `WritingDeps`)
- Falls back to `"unknown"` when deps have no model_config

### 3.5 `_app/events.py` — Event Bus

**What it does:**
- Redis Pub/Sub event bus for domain events
- `DomainEvent` includes `correlation_id` field
- Serializes events to JSON for Redis transport

**Trace propagation:**
- **Manual.** Correlation ID must be passed explicitly when creating events
- No automatic OTel context propagation to event handlers
- Publisher (`events/publisher.py`) dispatches synchronously — not traced

### 3.6 SSE Endpoints — Response Propagation

**What works:**
- HTTP response headers: all SSE `StreamingResponse` objects receive
  `X-Request-ID` and `X-Trace-ID` from the middleware
- Per-event data: each SSE event payload includes `x_trace_id` and
  `x_span_id` via the `enrich_sse_data()` helper

**Affected SSE endpoints:**
| Endpoint | File |
|----------|------|
| `POST /api/v1/writing/chapters/{id}/extend` | `writing/router_extend.py` |
| `POST /api/v1/writing/chapters/{id}/rewrite` | `writing/router_rewrite.py` |
| `POST /api/v1/writing/chapters/{id}/suggest` | `writing/router_suggest.py` |
| `POST /api/v1/writing/chapters/{id}/co-author` | `writing/router_coauthor.py` |

---

## 4. Identified Gaps

### Gap 1: mem0 Memory Client — No OTel Tracing

**Location:** `packages/core/narrare_core/memory/mem0_client.py`

**Problem:** Memory `add()`/`search()` operations are not wrapped in OTel
spans. When debugging, you can't trace from an HTTP request through memory
operations.

**Impact:** Medium. LLM → memory flow is a black box.

**Recommendation:** Wrap `add()` and `search()` on the `mem0.AsyncMemory`
client with OTel spans. See §5.1 for the pattern.

### Gap 2: Event Bus — No Automatic Trace Propagation

**Location:** `_app/events.py`, `events/publisher.py`

**Problem:** `DomainEvent.correlation_id` is set manually. Event handlers
run in-process but without OTel parent span context.

**Impact:** Low. Events carry correlation_id as a string, so the link is
preserved in logs. Tracing the event handler execution is not possible.

**Recommendation:** Wrap dispatch with OTel span, and auto-populate
`correlation_id` from current OTel trace context.

### Gap 3: Langfuse — No OTel Trace ID Linking

**Location:** `core/llm/observability.py`

**Problem:** Langfuse traces are completely separate from OTel traces.
No `trace_id` is passed from OTel to Langfuse, so you can't cross-reference
between the two systems.

**Impact:** Medium. When investigating errors, you need to search both
systems manually.

**Recommendation:** Pass `trace_id` as Langfuse `trace.metadata` field.
See `observability.py` `start_trace()` method.

### Gap 4: No Shared OTel `tracer()` Function

**Problem:** There is no shared `get_tracer()` function for components
outside FastAPI (e.g., services, background tasks) to create custom spans.

**Impact:** Low. FastAPIInstrumentor covers HTTP spans. Service spans
come from the ASGI span. Background tasks are untraced.

**Recommendation:** Add a `get_tracer(name: str)` function to
`_app/observability.py` that returns the configured tracer (or a no-op).

### Gap 5: WebSocket Sessions — No Trace Propagation

**Location:** `writing/router_sessions.py`, `writing/ws_handler.py`

**Problem:** WebSocket connections are not instrumented by
`FastAPIInstrumentor`. The middleware runs once during WebSocket upgrade
but not per-message. Trace context is lost during the session.

**Impact:** Low (current). WebSocket sessions are single-shot today. Will
matter when sessions become long-lived.

**Recommendation:** Wrap message handling in the WS handler with explicit
OTel spans.

### Gap 6: No Environment Variable for OTel in `.env.example`

**Location:** `.env.example`

**Problem:** The `.env.example` does not include OTel configuration
variables (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`).

**Impact:** Low. Discoverability is reduced.

**Recommendation:** Add commented-out OTel vars to `.env.example`.

---

## 5. How to Extend

### 5.1 Add OTel Span to a Custom Operation

```python
from opentelemetry import trace
from narrare._app.observability import get_current_trace_context

tracer = trace.get_tracer(__name__)

async def my_operation() -> None:
    with tracer.start_as_current_span("my_operation") as span:
        # Automatically linked to parent trace
        span.set_attribute("custom.key", "value")
        result = await do_something()
        span.set_attribute("result.count", len(result))
        return result
```

### 5.2 Add Tracing to a Background Task

```python
from opentelemetry import trace
from narrare._app.observability import get_current_trace_context

tracer = trace.get_tracer(__name__)

async def periodic_task() -> None:
    # Background tasks don't inherit HTTP trace context.
    # A new trace is created for each execution.
    with tracer.start_as_current_span("periodic_cleanup") as span:
        span.set_attribute("cleanup.type", "generation_requests")
        count = await cleanup_stale_generations()
        span.set_attribute("cleaned.count", count)
```

### 5.3 Propogate Correlation ID in Domain Events

```python
from narrare_core.events.types import DomainEvent, EventType
from narrare._app.observability import get_current_trace_context

def make_event(event_type: EventType, aggregate_id: UUID, **payload: Any) -> DomainEvent:
    ctx = get_current_trace_context()
    return DomainEvent(
        event_type=event_type,
        aggregate_id=aggregate_id,
        payload=payload,
        correlation_id=ctx.get("x_trace_id", ""),
    )
```

---

## 6. Debugging a Production Issue

### Scenario: "Why was this chapter content generated?"

```bash
# 1. Find the trace ID from the user's support request
TRACE_ID="ffa1b2c3d4e5f6a7b8c9d0e1f2a3b4c5"

# 2. Search structlog for all entries with this trace_id
grep "$TRACE_ID" logs/narrare.log

# 3. Search Prometheus for LLM metrics with this trace
# (Prometheus doesn't support per-trace lookup — use Jaeger/OTel Collector)

# 4. Search Langfuse for LLM call
# Langfuse UI → search by intent, model, or time range
# ⚠ No trace_id cross-reference available (Gap 3)

# 5. Check event bus correlation
grep "$TRACE_ID" logs/narrare.log | grep "event_published"
```

### Without OTel configured (development):

```bash
# Search by request_id instead
REQUEST_ID="a1b2c3d4-..."
grep "$REQUEST_ID" logs/narrare.log
```

---

## Environment Variables Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | (unset) | OTel Collector gRPC endpoint |
| `OTEL_SERVICE_NAME` | `narrare-api` | Service name in traces |
| `LANGFUSE_SECRET_KEY` | (unset) | Langfuse secret for LLM tracing |
| `LANGFUSE_PUBLIC_KEY` | (unset) | Langfuse public key |
| `LANGFUSE_HOST` | `http://localhost:3000` | Langfuse self-hosted URL |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG/INFO/WARNING/ERROR) |
| `LOG_FILE` | (unset) | File path for development dual-handler |

## Health Endpoint

The `/health` endpoint includes OTel availability status:

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

When OTel is not installed or unavailable:

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

## Test Coverage

The trace chain is validated by integration tests in
`tests/integration/observability/test_trace_propagation.py`:

| Test | What it verifies |
|------|------------------|
| `test_http_request_id_echo` | X-Request-ID propagates request → response |
| `test_otel_trace_id_propagation` | X-Trace-ID in response when OTel is active |
| `test_context_through_service_mock` | Trace context accessible from service layer |
| `test_structlog_log_correlation` | Log entries contain request_id + trace_id |

---

## Future Work

- [ ] Add OTel spans to mem0 `add()`/`search()` operations
- [ ] Link Langfuse traces with OTel trace IDs
- [ ] Auto-populate `DomainEvent.correlation_id` from OTel context
- [ ] Add `get_tracer()` helper to `_app/observability.py`
- [ ] Instrument WebSocket message handling
- [ ] Add OTel env vars to `.env.example`
