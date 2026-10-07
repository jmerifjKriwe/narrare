# STATS-002 — Embeddings Cost Capture — Design Addendum

- **Date:** 2026-10-07
- **Status:** PO-ratified (analytics program decision sheet, item D; sequencing C→D→B→A→E)
- **Amends:** `docs/superpowers/specs/2026-10-05-stats002-cost-tracking-design.md` (v1) —
  this addendum implements the "embeddings cost" deferred slice named in its §9
- **ADR:** ADR-093 Post-Implementation Amendment (2026-10-07) — decision 4 becomes
  **three disjoint emission surfaces**; this document is the binding implementation
  spec for surface (c)

---

## 1. Context & Goal

v1 tracks both LLM populations (capability agents + registry convenience layer) but
embedding API calls are untracked spend — every KB ingest, every semantic search
query, notes search, corpus passes. The only seam that sees embedding **token
counts** is the provider level: `OpenAIEmbeddingProvider.embed_texts`
(`packages/core/narrare_core/llm/embedding_providers.py:120-203`) receives the
OpenAI SDK `CreateEmbeddingResponse`, whose `usage` field is **required** by the SDK
(openai 3.x: `data, model, object, usage`) but currently discarded. The API layer
above (`embeddings/service.py` → `EmbeddingStoreProtocol.generate`) sees only
vectors — changing that Protocol would ripple through the store contract and every
caller. Therefore: emit at the provider.

**Goal:** every billable embedding API call lands in `usage_records` with
`intent="embeddings"` and a strict write-time cost, closing the honesty gap before
budgets (program stage A) build on the totals.

## 2. Decisions

| # | Decision | Ruling |
|---|----------|--------|
| D-1 | Emission point | `OpenAIEmbeddingProvider.embed_texts`, inside the batch loop, **one `UsageEvent` per API batch response** (batches of ≤100 texts — the correct per-call granularity; a multi-batch `embed_texts` emits one event per batch). |
| D-2 | Event shape | `intent="embeddings"` (stable key; FE label key added), `provider="openai"` (the class is OpenAI-specific — no dynamic provider), `model_id` = the resolved `model_name` (incl. the `model` override param), `tokens_in` = `response.usage.total_tokens` (`prompt_tokens == total_tokens` for embeddings), `tokens_out=0`, cache tokens 0, `duration_seconds` = the individual batch call's duration (not the whole `embed_texts` span). |
| D-3 | Cost | strict `estimate_cost_usd("openai", model_name, tokens_in=..., tokens_out=0)` — models.dev carries embedding input-only rates (e.g. text-embedding-3-small $0.02/1M, output 0); unknown/custom model names ⇒ `cost_usd NULL` = unpriced (unchanged strict semantics). |
| D-4 | Guard | a new helper `emit_embedding_usage_event(...)` in `narrare_core/llm/usage_events.py` following the FU-1 pattern: event construction + emission **inside** the never-raise catch-all (`usage_event_emission_failed` warning); `embed_texts` itself stays non-raising for telemetry on the happy path unchanged. |
| D-5 | Usage-omitted edge | a compatible gateway may omit `usage` despite the SDK type ⇒ `getattr` guard; `usage is None` (or `total_tokens is None`) ⇒ **skip emission + `logger.debug`** — no event, no raise (documented edge). |
| D-6 | Attribution | `usage_user_id`/`usage_novel_id` ContextVars (ADR-093 D3 lists embedding hooks among the `create_task` context-inheritors — ingest/search jobs attribute correctly; context-less calls ⇒ `user_id None` ⇒ sink skips, consistent with F2). |
| D-7 | TestEmbeddingProvider | emits **nothing** (no cost — correct by construction; assert in tests). |
| D-8 | Storage | same `usage_records` table (a separate table would split month totals/trend for no gain; `by_intent` already isolates embeddings rows). |
| D-9 | Budget interplay | embeddings count toward budget **totals** but are **not pre-call gated** (`get_model()` is not on their path) — recorded as a v1 limitation + review trigger in ADR-094 D1. Unpriced embedding calls stay excluded from USD budget math (visible as `unpriced_calls`). |

## 3. Implementation Notes

- New helper in `usage_events.py` (mirrors `emit_registry_usage_event`'s FU-1 shape):
  `async def emit_embedding_usage_event(*, model_name: str, tokens_in: int, duration_seconds: float) -> None` — builds the event (`intent="embeddings"`, `provider="openai"`, `tokens_out=0`, cost via strict estimation, attribution from ContextVars) and emits through the guarded seam.
- Provider: wrap the single `client.embeddings.create` call with a per-batch monotonic
  timestamp; after the response, read usage (D-5 guard) and `await emit_embedding_usage_event(...)`.
- No Protocol changes, no API-layer changes, no new dependencies.

## 4. Testing Strategy

- **Provider emission** (fake/injected OpenAI client, house pattern from
  `tests/unit/core/llm/test_embeddings.py`): multi-batch input ⇒ one event per batch
  with per-batch durations; tokens from `usage.total_tokens`; `model` override
  reflected in `model_id`; attribution ContextVars land on the event; cost
  monkeypatched at the helper's import site (no network); `usage=None` ⇒ no event, no
  raise, debug log; garbage usage value ⇒ no raise (FU-1 guard); all-empty-texts
  input ⇒ zero API calls ⇒ zero events; `TestEmbeddingProvider` ⇒ zero events.
- **Cost math**: strict pricing path already pinned in v1 tests; one embedding-model
  rate test (`get_rates_strict` monkeypatched to `{"input": 0.02, "output": 0.0}` ⇒
  1M tokens ⇒ `$0.02`).

## 5. Documentation Riders (slice D2b)

- Feature file `docs/features/analytics/STATS-002-cost-tracking.md`: remove
  "embeddings cost" from the deferred slices AND from the known-untracked list; fix
  the seam path drift (named `narrare_core/embeddings/`, actual surface is
  `narrare_core/llm/embedding_providers.py`); note the ADR-093 amendment.
- FE intent map: add the `embeddings` label key (en/de/fr).

## 6. Out of Scope

Other embedding providers (none exist beyond OpenAI + TestEmbeddingProvider) ·
API-layer emission (Protocol change rejected) · separate embeddings table (rejected) ·
pre-call gating of embeddings (ADR-094 D1 limitation, review trigger recorded) ·
per-source-type attribution (provider has no source context — flat `intent`).
