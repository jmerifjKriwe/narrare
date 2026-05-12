# ADR-010 — Observability Strategy

> **Status:** ✅ Accepted
> **Date:** 2026-05-12
> **Deciders:** Architecture Agent
> **Supersedes:** prometheus-client selection in ADR-006

---

## Context

Current observability: **prometheus-client** for metrics only. No distributed
tracing, no log correlation, no structured trace context.

- **LLM calls are opaque.** Can't trace prompt → response → cost → latency
  per intent.
- **SSE streaming breaks debugging.** Without correlation IDs, logs from the
  same request scatter across unrelated entries.
- **No end-to-end context.** User action → LLM call → memory op → embedding
  update are unlinked events.

No existing instrumentation to migrate. The "OTel when we need tracing" time
is now.

---

## Decision Drivers

- Full-stack observability — metrics, traces, logs in one system
- LLM-specific insight — prompt tracking, token costs, latency per intent
- Self-hostable — local-first philosophy
- Correlation — trace_id links logs, spans, and LLM calls
- Vendor-neutral instrumentation

---

## Options Considered

### Option A — OpenTelemetry + Langfuse (chosen)

OTel for vendor-neutral metrics/tracing/logging. Langfuse for LLM-specific
observability (prompt tracking, cost analysis, evaluation). OTel Collector
exports to Prometheus (metrics), Jaeger/Zipkin (traces), Loki (logs).

**Pros:** Full-stack from day one; LLM-specific dashboards; self-hostable;
vendor-neutral; shared trace context between OTel spans and Langfuse.
**Cons:** OTel Collector as additional infra; Langfuse needs its own PostgreSQL.

### Option B — OpenTelemetry + Phoenix (Arize)

Strong for LLM evaluation with notebook integration.

**Pros:** Excellent evaluation tooling; good for ML experimentation.
**Cons:** Self-hosting less mature; smaller community.

### Option C — prometheus-client + Jaeger separately

**Pros:** Minimal change.
**Cons:** Fragmented — no correlation; no LLM-specific observability.

### Option D — Datadog / New Relic (SaaS)

**Pros:** Turnkey.
**Cons:** Cloud-only contradicts local-first; vendor lock-in; expensive for LLM spans.

---

## Decision

**We choose OpenTelemetry + Langfuse.**

OTel gives vendor-neutral full-stack observability. Langfuse adds LLM-specific
insight that generic APM can't — prompt versioning, token cost tracking,
evaluation workflows. Both self-hostable.

---

## Rationale

LLM observability differs from generic HTTP observability. A single "POST
/chat" may contain three LLM calls with different latencies, token costs,
and failure modes. Generic APM treats this as one span. Langfuse understands
LLM call structure natively. Combined with OTel correlation, we trace from
HTTP request → gateway → model calls → memory ops, all linked by trace_id.

---

## Consequences

**Positive:** End-to-end trace correlation; LLM cost tracking per intent/user;
structured logging with trace_id; portable backends.
**Negative:** OTel Collector + Langfuse add infra complexity.

**Changes from TECH_STACK.md:**
- Remove: `prometheus-client`
- Add: `opentelemetry-api`, `opentelemetry-sdk`,
  `opentelemetry-instrumentation-fastapi`, `opentelemetry-exporter-otlp`,
  `langfuse`

---

## Implementation Notes

```toml
# pyproject.toml
"opentelemetry-api>=1.24.0",
"opentelemetry-sdk>=1.24.0",
"opentelemetry-instrumentation-fastapi>=0.45b0",
"opentelemetry-exporter-otlp>=1.24.0",
"langfuse>=2.30.0",
```

Gateway methods get both OTel spans and Langfuse `@observe` decorator:

```python
# core/llm/gateway.py
from langfuse.decorators import observe

class LLMGateway:
    @observe(name="llm-chat")
    async def chat(self, messages: list[dict], **kwargs) -> str: ...

    @observe(name="llm-embed")
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

Correlation ID middleware injects trace_id into structlog context:

```python
# _app/middleware.py
@app.middleware("http")
async def inject_trace_id(request, call_next):
    span = trace.get_current_span().get_span_context()
    structlog.contextvars.bind_contextvars(trace_id=format(span.trace_id, "032x"))
    response = await call_next(request)
    response.headers["X-Trace-ID"] = format(span.trace_id, "032x")
    return response
```

---

## Review Trigger

- [ ] If Langfuse changes self-hosting licensing
- [ ] If OTel Python SDK has a breaking v2 release
- [ ] If LLM call volume makes Langfuse storage costs unsustainable
