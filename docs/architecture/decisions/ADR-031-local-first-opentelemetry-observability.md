# ADR-031 — Local-First OpenTelemetry Observability

> **Status:** ✅ Accepted
> **Date:** 2026-06-04
> **Deciders:** User, Architecture Agent
> **Supersedes:** ADR-010
> **Related:** ADR-006, ADR-015, ADR-016, ADR-027

---

## Context

ADR-010 selected OpenTelemetry plus Langfuse for observability. That decision no longer fits Narrare's runtime reality or local-first architecture.

Observed state:

- `LLMObservability` exists for Langfuse in `packages/core/narrare_core/llm/observability.py`, but it is not wired into the runtime in a complete way.
- The API already initializes OpenTelemetry in `apps/api/narrare/_app/telemetry.py` when `OTEL_EXPORTER_OTLP_ENDPOINT` is configured.
- `/metrics` exports Prometheus metrics and `structlog` remains the logging standard.
- Pydantic AI supports native OpenTelemetry instrumentation for agent/model/tool spans without requiring Logfire.
- Logfire self-hosting is Enterprise/private-image oriented and therefore does not satisfy Narrare's local-first requirement for core functionality.

Root cause chain:

1. **Symptom:** LLM/agent observability is split between incomplete Langfuse code, API-level OTel, Prometheus metrics, and structlog logs.
2. **Why:** ADR-010 tried to solve generic distributed tracing and LLM-specific observability with two trace stacks.
3. **Why:** The decision optimized for feature coverage instead of one local-first trace standard integrated through Narrare's actual Pydantic-AI runtime.
4. **Design:** Use OpenTelemetry as the sole trace standard, Prometheus for metrics, and structlog for logs. Agent/model/tool spans come from Pydantic-AI OTel instrumentation, not from Langfuse or Logfire.

---

## Decision Drivers

- Local-first core functionality: no cloud-only or Enterprise-only observability requirement.
- One trace standard: no permanent dual trace stack.
- Native fit with Pydantic AI agents, tools, model calls, and output validation spans.
- Vendor-neutral export path to local OTel Collector, Tempo, Grafana, Loki, and Prometheus.
- RULE-01b / RULE-07 compliance: observability must not bypass the agent/model boundaries.
- RULE-20 compliance: no incomplete Langfuse wiring kept as a "future" path.

---

## Options Considered

### Option A — OpenTelemetry-only tracing with Prometheus metrics and structlog logs (chosen)

Use OpenTelemetry as the sole distributed tracing standard. Keep Prometheus metrics and structlog logs. Configure optional local backends through OTLP.

**Pros:**
- Local-first and vendor-neutral.
- One trace context across API, DB, tasks, agent/model/tool spans, and eval spans.
- Uses existing API OTel foundation.
- Compatible with Pydantic-AI native instrumentation.
- Removes incomplete Langfuse runtime dependency.

**Cons:**
- Generic OTel backends do not provide Langfuse-style LLM dashboards out of the box.
- Cost attribution and prompt-level dashboards must be implemented through spans/metrics conventions, not a dedicated SaaS UI.

### Option B — Keep OpenTelemetry + Langfuse

Continue ADR-010 and finish Langfuse wiring.

**Pros:**
- Langfuse provides LLM-specific UI and cost tracking.
- Existing dependency already present in `packages/core/pyproject.toml`.

**Cons:**
- Permanent dual trace stack.
- Langfuse is currently incomplete in runtime usage.
- Adds product coupling to an external LLM observability service.
- Conflicts with the user's decision to remove Langfuse from the core architecture.

### Option C — Logfire for all observability

Use Pydantic Logfire for Pydantic/Pydantic-AI observability.

**Pros:**
- Strong fit with Pydantic AI.
- Low-friction instrumentation.

**Cons:**
- Self-hosting is not generally available for Narrare's local-first product posture.
- Would make a cloud/Enterprise path necessary for core observability.

### Option D — Prometheus-only metrics

Drop tracing and keep only metrics/logs.

**Pros:**
- Minimal infrastructure.

**Cons:**
- Does not solve root cause: no span correlation across API, agents, tools, memory, and evals.
- Weak debugging for streaming and multi-agent workflows.

---

## Decision

**We choose Option A: OpenTelemetry-only tracing with Prometheus metrics and structlog logs.**

Narrare's accepted observability architecture is:

- **Traces:** OpenTelemetry only.
- **Metrics:** Prometheus-compatible metrics remain.
- **Logs:** `structlog` remains.
- **Optional local backends:** OTel Collector + Grafana/Tempo/Loki/Prometheus.
- **Agent/model/tool spans:** native Pydantic-AI OpenTelemetry instrumentation.

Forbidden steady states:

- Langfuse kept as a second LLM tracing stack.
- Logfire required for core Narrare functionality.
- Runtime paths where some agent spans go to Langfuse and others go to OTel.
- "Remove dependency later" as a migration endpoint.

---

## Rationale

The architecturally correct standard is not "more observability tools"; it is one trace context that every runtime component can join. OpenTelemetry is the durable standard because it is vendor-neutral, local-backend friendly, and already partially implemented in the API layer. Pydantic AI's native instrumentation gives Narrare the LLM/agent specificity ADR-010 wanted without binding the product to Langfuse or Logfire.

This is the simplest correct solution: one span model, one propagation mechanism, one export configuration, and local-first backends.

---

## Consequences

**Positive:**
- Removes an incomplete Langfuse architecture.
- Preserves local-first operation.
- Gives all clients and services one trace context.
- Aligns future eval traces with runtime traces.

**Negative / Tradeoffs:**
- Dedicated Langfuse UI features are not available by default.
- Token/cost attribution must be represented as span attributes and metrics.

**Constraints introduced:**
- Langfuse must be removed from runtime dependencies and code paths in the implementation phase.
- New observability integrations must export via OpenTelemetry or Prometheus-compatible metrics.
- Any future non-OTel observability tool requires a new ADR and explicit local-first review.

---

## Implementation Plan / Migration Plan

1. Remove Langfuse dependency from `packages/core/pyproject.toml` and lock files.
2. Delete or replace `packages/core/narrare_core/llm/observability.py`; no dormant Langfuse adapter remains.
3. Configure Pydantic-AI OpenTelemetry instrumentation at the approved runtime bootstrap boundary.
4. Define span attribute conventions for agent name, model provider, model id, intent, token counts, cost estimate, tool name, output validation result, and trace correlation id.
5. Keep `/metrics` Prometheus export and structlog trace context propagation.
6. Document optional local backend compose/profile separately in the Docs Gate.

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-01b | ✅ | Agent/model instrumentation uses Pydantic-AI/ModelRegistry paths; no direct provider calls. |
| RULE-03 | ✅ | Any new observability service/adapter in implementation requires Protocol first. |
| RULE-05 | ✅ | API telemetry remains in `_app`; core agent instrumentation remains in core agent/runtime boundaries. |
| RULE-07 | ✅ | Core does not import `apps/api`; telemetry configuration is injected/configured downward. |
| RULE-08 | ✅ | External observability integration is OTel/Prometheus only; Langfuse is removed. |
| RULE-11 | ✅ | Instrumentation failures must degrade visibly through logs/health, never silently. |
| RULE-20 | ✅ | No permanent dual Langfuse/OTel stack. |

---

## Sustainability Check

- Correct in 3 months: yes; OTel remains backend-neutral and compatible with local deployments.
- Hard-to-undo coupling: reduced by removing Langfuse coupling.
- Simplest correct solution: yes; one trace standard plus existing metrics/logs.
- Design intent clear: yes; no Logfire/Langfuse for core runtime observability.

---

## Review Triggers

- Pydantic AI changes or removes native OpenTelemetry instrumentation.
- OpenTelemetry Python v2 introduces breaking changes.
- A local-first, OSS LLM observability backend emerges that consumes OTel spans without adding a second instrumentation stack.
- Cost attribution requirements cannot be met with OTel attributes and metrics.
