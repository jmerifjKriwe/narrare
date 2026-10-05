# STATS-002 v1 — AI Cost Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist one usage record per LLM call (tokens, model, provider, intent, write-time cost) and surface a monthly AI cost overview in a new `/analytics` panel.

**Architecture:** Core defines a `UsageEventSink` Protocol + `UsageEvent` + attribution ContextVars and emits at two disjoint points (observability capability + `ModelRegistry.run()/stream()`); the API registers a DB-writing sink at startup, persists into a new `usage_records` table, and serves one aggregation endpoint; the frontend adds an Analytics page with an "AI Costs" tab (Recharts trend). Binding docs: spec `docs/superpowers/specs/2026-10-05-stats002-cost-tracking-design.md` (PO rulings D1–D4, gate findings F1–F7), ADR-093 `docs/architecture/decisions/ADR-093-usage-event-sink-cost-persistence.md`.

**Tech Stack:** Python 3.14 · pydantic-ai capabilities · SQLAlchemy 2.0 async + Alembic · FastAPI · Next.js 16 · TanStack Query · Recharts (existing dep) · next-intl.

## Global Constraints

- Project language: **English** in all code, comments, tests, docs (except i18n message files).
- **≤ 3 files changed / ≤ 250 new LOC per task** (coordinator package cap — if a task outgrows this, STOP and report PACKAGE_TOO_LARGE).
- Core (`packages/core`) stays **HTTP- and DB-free** (no FastAPI/SQLAlchemy imports).
- RULE-03: contract/Protocol before implementation. RULE-06: routers delegate immediately; one responsibility per file. RULE-08: SQLAlchemy only in `*/repository.py`. RULE-14: Alembic migration for schema changes.
- Never-raise: cost capture may not break a product run; the emitter guard is the enforcement point.
- Conventional commits; **never** `git commit --no-verify`/`-n`.
- i18n: keys in `packages/i18n/messages/{en,de,fr}/analytics.json`.
- Test commands: backend `uv run pytest <path> -v` (from repo root), frontend `pnpm vitest run <path>` (from `packages/web`).

---

### Task 1: Core — strict pricing (exact-model rates + cache rates)

**Files:**
- Modify: `packages/core/narrare_core/llm/model_pricing.py`
- Modify: `packages/core/narrare_core/llm/cost_rates.py`
- Test: `tests/unit/core/llm/test_model_pricing_strict.py` (create)

**Interfaces:**
- Consumes: existing `resolve_model_rates(...)`, `_rates_from_metadata(...)`, `get_rates(...)` (unchanged behavior for existing callers).
- Produces (used by Task 2):
  - `resolve_model_rates(..., strict: bool = False) -> dict[str, float] | None` — with `strict=True`: metadata rates only; **never** falls back to `DEFAULT_RATES`; on fetch failure returns `None`.
  - `_rates_from_metadata` additionally surfaces `"cache_read"` / `"cache_write"` keys (floats, $/1M) when present in models.dev metadata.
  - `cost_rates.get_rates_strict(provider: str, model_id: str) -> dict[str, float] | None` — exact-model rates only (unknown model of a known provider ⇒ `None`).

- [ ] **Step 1: Write failing tests**

```python
"""Strict pricing resolution — exact-model rates only, cache rates surfaced."""
from narrare_core.llm.model_pricing import _rates_from_metadata, resolve_model_rates

def _meta(cost: dict) -> dict:
    return {"models": {"glm-5.3": {"cost": cost}}}

def test_strict_unknown_model_returns_none_even_for_known_provider():
    # Provider has DEFAULT_RATES entry, model absent from metadata
    result = resolve_model_rates(
        "openai", "totally-unknown-model",
        load_cache=lambda: {"models": {}},
        fetch_models=lambda: (_ for _ in ()).throw(AssertionError("must not fetch when cache hit")),
        save_cache=lambda _d: None,
        strict=True,
    )
    assert result is None

def test_non_strict_keeps_fallback_behavior():
    result = resolve_model_rates(
        "openai", "totally-unknown-model",
        load_cache=lambda: {"models": {}},
        fetch_models=lambda: {"models": {}},
        save_cache=lambda _d: None,
    )
    assert result == {"input": 10.0, "output": 30.0}

def test_metadata_surfaces_cache_rates():
    rates = _rates_from_metadata("zai", "glm-5.3", _meta({
        "input": 1.0, "output": 2.0, "cache_read": 0.1, "cache_write": 2.0,
    }))
    assert rates is not None
    assert rates["input"] == 1.0 and rates["output"] == 2.0
    assert rates["cache_read"] == 0.1 and rates["cache_write"] == 2.0

def test_metadata_without_cache_rates_omits_keys():
    rates = _rates_from_metadata("zai", "glm-5.3", _meta({"input": 1.0, "output": 2.0}))
    assert rates is not None
    assert "cache_read" not in rates and "cache_write" not in rates

def test_strict_fetch_failure_returns_none(monkeypatch):
    def _boom():
        raise RuntimeError("network down")
    result = resolve_model_rates(
        "openai", "gpt-4o",
        load_cache=lambda: None, fetch_models=_boom, save_cache=lambda _d: None,
        strict=True,
    )
    assert result is None
```

Also add a `get_rates_strict` test in the same file (monkeypatch `narrare_core.llm.cost_rates._load_cache` to return metadata with a known model and, in a second test, empty metadata; assert `get_rates_strict` returns the rates dict / `None` respectively).

- [ ] **Step 2: Run tests — expect FAIL**

Run: `uv run pytest tests/unit/core/llm/test_model_pricing_strict.py -v`
Expected: FAIL (`TypeError: resolve_model_rates() got an unexpected keyword argument 'strict'`).

- [ ] **Step 3: Implement**

In `model_pricing.py`: add `strict: bool = False` parameter; in the fetch-failure branch return `None` when `strict`; replace the tail fallback with `if not strict: return DEFAULT_RATES.get(provider); return None`. In `_rates_from_metadata`, after building the base dict, read `cost.get("cache_read")` / `cost.get("cache_write")` and add them when not None (same try/float guard).

In `cost_rates.py`:

```python
def get_rates_strict(provider: str, model_id: str) -> dict[str, float] | None:
    """Exact-model pricing only; never falls back to provider defaults."""
    return resolve_model_rates(
        provider, model_id,
        load_cache=_load_cache, fetch_models=_fetch_models, save_cache=_save_cache,
        strict=True,
    )
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `uv run pytest tests/unit/core/llm/test_model_pricing_strict.py -v`
Expected: all PASS. Then run the existing pricing tests (`uv run pytest tests/unit/core/llm -k "pricing or cost_rates" -v`) — all PASS (no regression).

- [ ] **Step 5: Commit**

```bash
git add packages/core/narrare_core/llm/model_pricing.py packages/core/narrare_core/llm/cost_rates.py tests/unit/core/llm/test_model_pricing_strict.py
git commit -m "feat(core): strict model pricing resolution with cache rates"
```

---

### Task 2: Core — `usage_events.py` (event, protocol, sink slot, ContextVars, cost fn)

**Files:**
- Create: `packages/core/narrare_core/llm/usage_events.py`
- Test: `tests/unit/core/llm/test_usage_events.py` (create)

**Interfaces:**
- Consumes: `get_rates_strict` (Task 1).
- Produces (used by Tasks 3, 4, 8, 9, 11, 12):

```python
@dataclass(frozen=True)
class UsageEvent:
    timestamp: datetime            # timezone-aware UTC
    intent: str
    provider: str
    model_id: str
    tokens_in: int
    tokens_out: int
    cache_read_tokens: int
    cache_creation_tokens: int
    duration_seconds: float
    cost_usd: float | None         # None = unpriced
    user_id: UUID | None
    novel_id: UUID | None

class UsageEventSink(Protocol):
    async def record(self, event: UsageEvent) -> None: ...

def set_usage_event_sink(sink: UsageEventSink | None) -> None: ...
def get_usage_event_sink() -> UsageEventSink | None: ...
async def emit_usage_event(event: UsageEvent) -> None: ...   # never raises

usage_user_id: ContextVar[UUID | None]
usage_novel_id: ContextVar[UUID | None]
def set_usage_context(*, user_id: UUID | None, novel_id: UUID | None) -> None: ...

def estimate_cost_usd(provider: str, model_id: str, *, tokens_in: int, tokens_out: int,
                      cache_read_tokens: int = 0, cache_creation_tokens: int = 0) -> float | None: ...
```

- [ ] **Step 1: Write failing tests**

```python
"""UsageEvent sink seam — protocol, slot, attribution vars, strict cost fn."""
from datetime import timezone
from uuid import uuid4

import pytest

from narrare_core.llm.usage_events import (
    UsageEvent, emit_usage_event, estimate_cost_usd,
    get_usage_event_sink, set_usage_context, set_usage_event_sink,
    usage_novel_id, usage_user_id,
)


def _event(**over):
    base = dict(
        timestamp=__import__("datetime").datetime.now(timezone.utc),
        intent="draft", provider="zai", model_id="glm-5.3",
        tokens_in=1000, tokens_out=200, cache_read_tokens=0, cache_creation_tokens=0,
        duration_seconds=1.5, cost_usd=None, user_id=None, novel_id=None,
    )
    base.update(over)
    return UsageEvent(**base)


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[UsageEvent] = []

    async def record(self, event: UsageEvent) -> None:
        self.events.append(event)


class ExplodingSink:
    async def record(self, event: UsageEvent) -> None:
        raise RuntimeError("sink down")


async def test_emit_without_sink_is_noop():
    set_usage_event_sink(None)
    await emit_usage_event(_event())  # must not raise

async def test_emit_delivers_to_registered_sink():
    sink = RecordingSink()
    set_usage_event_sink(sink)
    try:
        await emit_usage_event(_event())
        assert len(sink.events) == 1
    finally:
        set_usage_event_sink(None)

async def test_emit_swallows_sink_exception():
    set_usage_event_sink(ExplodingSink())
    try:
        await emit_usage_event(_event())  # must not raise
    finally:
        set_usage_event_sink(None)

def test_set_usage_context_sets_both_vars():
    user, novel = uuid4(), uuid4()
    set_usage_context(user_id=user, novel_id=novel)
    assert usage_user_id.get() == user
    assert usage_novel_id.get() == novel
    set_usage_context(user_id=None, novel_id=None)

def test_estimate_cost_known_model(monkeypatch):
    monkeypatch.setattr(
        "narrare_core.llm.usage_events.get_rates_strict",
        lambda p, m: {"input": 2.0, "output": 6.0},
    )
    # 1M input + 1M output => 2.0 + 6.0
    assert estimate_cost_usd("zai", "glm-5.3", tokens_in=1_000_000, tokens_out=1_000_000) == pytest.approx(8.0)

def test_estimate_cost_cache_math(monkeypatch):
    monkeypatch.setattr(
        "narrare_core.llm.usage_events.get_rates_strict",
        lambda p, m: {"input": 2.0, "output": 6.0, "cache_read": 0.2, "cache_write": 4.0},
    )
    # input includes cache reads: non-cached part at input rate, cached at cache_read,
    # cache writes at cache_write
    cost = estimate_cost_usd("zai", "glm-5.3",
                             tokens_in=1_000_000, tokens_out=0,
                             cache_read_tokens=400_000, cache_creation_tokens=100_000)
    expected = 0.6 * 2.0 + 0.4 * 0.2 + 0.1 * 4.0
    assert cost == pytest.approx(expected)

def test_estimate_cost_unknown_model_is_none(monkeypatch):
    monkeypatch.setattr("narrare_core.llm.usage_events.get_rates_strict", lambda p, m: None)
    assert estimate_cost_usd("zai", "mystery", tokens_in=10, tokens_out=10) is None

def test_estimate_cost_zero_tokens_is_zero(monkeypatch):
    monkeypatch.setattr(
        "narrare_core.llm.usage_events.get_rates_strict",
        lambda p, m: {"input": 2.0, "output": 6.0},
    )
    assert estimate_cost_usd("zai", "glm-5.3", tokens_in=0, tokens_out=0) == 0.0
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `uv run pytest tests/unit/core/llm/test_usage_events.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'narrare_core.llm.usage_events'`).

- [ ] **Step 3: Implement `usage_events.py`**

```python
"""Usage-event sink seam — ADR-093.

Core emits one ``UsageEvent`` per billable LLM call at two disjoint points
(the observability capability and ``ModelRegistry.run()/stream()``); the app
registers a DB-writing sink at startup. The seam never raises into a run.
"""

from __future__ import annotations

import structlog
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from narrare_core.llm.cost_rates import get_rates_strict

logger = structlog.get_logger(__name__)

usage_user_id: ContextVar[UUID | None] = ContextVar("usage_user_id", default=None)
usage_novel_id: ContextVar[UUID | None] = ContextVar("usage_novel_id", default=None)


def set_usage_context(*, user_id: UUID | None, novel_id: UUID | None) -> None:
    """Set attribution ContextVars (API middleware / WS bootstrap call this)."""
    usage_user_id.set(user_id)
    usage_novel_id.set(novel_id)


@dataclass(frozen=True)
class UsageEvent:
    timestamp: datetime
    intent: str
    provider: str
    model_id: str
    tokens_in: int
    tokens_out: int
    cache_read_tokens: int
    cache_creation_tokens: int
    duration_seconds: float
    cost_usd: float | None
    user_id: UUID | None
    novel_id: UUID | None


class UsageEventSink(Protocol):
    async def record(self, event: UsageEvent) -> None: ...


_sink: UsageEventSink | None = None


def set_usage_event_sink(sink: UsageEventSink | None) -> None:
    global _sink
    _sink = sink


def get_usage_event_sink() -> UsageEventSink | None:
    return _sink


async def emit_usage_event(event: UsageEvent) -> None:
    """Guarded emission — never raises into the product run (ADR-093 D1)."""
    sink = _sink
    if sink is None:
        return
    try:
        await sink.record(event)
    except Exception as exc:  # noqa: BLE001 — deliberate catch-all
        logger.warning("usage_event_sink_failed", error=str(exc))


def estimate_cost_usd(
    provider: str,
    model_id: str,
    *,
    tokens_in: int,
    tokens_out: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
) -> float | None:
    """Strict write-time cost. None = model not exactly priced (unpriced)."""
    rates: dict[str, float] | None = get_rates_strict(provider, model_id)
    if rates is None:
        return None
    non_cached_in = max(tokens_in - cache_read_tokens, 0)
    cost = (
        non_cached_in / 1e6 * rates.get("input", 0.0)
        + cache_read_tokens / 1e6 * rates.get("cache_read", rates.get("input", 0.0))
        + cache_creation_tokens / 1e6 * rates.get("cache_write", rates.get("input", 0.0))
        + tokens_out / 1e6 * rates.get("output", 0.0)
    )
    return round(cost, 6)
```

Note: `Callable` import only if used — drop unused imports (ruff).

- [ ] **Step 4: Run tests — expect PASS**

Run: `uv run pytest tests/unit/core/llm/test_usage_events.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/narrare_core/llm/usage_events.py tests/unit/core/llm/test_usage_events.py
git commit -m "feat(core): usage-event sink seam (ADR-093)"
```

---

### Task 3: Core — capability emission (`NarrareObservability`)

**Files:**
- Modify: `packages/core/narrare_core/agents/capabilities/observability.py`
- Test: `tests/unit/core/agents/capabilities/test_observability_usage_events.py` (create; if a sibling `test_observability*.py` exists, extend it instead and keep this file's tests there)

**Interfaces:**
- Consumes: `UsageEvent`, `emit_usage_event`, `estimate_cost_usd`, `usage_user_id`, `usage_novel_id` (Task 2).
- Produces: capability-carrying agent runs now emit one `UsageEvent` per model request. Registry path (Task 4) is disjoint.

- [ ] **Step 1: Write failing test**

Test strategy: instantiate `NarrareObservability()`, stub a `ctx` object exposing `usage` (an object with `input_tokens`/`output_tokens`/`total_tokens`/`details`) and `deps=None`, call `after_model_request` with a minimal `ModelResponse` (build via `pydantic_ai.messages.ModelResponse(parts=[])`) and any `ModelRequestContext`; register a `RecordingSink` (pattern from Task 2 — copy the class, do not import from another test module); assert one event with correct token/cache/`unknown` intent/provider fallbacks; a second test with a deps object carrying `model_config` asserts provider/model are taken from it; a third test sets ContextVars and asserts attribution lands on the event; a fourth test registers an exploding sink and asserts `after_model_request` still returns the response.

- [ ] **Step 2: Run test — expect FAIL** (`attribute/addition missing` — no emission yet).

- [ ] **Step 3: Implement**

In `after_model_request`, after the existing `record_success(...)` / cache-metrics block and before `return response`, add:

```python
from narrare_core.llm.usage_events import (  # at module top
    UsageEvent, emit_usage_event, estimate_cost_usd, usage_novel_id, usage_user_id,
)

await emit_usage_event(
    UsageEvent(
        timestamp=datetime.now(timezone.utc),
        intent=self._intent or "unknown",
        provider=self._provider_name or "unknown",
        model_id=self._model_id or "unknown",
        tokens_in=token_usage.prompt_tokens,
        tokens_out=token_usage.completion_tokens,
        cache_read_tokens=cache_read,
        cache_creation_tokens=cache_creation,
        duration_seconds=elapsed,
        cost_usd=estimate_cost_usd(
            self._provider_name or "unknown", self._model_id or "unknown",
            tokens_in=token_usage.prompt_tokens, tokens_out=token_usage.completion_tokens,
            cache_read_tokens=cache_read, cache_creation_tokens=cache_creation,
        ),
        user_id=usage_user_id.get(),
        novel_id=usage_novel_id.get(),
    )
)
```

(`token_usage` and `cache_read`/`cache_creation` already exist in scope — reuse, do not re-extract. Monkeypatch `estimate_cost_usd` at the capability module's import location in tests to avoid network.)

- [ ] **Step 4: Run tests — expect PASS** (`uv run pytest tests/unit/core/agents/capabilities -v`; also re-run the full capability suite).

- [ ] **Step 5: Commit**

```bash
git add packages/core/narrare_core/agents/capabilities/observability.py tests/unit/core/agents/capabilities/test_observability_usage_events.py
git commit -m "feat(core): observability capability emits usage events"
```

---

### Task 3b: Core — capability intent wiring (class-identity, gate follow-up)

**Files:**
- Modify: `packages/core/narrare_core/agents/capabilities/observability.py`
- Modify: `packages/core/narrare_core/agents/base.py`
- Test: `tests/unit/core/agents/test_observability_intent.py` (create)

**Interfaces:**
- Consumes: Task 3's emission (unchanged semantics).
- Produces: capability-path `UsageEvent.intent` (and the existing `record_success`/`record_failure`/`record_cache_usage` metric labels — same source by construction) carries an agent-class slug instead of `"unknown"`.

Mechanism (Architecture ruling 2026-10-05, Option A):
1. `observability.py`: constructor field `intent: str = ""` (replaces the dead per-run-only `_intent`); `for_run` builds the per-run copy as `NarrareObservability(intent=self.intent)` (template state preserved; `_start_time` etc. stay per-run); hooks read `self.intent or "unknown"`.
2. `base.py`: `observability_intent: ClassVar[str | None] = None` override point + a ~8-LOC helper deriving a snake_case slug from `type(self).__name__` with a trailing `"Agent"` suffix stripped (`ChapterSummaryAgent` → `"chapter_summary"`); the `NarrareObservability(...)` construction at base.py:143 passes `intent=self.observability_intent or _derived_slug`.
3. Tests: TestModel-driven agent run emits the derived slug; a `ClassVar` override wins; bare `NarrareObservability()` construction falls back to `"unknown"`; `for_run` preserves the template intent.
4. Vocabulary note (corrected 2026-10-05 after Task 3b review): capability path emits
   agent-class slugs (`chapter_summary`), registry path emits `LLMIntent` values — the
   populations of CALLS are disjoint (exactly-once per request), but 5 slug keys equal
   `LLMIntent` values (`chat`, `consistency`, `consistency_triage`, `kb_improve`,
   `dialogue_coach`) and merge into one bucket each — same-feature merge, desirable;
   the FE intent→label map (Task 15) treats both key families as ONE namespace.
5. If updating pre-existing tests that assert `intent="unknown"` in metrics pushes the change beyond 3 files, STOP and report PACKAGE_TOO_LARGE (coordinator re-slices).

TDD per house standard; commit: `feat(core): capability path carries class-identity intent`.

### Task 3c: Core — capability provider/model attribution (gate follow-up)

**Files:**
- Modify: `packages/core/narrare_core/agents/capabilities/observability.py`
- Modify: `packages/core/narrare_core/agents/base.py`
- Test: `tests/unit/core/agents/test_observability_model_attribution.py` (create)

**Interfaces:**
- Consumes: Task 3b's template-state preservation.
- Produces: capability-path `UsageEvent.provider`/`model_id` (and metric labels) carry real values for all agents, not just WritingDeps-family.

Mechanism: `NarrareAgent.__init__` receives the pydantic-ai `model` object — derive `model_name` (and provider via pydantic-ai's `provider:model_name` parsing; see installed `pydantic_ai.models.__init__` ~:1332 and ~:1601-1604; handle `InstrumentedModel`/wrapper classes by unwrapping; `TestModel` yields its own name — acceptable in tests). Pass `provider_name`/`model_id` onto the capability template like Task 3b's intent; `for_run` keeps the existing deps-based `model_config` extraction as the PREFERRED source (resolved config is more accurate) with the template values as fallback (`deps-extracted or template-value or "unknown"`). Tests: real-model-name attribution without deps; WritingDeps-family still prefers `model_config`; wrapper unwrapping. Same PACKAGE_TOO_LARGE rule. TDD; commit: `feat(core): capability path model/provider attribution`.

### Task 4: Core — registry emission (`ModelRegistry.run`/`stream`)

**Files:**
- Modify: `packages/core/narrare_core/llm/gateway.py`
- Test: `tests/unit/core/llm/test_gateway_usage_events.py` (create)

**Interfaces:**
- Consumes: Task 2 seam.
- Produces: capability-less ephemeral agent runs (9 production call sites: name generation, KB consistency, inline suggest, WS writing turns, interview drafts, legacy WritingPipeline) are captured. Exactly-once with Task 3 (disjoint populations).

- [ ] **Step 1: Write failing test**

Use `TestModel` (pydantic-ai) with a registry-test pattern — mirror the existing gateway tests (`grep -l "ModelRegistry" tests/unit/core/llm/` and copy their fixture approach for registry construction + monkeypatched `get_model`). Register a `RecordingSink`; call `registry.run(intent=LLMIntent.GENERATE_NAMES, prompt="x", config=<resolved test config>)`; assert exactly one event with `intent="generate_names"` (the intent's value), provider/model from the config, tokens from the TestModel usage; second test: monkeypatch `registry.get_model` to raise nothing but make the sink explode and assert `run` still returns output. Third test for `stream()`: drive a small streamed run and assert one event after the final chunk.

- [ ] **Step 2: Run — expect FAIL** (no event recorded).

- [ ] **Step 3: Implement**

Add a small module-private helper in `gateway.py` (RULE-04: keep `run`/`stream` lean):

```python
async def _emit_usage_event(  # module level in gateway.py
    *,
    intent: LLMIntent,
    config: ResolvedModelConfig,
    usage: Any,           # pydantic_ai RunUsage
    duration_seconds: float,
) -> None:
    details = getattr(usage, "details", None)
    details = details if isinstance(details, dict) else {}
    cache_read = int(details.get("cache_read_input_tokens", 0) or 0)
    cache_creation = int(details.get("cache_creation_input_tokens", 0) or 0)
    tokens_in = usage.input_tokens or 0
    tokens_out = usage.output_tokens or 0
    await emit_usage_event(
        UsageEvent(
            timestamp=datetime.now(timezone.utc),
            intent=intent.value,
            provider=config.provider_name,
            model_id=config.model_id,
            tokens_in=tokens_in, tokens_out=tokens_out,
            cache_read_tokens=cache_read, cache_creation_tokens=cache_creation,
            duration_seconds=duration_seconds,
            cost_usd=estimate_cost_usd(
                config.provider_name, config.model_id,
                tokens_in=tokens_in, tokens_out=tokens_out,
                cache_read_tokens=cache_read, cache_creation_tokens=cache_creation,
            ),
            user_id=usage_user_id.get(), novel_id=usage_novel_id.get(),
        )
    )
```

Call `await _emit_usage_event(intent=intent, config=config, usage=_usage, duration_seconds=elapsed)` in `run()` right after the `TokenUsage(...)` construction (~line 217, before the `logger.info`), and the `stream()` equivalent after its `TokenUsage(...)` (~line 290, `usage=stream_result.usage`).

- [ ] **Step 4: Run tests — expect PASS** (`uv run pytest tests/unit/core/llm/test_gateway_usage_events.py tests/unit/core/llm -v` — no gateway regression).

- [ ] **Step 5: Commit**

```bash
git add packages/core/narrare_core/llm/gateway.py tests/unit/core/llm/test_gateway_usage_events.py
git commit -m "feat(core): model registry emits usage events (dual seam, ADR-093)"
```

---

### Task 5: API — `UsageRecordRow` + Alembic 0043

**Files:**
- Create: `apps/api/narrare/analytics/models.py`
- Create: `apps/api/alembic/versions/0043_usage_records.py`
- Modify: `apps/api/narrare/_app/models.py` (import the new model so metadata registers — mirror how notes/models is imported)

**Interfaces:**
- Produces (used by Tasks 6, 8): `UsageRecordRow` mapped to table `usage_records` with columns exactly per spec §3.4: `id UUID PK`, `user_id UUID FK users.id ON DELETE RESTRICT NOT NULL`, `novel_id UUID FK novels.id ON DELETE SET NULL NULL`, `intent TEXT NOT NULL`, `provider TEXT NOT NULL`, `model_id TEXT NOT NULL`, `tokens_in INTEGER NOT NULL`, `tokens_out INTEGER NOT NULL`, `cache_read_tokens INTEGER NOT NULL DEFAULT 0`, `cache_creation_tokens INTEGER NOT NULL DEFAULT 0`, `duration_ms INTEGER NOT NULL`, `cost_usd NUMERIC(12,6) NULL`, `created_at TIMESTAMPTZ NOT NULL`; indices `(user_id, created_at)` and `(novel_id)`.

- [ ] **Step 1: Write the model + migration**

Mirror `apps/api/narrare/notes/models.py` for imports/Base/id style (read it first). Migration: read `0042_chat_project_optional.py` for its `revision` id and use it as `down_revision`; write `upgrade()` with `op.create_table(...)` + `op.create_index(...)`×2 and `downgrade()` dropping them. Column types: `sa.UUID()`, `sa.Text()`, `sa.Integer()`, `sa.Numeric(12, 6)`, `sa.DateTime(timezone=True)`.

- [ ] **Step 2: Verify migration integrity**

Run: `uv run pytest tests/integration -k "migration or round_trip" -v` (locate the exact schema round-trip suite first: `grep -rl "0042" tests/integration | head` — if the suite enumerates migrations, add 0043 the same way; that list edit counts within this task's file budget only if it is a 3rd file — otherwise STOP and report PACKAGE_TOO_LARGE with the file name so the coordinator re-slices).

- [ ] **Step 3: Verify model metadata**

Run: `uv run python -c "from narrare._app.models import *; from sqlalchemy import MetaData; import narrare.analytics.models as m; assert m.UsageRecordRow.__tablename__ == 'usage_records'"` (adjust import path to the actual package layout).

- [ ] **Step 4: Commit**

```bash
git add apps/api/narrare/analytics/models.py apps/api/alembic/versions/0043_usage_records.py apps/api/narrare/_app/models.py
git commit -m "feat(api): usage_records table + Alembic 0043"
```

---

### Task 6: API — `UsageRecordRepository`

**Files:**
- Create: `apps/api/narrare/analytics/repository.py`
- Test: `tests/unit/api/analytics/test_usage_record_repository.py` (create)

**Interfaces:**
- Consumes: `UsageRecordRow` (Task 5). Mirror `apps/api/narrare/notes/repository.py` for session/BaseRepository conventions (read it first).
- Produces (used by Tasks 7, 8):

```python
@dataclass(frozen=True)
class UsageAggRow:
    month: date            # first day of the bucket month
    intent: str
    provider: str
    model_id: str
    calls: int
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal      # SUM over priced rows (0 when all unpriced)
    unpriced_calls: int

class UsageRecordRepository:
    def __init__(self, session: AsyncSession) -> None: ...
    async def insert(self, row: UsageRecordRow) -> None: ...
    async def aggregate_range(self, user_id: UUID, start: datetime, end: datetime) -> list[UsageAggRow]: ...
```

`aggregate_range` groups by `(date_trunc('month', created_at), intent, provider, model_id)` with `count(*)`, `sum(tokens_in)`, `sum(tokens_out)`, `sum(cost_usd)`, `count(*) FILTER (WHERE cost_usd IS NULL)`; rows ordered by month, then cost desc. `[start, end)` semantics.

- [ ] **Step 1: Write failing tests**

Mirror the notes-repository test setup (fake/in-memory session pattern the project uses for repository unit tests — check `tests/unit/api/notes/` for the established fake-session or real-session fixture). Seed rows across two months, two intents, one unpriced; assert bucketing, sums, `unpriced_calls`, and `[start, end)` exclusivity. Include an attribution-isolation test (second user's rows invisible).

- [ ] **Step 2: Run — expect FAIL.** **Step 3: Implement** (single `select` with `func.date_trunc`, `func.sum`, `func.count`; `group_by`; convert `Decimal`/`date` results into `UsageAggRow`).

- [ ] **Step 4: Run — expect PASS** (`uv run pytest tests/unit/api/analytics -v`).

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/analytics/repository.py tests/unit/api/analytics/test_usage_record_repository.py
git commit -m "feat(api): usage record repository with month aggregation"
```

---

### Task 7: API — contracts + `CostQueryService`

**Files:**
- Create: `apps/api/narrare/analytics/contracts.py`
- Create: `apps/api/narrare/analytics/service.py`
- Test: `tests/unit/api/analytics/test_cost_query_service.py` (create)

**Interfaces:**
- Consumes: `UsageRecordRepository.aggregate_range` (Task 6).
- Produces (used by Task 10):

```python
# contracts.py
class CostTotals(BaseModel): calls: int; tokens_in: int; tokens_out: int; cost_usd: float; unpriced_calls: int
class CostIntentRow(BaseModel): intent: str; calls: int; cost_usd: float; unpriced_calls: int
class CostModelRow(BaseModel): provider: str; model_id: str; calls: int; cost_usd: float; unpriced_calls: int
class CostTrendPoint(BaseModel): month: str; cost_usd: float
class CostMonthReport(BaseModel):
    month: str
    totals: CostTotals
    by_intent: list[CostIntentRow]
    by_model: list[CostModelRow]
    trend: list[CostTrendPoint]      # 6 months ending with `month`, oldest first

class CostQueryServiceProtocol(Protocol):
    async def month_report(self, user_id: UUID, month: str | None) -> CostMonthReport: ...

# service.py
class InvalidMonthError(ValueError): ...
class CostQueryService:            # implements the protocol
    def __init__(self, repo: UsageRecordRepository) -> None: ...
    async def month_report(self, user_id: UUID, month: str | None) -> CostMonthReport: ...
```

Semantics: `month is None` → current server-local month. `month` format `^\d{4}-(0[1-9]|1[0-2])$` else `InvalidMonthError`. One `aggregate_range` call spanning the 6-month window; Python-side bucketing into totals/by_intent/by_model/trend; `cost_usd` as `float(Decimal)` sums; `by_intent`/`by_model` sorted by cost desc.

- [ ] **Step 1: Write failing tests** — fake repository returning canned `UsageAggRow`s: default-month resolution (freeze time or compute expected), invalid month raises `InvalidMonthError` (`"2026-13"`, `"abc"`), bucketing correctness (two intents merge in `by_intent`, same model different provider stay separate rows in `by_model`), trend has 6 entries oldest-first with zero months included.
- [ ] **Step 2: Run — expect FAIL.** **Step 3: Implement contracts + service.**
- [ ] **Step 4: Run — expect PASS** (`uv run pytest tests/unit/api/analytics -v`).

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/analytics/contracts.py apps/api/narrare/analytics/service.py tests/unit/api/analytics/test_cost_query_service.py
git commit -m "feat(api): cost query contracts + service"
```

---

### Task 8: API — `SqlUsageEventSink`

**Files:**
- Create: `apps/api/narrare/analytics/usage_sink.py`
- Test: `tests/unit/api/analytics/test_usage_sink.py` (create)

**Interfaces:**
- Consumes: `UsageEvent` + `UsageEventSink` protocol (Task 2, Core), `UsageRecordRepository.insert` + `UsageRecordRow` (Tasks 5/6).
- Produces (used by Task 11):

```python
class SqlUsageEventSink:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None: ...
    async def record(self, event: UsageEvent) -> None: ...
```

Behavior: `user_id is None` ⇒ skip with `logger.debug("usage_event_skipped_unattributed")`; otherwise build `UsageRecordRow` (`duration_ms = round(event.duration_seconds * 1000)`; `cost_usd = Decimal(str(event.cost_usd))` when not None; `created_at = event.timestamp` — NOT DB now()); open `async with self._session_factory() as session:` → `UsageRecordRepository(session).insert(row)` → `await session.commit()`. The sink does not catch its own exceptions (the Core emitter guard is the enforcement point).

- [ ] **Step 1: Write failing tests** — fake session factory + fake repository (monkeypatch `UsageRecordRepository` in the sink module): None-user skip (no session opened), field mapping incl. seconds→ms + Decimal conversion + `created_at` from event, commit called.
- [ ] **Step 2: Run — expect FAIL.** **Step 3: Implement.**
- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/analytics/usage_sink.py tests/unit/api/analytics/test_usage_sink.py
git commit -m "feat(api): SQL usage-event sink (own session, RULE-08 delegation)"
```

---

### Task 9: API — attribution middleware + auth-dependency user binding

**Files:**
- Create: `apps/api/narrare/analytics/middleware.py`
- Modify: `apps/api/narrare/_app/dependencies_auth.py` (the canonical current-user dependency — locate with `grep -n "def get_current_user" apps/api/narrare/_app/dependencies_auth.py`)
- Test: `tests/unit/api/analytics/test_usage_attribution.py` (create)

**Interfaces:**
- Consumes: `usage_novel_id`, `usage_user_id` (Task 2).
- Produces:

```python
class UsageAttributionMiddleware:
    """Pure ASGI (http scope only): sets usage_novel_id from /novels/{uuid} path prefix."""
    def __init__(self, app: ASGIApp) -> None: ...
    async def __call__(self, scope, receive, send) -> None: ...
```

Regex: `^/api/v1/novels/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?:/|$)` — match ⇒ set var to the UUID; no match ⇒ set `None`; non-http scopes pass through untouched (WS attribution is Task 12). In `get_current_user` (and only there — it is the single canonical auth dependency), add after user resolution: `usage_user_id.set(user.id)` (import from `narrare_core.llm.usage_events`).

- [ ] **Step 1: Write failing tests** — middleware: novel route path sets var, non-novel path sets None, malformed UUID ⇒ None, websocket scope untouched; auth dep: monkeypatched user store → assert `usage_user_id` set after dependency resolves (mirror existing auth-dependency tests in `tests/unit/api/`).
- [ ] **Step 2: Run — expect FAIL.** **Step 3: Implement both.**
- [ ] **Step 4: Run — expect PASS** + `uv run pytest tests/unit/api -k auth -v` (no auth regression).

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/analytics/middleware.py apps/api/narrare/_app/dependencies_auth.py tests/unit/api/analytics/test_usage_attribution.py
git commit -m "feat(api): usage attribution middleware + auth user binding"
```

---

### Task 10: API — router + dependencies

**Files:**
- Create: `apps/api/narrare/analytics/router.py`
- Create: `apps/api/narrare/analytics/dependencies.py`
- Test: `tests/unit/api/analytics/test_costs_router.py` (create)

**Interfaces:**
- Consumes: `CostQueryService`/`CostMonthReport` (Task 7), `get_current_user` (existing), repository session dependency pattern from a sibling module (read `apps/api/narrare/notes/dependencies.py`).
- Produces: `router = APIRouter(prefix="/analytics", tags=["analytics"])` with

```python
@router.get("/costs", response_model=CostMonthReport)
async def get_monthly_costs(
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    user: User = Depends(get_current_user),
    service: CostQueryServiceProtocol = Depends(get_cost_query_service),
) -> CostMonthReport:
    return await service.month_report(user.id, month)
```

and `dependencies.py` with `get_cost_query_service()` building repo+service from the request session (mirror notes). Router delegates immediately (RULE-06); the Query pattern yields FastAPI's 422 for bad months; the service still validates defensively.

- [ ] **Step 1: Write failing tests** — mirror the notes-router test harness (app fixture, auth override or token fixture): 200 with default month, 200 with explicit month passing through to a fake service, 422 for `"2026-13"`/`"garbage"`, 401 unauthenticated.
- [ ] **Step 2: Run — expect FAIL.** **Step 3: Implement.**
- [ ] **Step 4: Run — expect PASS** (`uv run pytest tests/unit/api/analytics -v`).

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/analytics/router.py apps/api/narrare/analytics/dependencies.py tests/unit/api/analytics/test_costs_router.py
git commit -m "feat(api): GET /analytics/costs endpoint"
```

---

### Task 11: API — app wiring (router, middleware, sink registration)

**Files:**
- Modify: `apps/api/narrare/_app/main.py` (include the analytics router; `add_middleware(UsageAttributionMiddleware)` — last-added runs outermost, so add it AFTER the existing middleware adds to wrap everything)
- Modify: `apps/api/narrare/_app/lifespan.py` (on startup: `set_usage_event_sink(SqlUsageEventSink(<sessionmaker>))`; on shutdown: `set_usage_event_sink(None)`)
- Test: `tests/unit/api/test_analytics_wiring.py` (create)

**Interfaces:**
- Consumes: Tasks 8/9/10 products; the sessionmaker export in `apps/api/narrare/_app/database.py` (locate the exact name with `grep -n "sessionmaker\|SessionMaker\|session_factory" apps/api/narrare/_app/database.py`).
- Produces: fully wired runtime — every LLM call lands in `usage_records`; `GET /api/v1/analytics/costs` reachable.

- [ ] **Step 1: Write failing test** — build the app (mirror the app-construction fixture used by other wiring tests, `grep -rl "create_app\|app_factory" tests/unit/api | head -3`): assert `/api/v1/analytics/costs` appears in `app.routes`; assert `get_usage_event_sink()` is a `SqlUsageEventSink` after lifespan startup (use the project's lifespan test pattern) and `None` after shutdown.
- [ ] **Step 2: Run — expect FAIL.** **Step 3: Implement wiring in both files.**
- [ ] **Step 4: Run — expect PASS** + targeted smoke: `uv run pytest tests/unit/api -k "wiring or lifespan" -v`.

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/_app/main.py apps/api/narrare/_app/lifespan.py tests/unit/api/test_analytics_wiring.py
git commit -m "feat(api): wire usage sink, attribution middleware, costs router"
```

---

### Task 12: API — WS session bootstrap attribution

**Files:**
- Modify: `apps/api/narrare/writing/ws_handler.py` (at the `WritingSessionContext` construction, ~lines 113–119 — post ticket-validation where `user_id` is known)
- Test: `tests/unit/api/writing/test_ws_usage_attribution.py` (create)

**Interfaces:**
- Consumes: `set_usage_context` (Task 2).
- Produces: WS writing turns (and the background dispatch they spawn) carry `user_id` + `novel_id` attribution into usage events.

- [ ] **Step 1: Write failing test** — mirror the existing ws_handler test fixtures (`grep -rl "ws_handler" tests/unit/api/writing | head -3`): drive a session bootstrap with a validated ticket; assert `usage_user_id.get() == <user>` and `usage_novel_id.get() == <novel>` inside a stubbed turn handler.
- [ ] **Step 2: Run — expect FAIL.** **Step 3: Implement** — one call after context construction: `set_usage_context(user_id=user_id, novel_id=novel_id)` (adapt to the exact local variable names).
- [ ] **Step 4: Run — expect PASS** + `uv run pytest tests/unit/api/writing -k ws -v` (no WS regression).

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/writing/ws_handler.py tests/unit/api/writing/test_ws_usage_attribution.py
git commit -m "feat(api): WS writing sessions set usage attribution"
```

---

### Task 13: FE — `useAnalyticsCosts` hook + types

**Files:**
- Create: `packages/web/lib/hooks/useAnalyticsCosts.ts`
- Test: `packages/web/lib/hooks/useAnalyticsCosts.test.ts` (create)

**Interfaces:**
- Consumes: the authenticated API client helper used by sibling hooks (`grep -rn "queryKey" packages/web/lib/hooks/useBandSummary.ts` or any sibling to find the fetch wrapper + its import name).
- Produces (used by Task 14):

```ts
export interface CostTotals { calls: number; tokens_in: number; tokens_out: number; cost_usd: number; unpriced_calls: number }
export interface CostIntentRow { intent: string; calls: number; cost_usd: number; unpriced_calls: number }
export interface CostModelRow { provider: string; model_id: string; calls: number; cost_usd: number; unpriced_calls: number }
export interface CostTrendPoint { month: string; cost_usd: number }
export interface CostMonthReport { month: string; totals: CostTotals; by_intent: CostIntentRow[]; by_model: CostModelRow[]; trend: CostTrendPoint[] }

export function useAnalyticsCosts(month: string): UseQueryResult<CostMonthReport> // queryKey ["analytics","costs",month], GET /api/v1/analytics/costs?month=..., keepPreviousData
```

- [ ] **Step 1: Write failing test** — mirror a sibling hook test (msw handler for `/api/v1/analytics/costs`): returns report for a month; key changes with month. **Step 2: Run — FAIL** (`pnpm vitest run lib/hooks/useAnalyticsCosts.test.ts`). **Step 3: Implement.** **Step 4: Run — PASS.**
- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/hooks/useAnalyticsCosts.ts packages/web/lib/hooks/useAnalyticsCosts.test.ts
git commit -m "feat(web): useAnalyticsCosts hook"
```

---

### Task 14: FE — `AnalyticsCostsPanel`

**Files:**
- Create: `packages/web/components/analytics/AnalyticsCostsPanel.tsx`
- Test: `packages/web/components/analytics/AnalyticsCostsPanel.test.tsx` (create)

**Interfaces:**
- Consumes: `useAnalyticsCosts` (Task 13), `useTranslations("analytics.costs")` (keys land in Task 15 — component references them now; tests mock `next-intl` via the project's established test setup), Recharts `BarChart`/`Bar`/`ResponsiveContainer`/`XAxis`/`YAxis`/`Tooltip` (pattern: `components/studio/analysis/SentimentChart.tsx`).
- Produces: `<AnalyticsCostsPanel />` — self-contained month selector (prev/next buttons + `month` label in `YYYY-MM`), totals card (calls, tokens in/out, cost USD via the project's currency/number formatter, unpriced badge when `unpriced_calls > 0`), by-feature table (intent keys mapped `analytics.costs.intent.<intent>` with raw-key fallback), by-model table (`provider / model_id`), 6-month Recharts bar trend.

- [ ] **Step 1: Write failing tests** — render with a mocked query result (project's established wrapper): month label renders, prev/next shift the month, unpriced badge appears iff `> 0`, tables render rows, trend bars render (`ResponsiveContainer` mocked per SentimentChart test pattern).
- [ ] **Step 2: Run — FAIL.** **Step 3: Implement.** **Step 4: Run — PASS** (`pnpm vitest run components/analytics`).
- [ ] **Step 5: Commit**

```bash
git add packages/web/components/analytics/AnalyticsCostsPanel.tsx packages/web/components/analytics/AnalyticsCostsPanel.test.tsx
git commit -m "feat(web): analytics costs panel"
```

---

### Task 15: FE — i18n messages (`analytics` namespace)

**Files:**
- Create: `packages/i18n/messages/en/analytics.json`
- Create: `packages/i18n/messages/de/analytics.json`
- Create: `packages/i18n/messages/fr/analytics.json`

**Interfaces:**
- Consumes: Task 14's key usage.
- Produces: namespace `analytics` with `costs.*` (title, tab label, totals labels, table headers, month navigation aria-labels, unpriced badge, empty state) and `intent.<key>` entries for the shipped intents (enumerate via `grep -rn "value" packages/core/narrare_core/llm/intents/_enums.py` and mirror the snake_case keys). English source of truth:

```json
{
  "costs": {
    "title": "AI Costs",
    "monthLabel": "Month",
    "prevMonth": "Previous month",
    "nextMonth": "Next month",
    "calls": "AI calls",
    "tokensIn": "Tokens in",
    "tokensOut": "Tokens out",
    "cost": "Estimated cost (USD)",
    "unpriced": "{count} unpriced",
    "byFeature": "By feature",
    "byModel": "By model",
    "feature": "Feature",
    "model": "Model",
    "trend": "Last 6 months",
    "empty": "No AI usage recorded for this month."
  },
  "intent": { "draft": "Draft", "...": "— one entry per shipped intent —" }
}
```

DE/FR: idiomatic translations, informal register (du/tu — matches Q-013 convention). Do not translate the `intent.*` KEYS, only values.

- [ ] **Step 1: Write the three files** (identical key sets — verify with `jq -S 'keys' …` equality or the repo's i18n completeness test: `pnpm vitest run -t i18n` if present). **Step 2: Run the i18n/completeness gate** used by the repo (`grep -rn "i18n" packages/web/package.json` scripts). **Step 3: Commit**

```bash
git add packages/i18n/messages/en/analytics.json packages/i18n/messages/de/analytics.json packages/i18n/messages/fr/analytics.json
git commit -m "feat(i18n): analytics namespace (en/de/fr)"
```

---

### Task 16: FE — `/analytics` page + navigation

**Files:**
- Create: `packages/web/app/(studio)/analytics/page.tsx`
- Modify: the studio sidebar/nav component that holds the Scratchpad entry (locate: `grep -rn "scratchpad" packages/web/components --include=*.tsx -l | head -3`)
- Test: `packages/web/app/(studio)/analytics/page.test.tsx` (create)

**Interfaces:**
- Consumes: `AnalyticsCostsPanel` (Task 14).
- Produces: `/analytics` route (studio auth layout, like `/scratchpad`) rendering a tab bar with one tab (AI Costs → `AnalyticsCostsPanel`), plus the nav entry with icon + `analytics.costs.title` label between existing entries.

- [ ] **Step 1: Write failing test** — page renders the panel; nav (unit-level, per the existing nav test pattern) includes the analytics link.
- [ ] **Step 2: Run — FAIL.** **Step 3: Implement** — mirror `app/(studio)/scratchpad/page.tsx` structure. **Step 4: Run — PASS** (`pnpm vitest run app/\(studio\)/analytics` + nav tests).
- [ ] **Step 5: Commit**

```bash
git add "packages/web/app/(studio)/analytics/page.tsx" packages/web/components/<nav-file>.tsx "packages/web/app/(studio)/analytics/page.test.tsx"
git commit -m "feat(web): /analytics page + navigation"
```

---

### Task 17: Docs closure — feature file + feature index

**Files:**
- Modify: `docs/features/analytics/STATS-002-cost-tracking.md` (frontmatter: `service: analytics/service.py`, `contract: analytics/contracts.py#CostQueryServiceProtocol`, `router: analytics/router.py`; status → `in-progress` — v1 slices done, deferred slices keep it from `stable`; body: reflect the v1 design, known-untracked list, deferred slices)
- Modify: `docs/features/INDEX.md` (Analytics & Cost row note: v1 implemented `<date>`, ADR-093, deferred: budgets/export/CLI/embeddings)

**Steps:**
- [ ] **Step 1: Update both files** (English; follow the INDEX note conventions used by IO-002/SETUP-003).
- [ ] **Step 2: Doc gate** — run the docs checks the repo enforces (`just check-architecture` includes doc drift).
- [ ] **Step 3: Commit** `git commit -m "docs(features): STATS-002 v1 implemented — analytics module"` (add the two files).

---

### Task 18: Closure — ADR flip, state, full gate

**Files:**
- Modify: `docs/architecture/decisions/ADR-093-usage-event-sink-cost-persistence.md` (status → ✅ Implemented + completion note)
- Modify: `docs/architecture/decisions/INDEX.md` (ADR-093 row → ✅)
- Modify: `docs/_shared/CURRENT_STATE.md` (new dated entry: STATS-002 v1, commit range, deferred slices)

**Steps:**
- [ ] **Step 1: Full local gate** — `just verify` (backend + frontend + pyright + ruff) and `just check-architecture`; STOP on any failure, fix root cause in the owning layer before proceeding.
- [ ] **Step 2: Update the three docs files.**
- [ ] **Step 3: Commit** `git commit -m "docs: close STATS-002 v1 — ADR-093 implemented, state updated"`.

---

## Execution Notes

- **Review gates:** every task goes through the per-task review gate (subagent-driven-development); the reviewer is read-only.
- **Regression-first:** all tasks are new-feature TDD (test first); Tasks 3/4/9/11/12 additionally must not regress their touched suites.
- **Out of scope (do not build):** budgets, export, CLI, embeddings, read-time re-pricing (spec §9).
