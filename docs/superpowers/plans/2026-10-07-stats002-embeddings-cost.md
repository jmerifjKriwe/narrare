# STATS-002 — Embeddings Cost Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every billable embedding API call lands in `usage_records` (`intent="embeddings"`, strict write-time cost) via a guarded provider-level emission — ADR-093's third disjoint emission surface.

**Architecture:** One new guarded helper in the Core seam (`usage_events.py`), called once per API batch response inside `OpenAIEmbeddingProvider.embed_texts`; FE label key + feature-file docs. Binding spec: `docs/superpowers/specs/2026-10-07-stats002-embeddings-cost-design.md` (decisions D-1..D-9). ADR-093 Post-Implementation Amendment records the surface change.

**Tech Stack:** Python 3.14 · OpenAI SDK (response `usage` required) · existing usage-event seam · i18n en/de/fr.

## Global Constraints

- Project language English; Core stays HTTP/DB-free; TDD (RED→GREEN evidence); ≤3 files / ≤250 new LOC per task; conventional commits; never `git commit --no-verify`/`-n`.
- Never-raise discipline: helper construction + emission inside the FU-1 catch-all (`usage_event_emission_failed`).
- Attribution via `usage_user_id`/`usage_novel_id` ContextVars only.
- Test commands: `uv run pytest <path> -v` from repo root; i18n `pnpm check:i18n`.

---

### Task D1: Core — embedding usage-event emission

**Files:**
- Modify: `packages/core/narrare_core/llm/usage_events.py`
- Modify: `packages/core/narrare_core/llm/embedding_providers.py`
- Test: `tests/unit/core/llm/test_embedding_usage_events.py` (create; if a provider-test fake for the injected client already exists in `tests/unit/core/llm/test_embeddings.py`, mirror it)

**Interfaces:**
- Consumes: `UsageEvent`, `emit_usage_event`, `estimate_cost_usd`, `usage_user_id`, `usage_novel_id` (all in `usage_events.py`); the injected-client pattern of `OpenAIEmbeddingProvider` (`self._client`).
- Produces:

```python
async def emit_embedding_usage_event(
    *,
    model_name: str,
    tokens_in: int,
    duration_seconds: float,
) -> None:
    """Guarded emission for one embedding API batch call (ADR-093 surface c)."""
```

Construction + emission inside the FU-1 catch-all: event = `intent="embeddings"`, `provider="openai"`, `model_id=model_name`, `tokens_in=tokens_in`, `tokens_out=0`, cache tokens 0, `duration_seconds`, `cost_usd=estimate_cost_usd("openai", model_name, tokens_in=tokens_in, tokens_out=0)`, attribution from the ContextVars; any exception ⇒ `logger.warning("usage_event_emission_failed", ...)`.

Provider change (inside `embed_texts`'s batch loop, lines ~174-181): wrap the single `client.embeddings.create(...)` call with a per-batch `time.monotonic()` start; after the response read usage defensively:

```python
usage = getattr(response, "usage", None)
total_tokens = getattr(usage, "total_tokens", None) if usage is not None else None
if total_tokens:
    await emit_embedding_usage_event(
        model_name=model_name,
        tokens_in=int(total_tokens),
        duration_seconds=time.monotonic() - batch_start,
    )
```

(`total_tokens` falsy or missing ⇒ skip silently-per-spec-D5 — a `logger.debug` inside the helper path is acceptable; `TestEmbeddingProvider` is untouched and emits nothing.)

- [ ] **Step 1: Write failing tests** (fake injected client returning controlled `CreateEmbeddingResponse`-shaped objects — dataclass stubs with `data`/`usage`):

```python
async def test_one_event_per_batch(...):
    # 150 texts, batch_size 100 -> 2 API calls -> 2 events with per-batch durations
async def test_event_fields_and_attribution(...):
    # intent=="embeddings", provider=="openai", model_id from override param,
    # tokens_in from usage.total_tokens, tokens_out==0, ContextVars land on event
async def test_cost_is_strict(...):
    # monkeypatch estimate at usage_events' module: called with ("openai", model, tokens_in=..., tokens_out=0)
async def test_usage_omitted_skips_event(...):
    # response without usage -> no event, no raise
async def test_garbage_usage_does_not_raise(...):
    # monkeypatch emit helper target? no: pass a response whose total_tokens is "garbage"
    # -> helper guard swallows (warning), embed_texts still returns vectors
async def test_all_empty_texts_emit_nothing(...): ...
async def test_provider_zero_token_response_emits_nothing(...):  # total_tokens=0 -> skip
def test_test_provider_emits_nothing(...): ...
```

- [ ] **Step 2: Run — expect FAIL** (`AttributeError: module ... has no attribute 'emit_embedding_usage_event'` / no events recorded).
- [ ] **Step 3: Implement helper + provider wiring.**
- [ ] **Step 4: Run — expect PASS** (`uv run pytest tests/unit/core/llm/test_embedding_usage_events.py tests/unit/core/llm/test_embeddings.py -v` — no provider regression; plus the full `tests/unit/core/llm` suite).
- [ ] **Step 5: Commit**

```bash
git add packages/core/narrare_core/llm/usage_events.py packages/core/narrare_core/llm/embedding_providers.py tests/unit/core/llm/test_embedding_usage_events.py
git commit -m "feat(core): embedding usage-event emission (ADR-093 surface c)"
```

---

### Task D2: i18n — `embeddings` intent label

**Files:**
- Modify: `packages/i18n/messages/en/analytics.json`
- Modify: `packages/i18n/messages/de/analytics.json`
- Modify: `packages/i18n/messages/fr/analytics.json`

**Interfaces:**
- Consumes: the `analytics.costs.intent.*` map (58 keys + wiki_chapter/wiki_generation/interview_question landed earlier).
- Produces: `embeddings` label key at the alphabetically consistent position — en "Embeddings"; de/fr anchored to the existing catalog's usage of the loanword (check `studio.json`/`settings-ai.json` for "Embedding(s)"/"Embeddings" precedent; keep consistent).

- [ ] **Step 1:** Add the key to all three locales (identical position, values only).
- [ ] **Step 2:** `pnpm check:i18n` green.
- [ ] **Step 3: Commit** `feat(i18n): embeddings cost-intent label (en/de/fr)` (add the three files).

---

### Task D3: Docs — feature-file closure for the slice

**Files:**
- Modify: `docs/features/analytics/STATS-002-cost-tracking.md`

**Interfaces / requirements (spec §5):**
- Remove "embeddings cost" from the deferred-slices list AND from the known-untracked list (both blockquote note and body list if present).
- Fix the seam path drift: the file names `narrare_core/embeddings/` as the (former) seam — the actual surface is `packages/core/narrare_core/llm/embedding_providers.py`.
- Add a dated history note (2026-10-07): embeddings cost implemented per ADR-093 Post-Implementation Amendment (surface c); budget interplay per ADR-094 D1 (counted in totals, not pre-call gated).
- Run `just check-architecture` (doc drift).

- [ ] **Step 1: Amend the file.** **Step 2: Gate green.**
- [ ] **Step 3: Commit** `docs(features): STATS-002 embeddings cost implemented — surface c` (add the file).
