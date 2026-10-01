# Pydantic-AI 2.52 Upgrade & Feature Adoption — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `pydantic-ai-slim` 2.35.3 → 2.52.0 (with `pydantic-evals` in lockstep), verify the security/compat surface against our code, and pilot three pydantic-ai-2.5x capabilities behind opt-in flags: OTel content-leak regression (GHSA-4x9p-g9wm-8q7f), z.AI `glm-5.3-flash` registration, SelectModel dynamic tier routing, DecisionModel-pattern consistency triage, and a local multi-vector rerank tier.

**Architecture:** The pin bump is a family jump (`pydantic-ai-slim` + `pydantic-evals`, resolver-unresolvable when split — PR #194 lesson). All new LLM-facing code goes through the existing Gateway/ModelRegistry (RULE-01b): SelectModel wiring lives in `core/llm/`, the triage agent in `core/agents/`, the rerank stage in `core/embeddings/`. Every feature is additive and default-off (env flag or optional extra) so the upgrade commit alone is behavior-preserving.

**Tech Stack:** Python 3.14 · pydantic-ai-slim 2.52.0 · pydantic-evals 2.52.0 · pydantic 2.13.5 (unchanged) · sentence-transformers ≥6.1,<7 (optional `embeddings` extra) · OpenTelemetry SDK · Pydantic Evals (ADR-032).

## Global Constraints

- Layer order per task: Architecture → Core → Backend → Frontend → Platform (Tests/CI) → Docs. Assigned layer is stated per task.
- Package sizing: ≤3 files changed / ≤250 new LOC per task (one documented exception: Task 9, atomicity rationale in the task).
- RULE-01b: no direct LLM imports outside `core/llm/`; `pydantic_ai.Agent` only in `core/agents/` (plus the registered `# narrare: allow-agent` exceptions).
- RULE-02/02a: prompts only via `core/prompts/` (PromptComposer cascade) or sanctioned dynamic `@agent.instructions` in `core/agents/` — no inline prompt strings in services.
- RULE-03: contract (Protocol) before implementation. RULE-04: modularize. RULE-06: routers delegate immediately. RULE-08: external libs confined to dedicated modules (`sentence_transformers` only in `core/embeddings/`).
- Regression-first: every behavior-changing task starts with a failing test.
- Exact version pins in `pyproject.toml` (project convention) — `pydantic-ai-slim[openai,anthropic,google,groq]==2.52.0`, `pydantic-evals==2.52.0`, `sentence-transformers>=6.1,<7`.
- Verification per task: named pytest subset; `just verify` at phase ends; `just check-architecture` (= `scripts/check_architecture.py`) for anything touching intents/prompts/boundaries; eval suites (ADR-032) as regression net for agent-behavior tasks.
- Git writes (add/commit/push) go through **NarrarePlatformSpecialist**; other layers hand over.
- Project language: English (source, comments, tests, docs).
- Frontend: no frontend tasks in this plan (all flags are env-level, no UI).

## Out of Scope

- **mem0 upgrade 2.0.18 → 2.2.1** — separate parallel work stream; only interacts with this plan via the shared `transformers` requirement (see Risks). Coordinate merges so `uv.lock` conflicts are resolved once.
- **TypeSafe / Jev** — deliberately NOT integrated (DecisionModel is the generic base; we adopt only its output-design patterns).
- **True calibrated probabilities** (logprobs-derived, custom DecisionModel subclass, "Weg B") — future ADR; this plan ships rubric-based classification only.
- Production wiring of the consistency triage beyond the eval pipeline (gated on pilot eval results — see Task 12 acceptance).
- pgvector schema/index changes, `SubAgents`/`inherit_tools` adoption (unused by us, verified in Task 3).

## User Decisions (2026-09-30, binding for all tasks)

1. **F3 escalation target** = `LLMIntent.ANALYSE` (confirmed) — resolved via the existing `ModelRoutingResolver` cascade; no new settings surface.
2. **ADR-089 escape hatch** = YES, documented (confirmed): ADR-089 pre-authorizes a minimal custom `Model` wrapper as the fallback if the installed 2.52 `SelectModel` API proves unsuitable for our Gateway boundary. F3 degrades to the wrapper instead of aborting.
3. **F5 rerank encoder** = specific checkpoint pinned (confirmed): ADR-090 (Task 13) records a concrete encoder checkpoint — candidate `lightonai/LateOn` from the ST v6 release benchmarks; final choice verified during Task 13's API check. Never rely on the sentence-transformers library default (drifts between releases; breaks eval comparability — contradicts our exact-pin philosophy).

## Motivation (facts, verified against upstream release notes)

| Version | What we get | Narrare impact |
|---|---|---|
| 2.37.0 | `glm-5.3-flash` support + z.AI non-standard `finish_reason` fix (PR #7685) | z.AI GLM is our primary cost-efficient provider (ADR-006, Q-005) — direct enabler for F2/F4 cheap-model work |
| 2.44.0 | 4 security fixes; **GHSA-4x9p-g9wm-8q7f**: OTel spans leaked exceptions, error statuses, instructions and output templates under `include_content=False` | We run OTel with `NARRARE_OTEL_INCLUDE_CONTENT` default-off in production (`apps/api/narrare/_app/telemetry.py` → `packages/core/narrare_core/agents/instrumentation.py`) — Task 4 adds the regression test |
| 2.46.0 | `LLMJudge`/`GEval` run on models without text output | Eval-harness robustness (ADR-032) |
| 2.50.0 | `ModelSelectionContext.messages`/`.prompt` improvements + `SelectModel` capability + `DecisionModel` base class | Enabler for F3 (SelectModel) and F4 (DecisionModel patterns) |
| 2.51.0 | Agent graph cached instead of rebuilt per `Agent.run()`; less RunContext copying; no task group for single-child fan-out | Free perf — we instantiate agents per request (NarrareAgent subclasses, WritingGraph); verified in Task 17 |
| 2.52.0 | Security fix GHSA-v36g-jcw9-x7cw (`web_fetch` DoS — we use no pydantic-ai web tools; advisory hygiene) + Anthropic `max_tokens` default 4096→16384 on Claude Sonnet 4.5+ | Walkthrough item in Task 3 |

## Key Code Facts (verified in repo, 2026-09-30 — do not re-research)

- Pin lives in `packages/core/pyproject.toml` line 10: `pydantic-ai-slim[openai,anthropic,google,groq]==2.35.3`. **`pydantic-evals==2.35.3` is separately pinned at root `pyproject.toml` line 29 — MUST move in lockstep** (family jump; split pins are resolver-unresolvable, PR #194).
- venv currently holds `pydantic_ai_slim-2.35.3`; after the bump run `uv sync --all-packages` (ADR-063: sync once, `--no-sync` afterwards in CI).
- Intent→model routing today (accurate mechanism, supersedes the stale TECH_STACK.md wording "MODEL_ROUTING in intents.py"): **advisory tier table** `INTENT_PROFILES` in `packages/core/narrare_core/llm/intent_profiles.py` + **user-config cascade** via `ModelRoutingResolver` Protocol (`core/llm/model_routing.py`), backend impl resolves per intent/user/project (ADR-086 lazy `ModelResolution` in `apps/api/narrare/_app/dependencies_services.py`).
- z.AI SSOT: `packages/core/narrare_core/llm/_providers/zai.py` (`register_model` list at EOF, `_ZAI_MODEL_PROFILE` already sets `supports_thinking=True` + `openai_chat_supports_max_completion_tokens=False` for ALL registered IDs — `glm-5.3-flash` inherits both) and `apps/api/narrare/setup/provider_service.py` (`_FALLBACK_MODELS[AIProvider.ZAI]`).
- `max_tokens` is sent to providers ONLY when `usage_limits.output_tokens_limit` is set (`packages/core/narrare_core/llm/_model_settings.py::build_runtime_model_settings`) — relevant to the 2.52 Anthropic default change.
- Consistency: `packages/core/narrare_core/agents/consistency_types.py` (`ConsistencyIssue.check_type/severity/confidence`), `consistency_agent.py` (ADR-035 output validator pattern), backend `apps/api/narrare/consistency/checker_service.py` + `consistency_orchestrator.py` (ADR-044 staged pipeline).
- Embeddings: `packages/core/narrare_core/embeddings/scoring.py` (`rank_candidates`, `compute_hybrid_score`, `ScoredCandidate`, `ScoringConfig`); search consumer `apps/api/narrare/embeddings/service.py::EmbeddingService.search` (lines ~157–195: pgvector search → ScoredCandidate list → `rank_candidates`); constructed in `apps/api/narrare/embeddings/dependencies.py` (+ 2 unrelated call sites that must stay unchanged). Search rows carry **no document text** (only embedding + usage metadata) → rerank needs a text fetcher.
- mem0 local embedding Tier 3 (`all-MiniLM-L6-v2` via mem0's "huggingface" provider): `packages/core/narrare_core/memory/embedding_cascade.py` — sentence-transformers is currently ONLY consumed indirectly through mem0; no direct import anywhere.
- Eval harness (ADR-032): `evals/runner.py` CLI (`uv run --all-packages python -m evals run --suite <name> --mode smoke|runtime`), runtime tasks in `evals/tasks/runtime.py` (env: `NARRARE_EVAL_PROVIDER/MODEL/API_KEY/BASE_URL`), suite `rewrite_selection` (dataset `evals/datasets/rewrite_selection.py`) and `consistency_staged` (task `evals/tasks/consistency_runtime.py`).
- Cost estimation uses our own models.dev fetcher (`packages/core/narrare_core/llm/cost_rates.py`, 24h TTL) — NOT `pydantic_ai.prices` (relevant to F6 verdict).
- No repo usage of `SubAgents`, `inherit_tools`, `DeferredToolResults`, `UserPromptPart` (verified by grep 2026-09-30 — re-verified in Task 3).
- Next free ADR numbers: **ADR-089, ADR-090** (ADR-087, ADR-088 exist in `docs/architecture/decisions/INDEX.md`).
- `CHANGELOG.md` (repo root) is **auto-generated by Release Please — never hand-edit**; changelog coverage comes from Conventional Commits (doc-gate note in Task 18).
- Gates: `just test-unit`, `just verify` (= check + test-all), `just check-architecture`, `just test-unit-cov`. pytest defaults add `-x --timeout=30 -q`.

---

## Phase 0 — Branch & Prep

### Task 1: Branch and baseline

**Files:** none (git only)

**Assigned layer/subagent:** NarrarePlatformSpecialist · **Est. LOC:** 0

- [ ] **Step 1: Create the feature branch**

```bash
git checkout main
git pull --ff-only
git checkout -b feature/pydantic-ai-2.52-upgrade
```

- [ ] **Step 2: Confirm clean tree and record baseline**

```bash
git status --porcelain          # expect: empty
uv sync --all-packages
uv run --all-packages python -c "import pydantic_ai; print(pydantic_ai.__version__)"
# expect: 2.35.3
```

- [ ] **Step 3: Baseline test run (must be green before the bump)**

Run: `just test-unit`
Expected: all pass. If the baseline is red, STOP and report to the coordinator — do not upgrade on a red baseline.

- [ ] **Step 4: Commit** — none (prep only).

---

## Phase 1 — Version Bump + Compatibility Walkthrough

### Task 2: Family pin bump 2.35.3 → 2.52.0

**Files:**
- Modify: `packages/core/pyproject.toml:10`
- Modify: `pyproject.toml:29` (root, dev deps)
- Modify: `uv.lock` (generated)

**Interfaces:**
- Consumes: none.
- Produces: installed `pydantic_ai` 2.52.0 + `pydantic_evals` 2.52.0 for all later tasks.

**Assigned layer/subagent:** NarrareCoreSpecialist (pin) → NarrarePlatformSpecialist (commit) · **Est. LOC:** 2

- [ ] **Step 1: Edit both pins in the same change (family jump — never split)**

`packages/core/pyproject.toml` line 10:
```diff
-  "pydantic-ai-slim[openai,anthropic,google,groq]==2.35.3",
+  "pydantic-ai-slim[openai,anthropic,google,groq]==2.52.0",
```

Root `pyproject.toml` line 29:
```diff
-    "pydantic-evals==2.35.3",
+    "pydantic-evals==2.52.0",
```

- [ ] **Step 2: Sync and verify resolution**

```bash
uv sync --all-packages
uv run --all-packages python -c "import pydantic_ai, pydantic_evals; print(pydantic_ai.__version__)"
# expect: 2.52.0
uv pip check
# expect: no conflicts (this also proves pydantic 2.13.5 and the openai/anthropic/google/groq SDK ranges still resolve)
```

- [ ] **Step 3: Targeted smoke — the two suites closest to the pydantic-ai API surface**

Run: `uv run --all-packages pytest tests/unit/core/llm tests/unit/core/agents -q`
Expected: PASS. Any failure here is an upgrade regression → STOP, root-cause (≥2× why?), fix forward or report; never patch around.

- [ ] **Step 4: Commit (Platform)**

```bash
git add packages/core/pyproject.toml pyproject.toml uv.lock
git commit -m "chore(deps): bump pydantic-ai family 2.35.3 -> 2.52.0 (slim[openai,anthropic,google,groq] + pydantic-evals)"
```

**Acceptance criteria:** both pins at 2.52.0, `uv pip check` clean, `tests/unit/core/llm` + `tests/unit/core/agents` green, single commit containing pins + lockfile.

### Task 3: Compatibility walkthrough 2.35.3 → 2.52.0

**Files:**
- Modify: `tests/unit/core/llm/test_runtime_model_settings.py` (add one guard test)

**Interfaces:**
- Consumes: Task 2 install.
- Produces: documented verdict per compat item (recorded in the Task 18 CURRENT_STATE entry); guard test pinning our `max_tokens` omission behavior.

**Assigned layer/subagent:** NarrareCoreSpecialist · **Est. LOC:** ~25

Each item: run the check, note the verdict in the task's completion report. Only add code where a test pins behavior we depend on.

- [ ] **Step 1: v2.38 — one-off capabilities get default `id` + `combine` rule**

Our capabilities: `NarrareObservability`, `NarrareUniversalRules`, `NarrareMeta` (`packages/core/narrare_core/agents/capabilities/`) plus upstream `ToolSearch`/`Toolset` used by `ConsistencyAgent`.

```bash
uv run --all-packages pytest tests/unit/core/agents -q
uv run --all-packages python - <<'EOF'
import inspect
from pydantic_ai.capabilities import ToolSearch
sig = inspect.signature(ToolSearch.__init__)
print({n: p.default for n, p in sig.parameters.items() if n in {"id", "combine", "strategy"}})
EOF
```
Expected: tests green; printed defaults show `id`/`combine` exist. Verdict: our usage passes explicit args → behavior unchanged.

- [ ] **Step 2: v2.42 — `DeferredToolResults.approvals` validation**

```bash
rg -n "DeferredToolResults|tool_approval|approval" apps packages -g '*.py'
```
Expected: no matches (verified during planning; re-confirm). Verdict: not affected.

- [ ] **Step 3: v2.44 — security changes in instrumentation content handling**

Deferred to Task 4 (dedicated regression test). Verdict placeholder: "covered by Task 4".

- [ ] **Step 4: v2.47 — non-str/non-sequence `UserPromptPart.content` now raises; `None` output route renamed `None`**

```bash
rg -n "\.run\(\s*(dict\(|\{)" apps packages -g '*.py'        # dict content passed to agent.run
rg -n "output_type=None" packages/core -g '*.py'             # None output unions
```
Expected: no matches. All our `run(prompt=...)` call sites pass `str` (verified during planning). Verdict: not affected.

- [ ] **Step 5: v2.50 — `ModelSelectionContext.messages` ends with the request being routed**

Informational only — consumed by the ADR-089 design (Task 6). No check needed.

- [ ] **Step 6: v2.52 — Anthropic `max_tokens` default 4096→16384 (Sonnet 4.5+; model-max default with behind-the-scenes streaming)**

Read `packages/core/narrare_core/llm/_providers/anthropic.py` and confirm: we set NO profile-level `max_tokens` and `build_runtime_model_settings` only emits `max_tokens` when `usage_limits.output_tokens_limit` is set. Then add the guard test (red-first is impossible for an already-true invariant; this is a characterization test):

Append to `tests/unit/core/llm/test_runtime_model_settings.py`:

```python
def test_runtime_settings_omit_max_tokens_without_output_limit() -> None:
    """pydantic-ai 2.52 raises Anthropic's default max_tokens 4096->16384 (Sonnet 4.5+).

    Narrare deliberately does NOT pin max_tokens unless a UsageLimits
    output cap is configured — the provider default applies. This test
    pins that contract so the 2.52 default change stays a conscious,
    documented behavior (cost is guarded by UsageLimits, which DO set
    max_tokens when configured).
    """
    from narrare_core.llm._model_settings import build_runtime_model_settings
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.model_config import ResolvedModelConfig

    config = ResolvedModelConfig(
        provider_name="anthropic", model_id="claude-sonnet-4-5-20251020"
    )
    settings = build_runtime_model_settings(config, None, intent=LLMIntent.CHAT)
    assert settings is None or "max_tokens" not in settings
```

Run: `uv run --all-packages pytest tests/unit/core/llm/test_runtime_model_settings.py -q` → PASS.

**Decision (recorded for CHANGELOG/CURRENT_STATE):** accept the higher Anthropic default (fewer truncations); users with configured output limits are unaffected because their limit is forwarded as `max_tokens`.

- [ ] **Step 7: v2.52 — `SubAgents` no longer load agent files by default + `inherit_tools` deprecated**

```bash
rg -n "SubAgents|inherit_tools" apps packages evals tests -g '*.py'
```
Expected: no matches. Verdict: not affected.

- [ ] **Step 8: Full unit gate + commit (Platform)**

```bash
just test-unit
git add tests/unit/core/llm/test_runtime_model_settings.py
git commit -m "test(core/llm): pin max_tokens omission without output limit (pydantic-ai 2.52 anthropic default change)"
```

- [ ] **Step 9: Phase-end gate**

```bash
just verify && just check-architecture
```

**Acceptance criteria:** every walkthrough item has an explicit verdict; guard test green; phase gate green.

---

## Phase 2 — Security Verification (F1)

### Task 4: OTel content-leak regression test (GHSA-4x9p-g9wm-8q7f)

**Files:**
- Create: `tests/unit/api/_app/test_telemetry_content_leak.py`

**Interfaces:**
- Consumes: `narrare_core.agents.instrumentation.configure_pydantic_ai_instrumentation(include_content=..., tracer_provider=...)` (existing), pydantic-ai 2.52 instrumentation.
- Produces: regression net proving spans carry no prompt/instruction/output-template content when `NARRARE_OTEL_INCLUDE_CONTENT=false`, and still carry non-content telemetry ("no MORE and no LESS").

**Assigned layer/subagent:** NarrareBackendSpecialist · **Est. LOC:** ~130

- [ ] **Step 1: Verify the installed instrumentation API surface (2.52)**

```bash
uv run --all-packages python -c "from pydantic_ai import Agent; print(hasattr(Agent, 'instrument'), hasattr(Agent, 'instrument_all'))"
rg -n "include_content" .venv/lib/python3.14/site-packages/pydantic_ai/_instrumentation.py | head
```
Expected: per-agent `Agent.instrument(settings)` exists (preferred — avoids global state); if only `instrument_all` exists, adapt the test with a try/finally that calls `Agent.instrument_all(None)` to un-instrument. Note: `InstrumentationSettings(tracer_provider=...)` is public API (already used in `instrumentation.py`).

- [ ] **Step 2: Write the regression test**

`tests/unit/api/_app/test_telemetry_content_leak.py`:

```python
"""Regression: GHSA-4x9p-g9wm-8q7f — no content in spans when include_content=False.

pydantic-ai < 2.44 leaked exceptions, error statuses, instructions and
output templates into OpenTelemetry spans even with
``include_content=False``. Narrare defaults content OFF in production
(``NARRARE_OTEL_INCLUDE_CONTENT``, apps/api/narrare/_app/telemetry.py).

The test runs a real agent (TestModel) under a private in-memory tracer
provider and asserts:
1. include_content=False -> no prompt / instruction / output-template
   content in any span attribute or event (the security property).
2. include_content=True  -> content IS captured (negative control: the
   test can detect content, so absence in (1) is meaningful).
3. Non-content telemetry (gen_ai request/usage attributes) is still
   present with include_content=False (no MORE and no LESS than before).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic_ai import Agent, InstrumentationSettings
from pydantic_ai.models.test import TestModel
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from pydantic import BaseModel

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import ReadableSpan

SECRET_INSTRUCTION = "SECRET-INSTRUCTION-MARKER-7f3a"
SECRET_PROMPT = "SECRET-USER-PROMPT-MARKER-b81c"
SECRET_OUTPUT = "SECRET-OUTPUT-MARKER-4d29"


class _LeakProbeOutput(BaseModel):
    """Structured output so output-template rendering is also exercised."""

    verdict: str
    reason: str


def _spans_for_run(include_content: bool) -> list[ReadableSpan]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    agent = Agent(
        TestModel(custom_output_text=SECRET_OUTPUT),
        instructions=SECRET_INSTRUCTION,
        output_type=_LeakProbeOutput,
    )
    agent.instrument(
        InstrumentationSettings(
            tracer_provider=provider,
            include_content=include_content,
            include_binary_content=False,
        )
    )
    agent.run_sync(SECRET_PROMPT)
    provider.force_flush()
    return exporter.get_finished_spans()


def _all_attribute_values(spans: list[ReadableSpan]) -> list[str]:
    values: list[str] = []
    for span in spans:
        values.extend(str(v) for v in span.attributes.values())
        for event in span.events:
            values.extend(str(v) for v in event.attributes.values())
    return values


def test_include_content_false_leaks_no_content() -> None:
    spans = _spans_for_run(include_content=False)
    assert spans, "expected at least one pydantic-ai span"
    joined = "\n".join(_all_attribute_values(spans))
    for marker in (SECRET_INSTRUCTION, SECRET_PROMPT, SECRET_OUTPUT):
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
        attr_names.update(span.attributes.keys())
    assert any(name.startswith("gen_ai") or "pydantic_ai" in name for name in attr_names), (
        "expected gen_ai/pydantic_ai telemetry attributes to survive include_content=False"
    )


@pytest.mark.parametrize("include_content", [False, True])
def test_no_span_exceptions_or_errors_leak(include_content: bool) -> None:
    """Error-status/exception redaction companion (same advisory family)."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    agent = Agent(TestModel(), instructions=SECRET_INSTRUCTION)
    agent.instrument(
        InstrumentationSettings(
            tracer_provider=provider,
            include_content=include_content,
            include_binary_content=False,
        )
    )
    with pytest.raises(Exception):  # noqa: BLE001, PT011 — TestModel validation blow-up path
        agent.run_sync(SECRET_PROMPT)  # prompt deliberately not a str-compatible input
    provider.force_flush()
    joined = "\n".join(_all_attribute_values(exporter.get_finished_spans()))
    assert SECRET_INSTRUCTION not in joined
```

Note: if the TestModel blow-up path in the last test does not raise on 2.52, drop that test (keep the first three) — do not invent a failure path.

- [ ] **Step 3: Run and iterate**

Run: `uv run --all-packages pytest tests/unit/api/_app/test_telemetry_content_leak.py -v`
Expected: PASS on 2.52.0. If `include_content=False` leaks a marker → STOP: real security regression in our stack; report immediately.

- [ ] **Step 4: Full _app suite + commit (Platform)**

```bash
uv run --all-packages pytest tests/unit/api/_app -q
git add tests/unit/api/_app/test_telemetry_content_leak.py
git commit -m "test(otel): regression — no span content with include_content=false (GHSA-4x9p-g9wm-8q7f, pydantic-ai 2.44 fixes)"
```

**Acceptance criteria:** regression test green with a meaningful negative control; no leaks observed; committed.

---

## Phase 3 — z.AI Provider Refresh (F2)

### Task 5: Register `glm-5.3-flash`

**Files:**
- Modify: `packages/core/narrare_core/llm/_providers/zai.py` (register_model list, lines 157–163)
- Modify: `apps/api/narrare/setup/provider_service.py` (`_FALLBACK_MODELS[AIProvider.ZAI]`, lines 68–71)
- Test: `tests/unit/core/llm/test_providers_zai.py`, `tests/unit/api/setup/test_provider_service.py`

**Interfaces:**
- Consumes: Task 2 install (v2.37 added glm-5.3-flash support + finish_reason fix).
- Produces: `glm-5.3-flash` selectable via provider registry (`register_model` → exact-match before prefix inference) and listed in the setup wizard fallback catalog; usable as the F4 cheap-model default.

**Assigned layer/subagent:** NarrareCoreSpecialist (zai.py + tests) + NarrareBackendSpecialist (provider_service.py + test) · **Est. LOC:** ~40

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/core/llm/test_providers_zai.py` (inside `TestMakeZai` or as a new class):

```python
class TestGlm53FlashRegistration:
    """glm-5.3-flash (pydantic-ai 2.37+) is a registered, thinking-capable z.AI model."""

    def test_factory_builds_model(self) -> None:
        model = _make_zai("glm-5.3-flash", api_key="zai-key")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "glm-5.3-flash"

    def test_infer_provider_maps_to_zai(self) -> None:
        from narrare_core.llm._providers.registry import infer_provider

        assert infer_provider("glm-5.3-flash") == "zai"
```

Append to `tests/unit/api/setup/test_provider_service.py`:

```python
def test_fallback_catalog_contains_glm_53_flash() -> None:
    """Offline fallback catalog must list glm-5.3-flash (setup wizard availability)."""
    from narrare.setup.base_schemas import AIProvider
    from narrare.setup.provider_service import _FALLBACK_MODELS

    ids = {m.id for m in _FALLBACK_MODELS[AIProvider.ZAI]}
    assert "glm-5.3-flash" in ids
```

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run --all-packages pytest tests/unit/core/llm/test_providers_zai.py::TestGlm53FlashRegistration tests/unit/api/setup/test_provider_service.py::test_fallback_catalog_contains_glm_53_flash -v`
Expected: FAIL (registry/model-list assertions).

- [ ] **Step 3: Implement**

`packages/core/narrare_core/llm/_providers/zai.py` — extend the registration loop:

```python
for _mid in [
    "glm-z1-32b",
    "glm-4-flash",
    "glm-4-plus",
    "glm-5.3-flash",
    "chatglm-4",
]:
    register_model(_mid, "zai")
```

`apps/api/narrare/setup/provider_service.py` — extend the ZAI fallback list:

```python
    AIProvider.ZAI: [
        ProviderModel(id="glm-z1-32b", name="GLM-Z1 32B", context_window=128000),
        ProviderModel(id="glm-4-flash", name="GLM-4 Flash", context_window=128000),
        ProviderModel(id="glm-5.3-flash", name="GLM-5.3 Flash", context_window=128000),
    ],
```

- [ ] **Step 4: Run — expect PASS, then regression suites**

```bash
uv run --all-packages pytest tests/unit/core/llm/test_providers_zai.py tests/unit/api/setup -q
```

- [ ] **Step 5: Commit (Platform)**

```bash
git add packages/core/narrare_core/llm/_providers/zai.py apps/api/narrare/setup/provider_service.py tests/unit/core/llm/test_providers_zai.py tests/unit/api/setup/test_provider_service.py
git commit -m "feat(zai): register glm-5.3-flash in provider registry and setup fallback catalog"
```

**Acceptance criteria:** both tests green; `_ZAI_MODEL_PROFILE` deltas (`supports_thinking=True`, `max_completion_tokens=False`) apply unchanged (inherited — no profile edit needed); live wizard listing comes from the provider API when reachable (fallback is offline-only).

---

## Phase 4 — SelectModel Dynamic Tier Routing (F3) — design first, then pilot

### Task 6: ADR-089 — Dynamic tier routing design (spec before code)

**Files:**
- Create: `docs/architecture/decisions/ADR-089-dynamic-tier-routing-selectmodel.md`
- Modify: `docs/architecture/decisions/INDEX.md` (one row)

**Interfaces:**
- Consumes: installed pydantic-ai 2.52 (exact `SelectModel` API), `ModelRegistry` (`core/llm/gateway.py`), `ModelRoutingResolver` (`core/llm/model_routing.py`).
- Produces: binding design implemented by Tasks 7–8: module home `core/llm/dynamic_tiering.py`, factory `build_tiered_model(...)`, pure policy `should_escalate(...)`, CoreSettings flag `llm_dynamic_tiering_enabled` (default False).

**Assigned layer/subagent:** NarrareArchitectureSpecialist (this agent's mandate; may be delegated with this task text as the spec) · **Est. LOC:** ~150 (prose)

- [ ] **Step 1: Pin the exact upstream API against the installed package**

```bash
rg -n "class SelectModel|ModelSelectionContext" .venv/lib/python3.14/site-packages/pydantic_ai/ -g '*.py'
uv run --all-packages python -c "from pydantic_ai.models import SelectModel" 2>&1 | tail -1
```
Record import path, constructor signature, and the callback signature (what `ModelSelectionContext` exposes: `.messages`, `.prompt`) verbatim in the ADR. If the import path differs (e.g. `pydantic_ai.models.select`), the ADR records the verified path and Task 7 uses it.

- [ ] **Step 2: Write ADR-089 with these binding decisions** (full prose expansion of each, following `_TEMPLATE.md`):

1. **Gateway mediation (RULE-01b):** `SelectModel` wiring lives in `core/llm/dynamic_tiering.py`. The selection callback resolves ONLY between two eagerly-constructed `Model` instances built through `ModelRegistry.get_model` (provider registry factories) with per-user `api_key`/`base_url` closed over at construction time — the callback itself never touches factories/env (credential safety, ADR-071).
2. **Static routing stays default:** `INTENT_PROFILES` advisory tiers + the user cascade are untouched. Dynamic selection is opt-in via `CoreSettings.llm_dynamic_tiering_enabled` (default `False`, env `NARRARE_LLM_DYNAMIC_TIERING`).
3. **Escalation policy v1 is deterministic** (no LLM in the routing path): escalate when `len(latest user message) > max_prompt_chars` (default 2000) OR `turn_count >= min_turns` (default 6). Env-tunable (`NARRARE_LLM_DYNAMIC_TIERING_MAX_PROMPT_CHARS`, `..._MIN_TURNS`) for pilot evaluation.
4. **Escalation target:** resolved through the existing `ModelRoutingResolver` cascade with `LLMIntent.ANALYSE` (an existing, user-configurable reasoning-tier route — no new settings surface). Graceful degradation: if the escalation cascade raises `ConfigurationError`, log a warning and stay on the base model (opt-in feature must never hard-fail chat; RULE-11 with explicit warning, not silence).
5. **Pilot scope:** `ChatService` path only (`apps/api/narrare/chat/`).
6. **Alternatives evaluated and rejected:** (a) LLM-judge router — cost/latency + non-determinism, needs its own eval; (b) custom `Model` wrapper outside pydantic-ai — reimplements maintained upstream logic; (c) always-capable model — status quo, no saving; (d) per-user DB-configured tier ladder — needs settings UI + migration, out of pilot scope.
7. **Related:** ADR-001, ADR-015, ADR-072 (adoption strategy), ADR-086 (lazy resolution — tiered model is built at first use, same seam).

- [ ] **Step 3: Add the INDEX.md row** (Status 🔄 Proposed → ✅ when Task 8 lands; Affects: `core/llm/dynamic_tiering.py`, `apps/api/narrare/chat/`, RULE-01b/03/18).

- [ ] **Step 4: Commit (Platform)**

```bash
git add docs/architecture/decisions/ADR-089-dynamic-tier-routing-selectmodel.md docs/architecture/decisions/INDEX.md
git commit -m "docs(adr): ADR-089 — opt-in dynamic tier routing pilot via pydantic-ai SelectModel"
```

**Acceptance criteria:** ADR contains the verbatim verified upstream API signatures and all seven decisions; INDEX updated.

### Task 7: Core module — `dynamic_tiering.py` (policy + tiered model factory)

**Files:**
- Create: `packages/core/narrare_core/llm/dynamic_tiering.py`
- Modify: `packages/core/narrare_core/settings.py` (3 flag fields)
- Test: `tests/unit/core/llm/test_dynamic_tiering.py`

**Interfaces:**
- Consumes: ADR-089 verified `SelectModel` API; `ModelRegistry.get_model`; `ResolvedModelConfig`.
- Produces (exact signatures Tasks 8 and later rely on):

```python
@dataclass(frozen=True, slots=True)
class TierEscalationPolicy:
    max_prompt_chars: int = 2000
    min_turns: int = 6

def should_escalate(latest_user_message: str, turn_count: int, policy: TierEscalationPolicy | None = None) -> bool

def latest_user_text(messages: Sequence[Any]) -> str   # Any = pydantic_ai.messages.ModelMessage

async def build_tiered_model(
    registry: ModelRegistry,
    base_config: ResolvedModelConfig,
    capable_config: ResolvedModelConfig,
    *,
    intent: LLMIntent = LLMIntent.CHAT,
    api_key: str | None = None,
    base_url: str | None = None,
    policy: TierEscalationPolicy | None = None,
) -> Model
```

**Assigned layer/subagent:** NarrareCoreSpecialist · **Est. LOC:** ~200

- [ ] **Step 1: Write failing tests**

`tests/unit/core/llm/test_dynamic_tiering.py`:

```python
"""Unit tests for core/llm/dynamic_tiering.py (ADR-089 pilot)."""

from __future__ import annotations

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from narrare_core.llm.dynamic_tiering import (
    TierEscalationPolicy,
    latest_user_text,
    should_escalate,
)


class TestShouldEscalate:
    def test_short_first_turn_stays_on_base(self) -> None:
        assert should_escalate("hello", 1) is False

    def test_long_prompt_escalates(self) -> None:
        assert should_escalate("x" * 2001, 1) is True

    def test_turn_count_escalates(self) -> None:
        assert should_escalate("hello", 6) is True

    def test_custom_policy_overrides(self) -> None:
        policy = TierEscalationPolicy(max_prompt_chars=10, min_turns=99)
        assert should_escalate("x" * 11, 1, policy) is True
        assert should_escalate("x" * 5, 50, policy) is False


class TestLatestUserText:
    def test_extracts_last_user_message(self) -> None:
        messages = [
            ModelRequest(parts=[UserPromptPart(content="first question")]),
            ModelRequest(parts=[UserPromptPart(content="second question")]),
        ]
        assert latest_user_text(messages) == "second question"

    def test_empty_history_returns_empty(self) -> None:
        assert latest_user_text([]) == ""


class TestBuildTieredModel:
    async def test_builds_model_from_registry_configs(self) -> None:
        """Factory resolves both tiers through ModelRegistry and returns a Model.

        Uses a stub registry (no network): get_model returns sentinel Models.
        """
        from narrare_core.llm.dynamic_tiering import build_tiered_model
        from narrare_core.llm.model_config import ResolvedModelConfig

        class _StubRegistry:
            async def get_model(self, config, *, api_key=None, base_url=None, usage_limits=None):
                from pydantic_ai.models.test import TestModel

                return TestModel()

        base = ResolvedModelConfig(provider_name="zai", model_id="glm-5.3-flash")
        capable = ResolvedModelConfig(provider_name="zai", model_id="glm-4-plus")
        model = await build_tiered_model(_StubRegistry(), base, capable)  # type: ignore[arg-type]
        assert model is not None
```

Run: `uv run --all-packages pytest tests/unit/core/llm/test_dynamic_tiering.py -v` → FAIL (module not defined).

- [ ] **Step 2: Implement `packages/core/narrare_core/llm/dynamic_tiering.py`**

```python
"""Opt-in per-step dynamic model tier selection (ADR-089, pydantic-ai SelectModel pilot).

Wraps a cheap base model and a capable escalation model. Both are built
ONCE through ``ModelRegistry.get_model`` (RULE-01b: the gateway stays the
only model factory); the per-step selection callback only picks between
the two pre-built instances — no factory/env access at selection time.

The escalation policy v1 is deterministic: latest-user-message length or
conversation turn count. No LLM in the routing path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai.models import Model

    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_config import ResolvedModelConfig

logger = structlog.get_logger(__name__)

__all__ = ["TierEscalationPolicy", "should_escalate", "latest_user_text", "build_tiered_model"]


@dataclass(frozen=True, slots=True)
class TierEscalationPolicy:
    """Deterministic escalation thresholds (ADR-089 Decision 3).

    Attributes:
        max_prompt_chars: Escalate when the latest user message is longer.
        min_turns: Escalate when the conversation has at least this many turns.
    """

    max_prompt_chars: int = 2000
    min_turns: int = 6


def should_escalate(
    latest_user_message: str,
    turn_count: int,
    policy: TierEscalationPolicy | None = None,
) -> bool:
    """Return True when the request should run on the capable tier."""
    cfg = policy or TierEscalationPolicy()
    return len(latest_user_message) > cfg.max_prompt_chars or turn_count >= cfg.min_turns


def latest_user_text(messages: Sequence[Any]) -> str:
    """Extract the newest user-prompt text from a pydantic-ai message history."""
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    for message in reversed(list(messages)):
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    return part.content
    return ""


def _turn_count(messages: Sequence[Any]) -> int:
    """Count user turns (request messages) in the history."""
    from pydantic_ai.messages import ModelRequest

    return sum(1 for m in messages if isinstance(m, ModelRequest))


async def build_tiered_model(
    registry: ModelRegistry,
    base_config: ResolvedModelConfig,
    capable_config: ResolvedModelConfig,
    *,
    intent: LLMIntent = LLMIntent.CHAT,
    api_key: str | None = None,
    base_url: str | None = None,
    policy: TierEscalationPolicy | None = None,
) -> Model:
    """Build a tiered Model: cheap base, capable escalation (ADR-089).

    Both models are resolved eagerly through the registry with credentials
    closed over; the SelectModel callback only chooses between them.
    The exact pydantic-ai ``SelectModel`` wiring (import path + callback
    signature) is pinned verbatim in ADR-089 Step 1 — use those verified
    names here.
    """
    cfg = policy or TierEscalationPolicy()
    base_model = await registry.get_model(base_config, api_key=api_key, base_url=base_url)
    capable_model = await registry.get_model(capable_config, api_key=api_key, base_url=base_url)

    def _select(context: Any) -> Model:
        messages = getattr(context, "messages", [])
        if should_escalate(latest_user_text(messages), _turn_count(messages), cfg):
            logger.debug(
                "dynamic_tier_escalated",
                base=base_config.model_id,
                capable=capable_config.model_id,
                intent=intent.value,
            )
            return capable_model
        return base_model

    from pydantic_ai.models import SelectModel  # exact import per ADR-089 Step 1

    return SelectModel(_select)
```

Implementation note for the executor: ADR-089 Step 1's verbatim signature rules here — if `SelectModel` expects model *names* plus a lookup, or a different callable shape, adapt `_select`/return exactly as the ADR records (the ADR is the contract; do not improvise a second design). Keep the policy functions untouched either way.

- [ ] **Step 3: Add the CoreSettings fields** (ADR-071 pattern, `packages/core/narrare_core/settings.py`):

```python
    llm_dynamic_tiering_enabled: bool = Field(
        default=False, validation_alias="NARRARE_LLM_DYNAMIC_TIERING"
    )
    """ADR-089 pilot: opt-in per-step dynamic tier selection (chat path only)."""

    llm_dynamic_tiering_max_prompt_chars: int = Field(
        default=2000, validation_alias="NARRARE_LLM_DYNAMIC_TIERING_MAX_PROMPT_CHARS"
    )
    llm_dynamic_tiering_min_turns: int = Field(
        default=6, validation_alias="NARRARE_LLM_DYNAMIC_TIERING_MIN_TURNS"
    )
```

- [ ] **Step 4: Run tests → PASS; then architecture gate**

```bash
uv run --all-packages pytest tests/unit/core/llm/test_dynamic_tiering.py -v
uv run --all-packages pytest tests/unit/core -q
just check-architecture
```

- [ ] **Step 5: Commit (Platform)**

```bash
git add packages/core/narrare_core/llm/dynamic_tiering.py packages/core/narrare_core/settings.py tests/unit/core/llm/test_dynamic_tiering.py
git commit -m "feat(core/llm): dynamic tier selection module — deterministic policy + registry-mediated SelectModel factory (ADR-089)"
```

**Acceptance criteria:** policy pure-function tests green; factory returns a tiered Model built exclusively via the registry; flag default False; architecture gate green (module correctly inside `core/llm/`).

### Task 8: Backend pilot wiring — ChatService opt-in

**Files:**
- Modify: `apps/api/narrare/chat/dependencies.py`
- Modify: `apps/api/narrare/chat/chat_service.py`
- Test: `tests/unit/api/chat/test_chat_dynamic_tiering.py`

**Interfaces:**
- Consumes: `build_tiered_model` (Task 7), `CoreSettings.llm_dynamic_tiering_enabled`, `ModelResolution` protocol (`apps/api/narrare/_app/dependencies_services.py`, ADR-086).
- Produces: chat path behavior — flag off (default): byte-identical to today; flag on: base CHAT model wrapped for tier escalation, capable tier resolved via `LLMIntent.ANALYSE` cascade with graceful degradation.

**Assigned layer/subagent:** NarrareBackendSpecialist · **Est. LOC:** ~120

- [ ] **Step 1: Read the seam before editing** — `apps/api/narrare/chat/chat_service.py` (`ensure_resolved` at ~line 112, agent creation ~lines 183–223) and `apps/api/narrare/chat/dependencies.py` (how the CHAT `ModelResolution` is constructed). RULE-086: resolution stays lazy (first use), never at DI time.

- [ ] **Step 2: Write the failing service-level tests** (use the existing chat test fixtures/fakes in `tests/unit/api/chat/`; `StaticModelResolution` from `_app/dependencies_services.py` for both cascades):

```python
"""ChatService dynamic tiering pilot wiring (ADR-089) — default-off invariant."""

from __future__ import annotations

# Three cases (adapt fixture names to the existing chat service test module):
#
# 1. test_flag_disabled_uses_base_model_unchanged:
#    settings.llm_dynamic_tiering_enabled=False -> the model handed to the
#    agent is exactly the base-resolution model (identity assert), and no
#    escalation resolution is ever awaited.
#
# 2. test_flag_enabled_wraps_model_with_tiered_factory:
#    flag=True + ANALYSE cascade resolves -> ChatAgent receives the model
#    returned by build_tiered_model (monkeypatch build_tiered_model with a
#    recording stub returning a sentinel TestModel).
#
# 3. test_flag_enabled_degrades_gracefully_when_capable_unresolvable:
#    flag=True + ANALYSE cascade raises ConfigurationError -> chat still
#    answers on the base model and a warning event
#    "dynamic_tiering_escalation_unavailable" is logged.
```

Write the three tests concretely against the real fixture names found in Step 1 (the case list above is the contract; the bodies follow the established chat service fake pattern).

Run: `uv run --all-packages pytest tests/unit/api/chat/test_chat_dynamic_tiering.py -v` → FAIL (no wiring).

- [ ] **Step 3: Implement the wiring**

In `chat_service.py`: accept optional `escalation_resolution: ModelResolution | None = None`; inside the first-use resolution path (after base resolution succeeds):

```python
from narrare_core.llm.dynamic_tiering import TierEscalationPolicy, build_tiered_model
from narrare_core.settings import get_core_settings
# flag check + wrap (sketched — place at the exact seam found in Step 1):
settings = get_core_settings()
if settings.llm_dynamic_tiering_enabled and self._escalation_resolution is not None:
    try:
        capable = await self._escalation_resolution.resolve()
        model = await build_tiered_model(
            self._registry, resolved.config, capable.config,
            api_key=resolved.api_key, base_url=resolved.base_url,
            policy=TierEscalationPolicy(
                max_prompt_chars=settings.llm_dynamic_tiering_max_prompt_chars,
                min_turns=settings.llm_dynamic_tiering_min_turns,
            ),
        )
    except ConfigurationError:
        logger.warning("dynamic_tiering_escalation_unavailable")
        model = base_model
```

(The policy is built from the CoreSettings knobs added in Task 7 — the env vars are live-tunable for pilot evaluation.)

In `dependencies.py`: construct the escalation resolution via the same resolver factory used for CHAT, but for `LLMIntent.ANALYSE`, and pass it in (only when the flag is on — keep DI cheap otherwise; `None` when off).

- [ ] **Step 4: Run — expect PASS, then regression**

```bash
uv run --all-packages pytest tests/unit/api/chat -q
uv run --all-packages pytest tests/unit/api -q
```

- [ ] **Step 5: Commit (Platform) + flip ADR status**

```bash
git add apps/api/narrare/chat/chat_service.py apps/api/narrare/chat/dependencies.py tests/unit/api/chat/test_chat_dynamic_tiering.py
git commit -m "feat(chat): opt-in dynamic tier escalation pilot behind NARRARE_LLM_DYNAMIC_TIERING (ADR-089)"
```
Update ADR-089 + INDEX row to ✅ (same commit or immediate follow-up via Platform).

- [ ] **Step 6: Phase-end gate:** `just verify && just check-architecture`.

**Acceptance criteria:** flag-off byte-identical behavior (test 1); flag-on wrap + graceful degradation (tests 2–3); no eager resolution at DI time (ADR-086 respected); gates green.

---

## Phase 5 — Decision-Patterns Pilot (F4, "Weg A", no TypeSafe)

### Task 9: New `LLMIntent.CONSISTENCY_TRIAGE` across the SSOT tables

> Sizing deviation note: this task touches 5 files, each with a 1–6 line edit. The intent tables are one atomic invariant — any intermediate state fails `just check-architecture` (every `LLMIntent` member must sit in exactly one of ROUTE_CONFIGS / INTENT_TO_CATEGORY / NON_ROUTEABLE_INTENTS and have a profile + category + docs entry). Splitting would leave red gates mid-phase; the atomic edit is ~15 LOC total.

**Files:**
- Modify: `packages/core/narrare_core/llm/intents/_enums.py` (member)
- Modify: `packages/core/narrare_core/llm/intents/_docs_analysis.py` (INTENT_DOCS entry)
- Modify: `packages/core/narrare_core/llm/intent_profiles.py` (INTENT_PROFILES entry)
- Modify: `packages/core/narrare_core/llm/intent_categories.py` (INTENT_CATEGORY_MAP entry)
- Modify: `packages/core/narrare_core/prompts/route_table.py` (NON_ROUTEABLE_INTENTS entry)

**Interfaces:**
- Produces (for Tasks 10–12): `LLMIntent.CONSISTENCY_TRIAGE` ("consistency_triage"), profile `IntentProfile("quick", "fast", ...)`, category ANALYSIS, non-routeable (agent uses deps-driven dynamic instructions per RULE-02a §3 — no PromptComposer cascade prompt).

**Assigned layer/subagent:** NarrareCoreSpecialist · **Est. LOC:** ~35

- [ ] **Step 1: Add the enum member FIRST, then watch the guards fail (regression-first)**

In `_enums.py`, ANALYSIS section:

```python
    CONSISTENCY_TRIAGE = "consistency_triage"
    """Rubric-based severity/confidence re-scoring of consistency issues (cheap model)."""
```

Run: `uv run --all-packages pytest tests/unit/core/llm/test_intent_profile_completeness.py tests/unit/core/llm/test_intent_profiles.py -q`
Expected: FAIL — the completeness guard demands a profile entry (this is the failing test that drives the rest of the task).

- [ ] **Step 2: Fill the tables**

`_docs_analysis.py` (append to `ANALYSIS_INTENT_DOCS`, matching its doc style):

```python
    LLMIntent.CONSISTENCY_TRIAGE: """Rubric-based severity/confidence triage of
ConsistencyAgent issues on a cheap model.

Scope: re-score each already-detected ConsistencyIssue with an IntEnum
severity rubric, evidence booleans and a confidence band (DecisionModel
output-design patterns, Weg A — no TypeSafe, no logprob calibration).
Input: issue list (description + conflicting_facts + current severity).
Output: per-issue rubric assessment.
NOT: issue detection (that is LLMIntent.CONSISTENCY / FACT_EXTRACT),
full calibrated probabilities (Weg B — future ADR).""",
```

`intent_profiles.py` (ANALYSIS section):

```python
    LLMIntent.CONSISTENCY_TRIAGE: IntentProfile(
        "quick", "fast", "Rubric-based consistency triage (cheap model)"
    ),
```

`intent_categories.py`:

```python
    LLMIntent.CONSISTENCY_TRIAGE: IntentCategory.ANALYSIS,
```

`route_table.py` `NON_ROUTEABLE_INTENTS`:

```python
    LLMIntent.CONSISTENCY_TRIAGE: (
        "Triage agent uses deps-driven dynamic instructions (RULE-02a §3); "
        "no PromptComposer cascade prompt."
    ),
```

- [ ] **Step 3: Run guards green + architecture check**

```bash
uv run --all-packages pytest tests/unit/core/llm -q
just check-architecture
```

- [ ] **Step 4: Commit (Platform)**

```bash
git add packages/core/narrare_core/llm/intents/_enums.py packages/core/narrare_core/llm/intents/_docs_analysis.py packages/core/narrare_core/llm/intent_profiles.py packages/core/narrare_core/llm/intent_categories.py packages/core/narrare_core/prompts/route_table.py
git commit -m "feat(core/llm): add LLMIntent.CONSISTENCY_TRIAGE (fast tier, non-routeable) for decision-pattern pilot"
```

**Acceptance criteria:** intent completeness/profile/checker guards green; `just check-architecture` green.

### Task 10: Triage output types — DecisionModel rubric patterns

**Files:**
- Create: `packages/core/narrare_core/agents/consistency_triage_types.py`
- Test: `tests/unit/core/agents/test_consistency_triage_types.py`

**Interfaces:**
- Consumes: `ConsistencyOutput`/`ConsistencyIssue`/`ConsistencySeverity` from `consistency_types.py` (Task 9 intent).
- Produces (Task 11/12 rely on exactly these names):

```python
class SeverityRubric(IntEnum):            # NO_ISSUE=0, MINOR=1, WARNING=2, ERROR=3
class ConfidenceBand(IntEnum):            # LOW=0, MEDIUM=1, HIGH=2
class TriageEvidence(BaseModel):          # BoolCriteria pattern: 4 evidence booleans
class TriageAssessment(BaseModel):        # issue_index, severity, evidence, confidence
class ConsistencyTriageOutput(BaseModel): # assessments: list[TriageAssessment]
SEVERITY_TO_CONSISTENCY: dict[SeverityRubric, ConsistencySeverity]
BAND_TO_CONFIDENCE: dict[ConfidenceBand, float]
def apply_triage(output: ConsistencyOutput, triage: ConsistencyTriageOutput) -> ConsistencyOutput
class ConsistencyTriageDeps:              # language, issues (plain class, ConsistencyDeps pattern)
```

**Assigned layer/subagent:** NarrareCoreSpecialist · **Est. LOC:** ~160

- [ ] **Step 1: Write the failing tests**

`tests/unit/core/agents/test_consistency_triage_types.py`:

```python
"""Unit tests for consistency_triage_types (DecisionModel-pattern pilot, Weg A)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.agents.consistency_types import (
    ConsistencyIssue,
    ConsistencyOutput,
    ConsistencySeverity,
    ConsistencyCheckType,
)
from narrare_core.agents.consistency_triage_types import (
    BAND_TO_CONFIDENCE,
    SEVERITY_TO_CONSISTENCY,
    ConfidenceBand,
    ConsistencyTriageOutput,
    SeverityRubric,
    TriageAssessment,
    TriageEvidence,
    apply_triage,
)


def _issue(i: int, severity: ConsistencySeverity = ConsistencySeverity.WARNING) -> ConsistencyIssue:
    return ConsistencyIssue(
        check_type=ConsistencyCheckType.PLOT,
        severity=severity,
        description=f"issue {i}",
        locations=["ch1"],
        conflicting_facts=["fact a", "fact b"],
        confidence=0.5,
    )


class TestRubricMappings:
    def test_severity_rubric_covers_all_levels(self) -> None:
        assert SEVERITY_TO_CONSISTENCY[SeverityRubric.NO_ISSUE] == ConsistencySeverity.INFO
        assert SEVERITY_TO_CONSISTENCY[SeverityRubric.MINOR] == ConsistencySeverity.INFO
        assert SEVERITY_TO_CONSISTENCY[SeverityRubric.WARNING] == ConsistencySeverity.WARNING
        assert SEVERITY_TO_CONSISTENCY[SeverityRubric.ERROR] == ConsistencySeverity.ERROR

    def test_band_to_confidence_within_bounds(self) -> None:
        for value in BAND_TO_CONFIDENCE.values():
            assert 0.0 <= value <= 1.0


class TestApplyTriage:
    def test_regrades_severity_and_confidence(self) -> None:
        output = ConsistencyOutput(issues=[_issue(0), _issue(1)])
        triage = ConsistencyTriageOutput(
            assessments=[
                TriageAssessment(
                    issue_index=0,
                    severity=SeverityRubric.ERROR,
                    evidence=TriageEvidence(
                        facts_directly_contradict=True,
                        both_facts_explicitly_stated=True,
                        contradiction_verifiable_without_external_knowledge=True,
                        could_be_intentional_stylistic_choice=False,
                    ),
                    confidence=ConfidenceBand.HIGH,
                ),
                TriageAssessment(
                    issue_index=1,
                    severity=SeverityRubric.WARNING,
                    evidence=TriageEvidence(
                        facts_directly_contradict=True,
                        both_facts_explicitly_stated=False,
                        contradiction_verifiable_without_external_knowledge=True,
                        could_be_intentional_stylistic_choice=True,
                    ),
                    confidence=ConfidenceBand.MEDIUM,
                ),
            ]
        )
        result = apply_triage(output, triage)
        assert result.issues[0].severity == ConsistencySeverity.ERROR
        assert result.issues[0].confidence == BAND_TO_CONFIDENCE[ConfidenceBand.HIGH]
        assert result.issues[1].severity == ConsistencySeverity.WARNING

    def test_no_issue_assessment_drops_issue(self) -> None:
        output = ConsistencyOutput(issues=[_issue(0)])
        triage = ConsistencyTriageOutput(
            assessments=[
                TriageAssessment(
                    issue_index=0,
                    severity=SeverityRubric.NO_ISSUE,
                    evidence=TriageEvidence(
                        facts_directly_contradict=False,
                        both_facts_explicitly_stated=False,
                        contradiction_verifiable_without_external_knowledge=True,
                        could_be_intentional_stylistic_choice=True,
                    ),
                    confidence=ConfidenceBand.HIGH,
                )
            ]
        )
        result = apply_triage(output, triage)
        assert result.issues == []

    def test_index_out_of_range_raises(self) -> None:
        output = ConsistencyOutput(issues=[_issue(0)])
        triage = ConsistencyTriageOutput(
            assessments=[
                TriageAssessment(
                    issue_index=7,
                    severity=SeverityRubric.MINOR,
                    evidence=TriageEvidence(
                        facts_directly_contradict=True,
                        both_facts_explicitly_stated=True,
                        contradiction_verifiable_without_external_knowledge=True,
                        could_be_intentional_stylistic_choice=False,
                    ),
                    confidence=ConfidenceBand.LOW,
                )
            ]
        )
        with pytest.raises(ValueError):
            apply_triage(output, triage)
```

Run: `uv run --all-packages pytest tests/unit/core/agents/test_consistency_triage_types.py -v` → FAIL (module missing).

- [ ] **Step 2: Implement `consistency_triage_types.py`**

```python
"""DecisionModel-pattern output types for consistency triage (Weg A pilot).

Adopts pydantic-ai DecisionModel OUTPUT-DESIGN patterns only — IntEnum
rubrics with described levels, BoolCriteria-style evidence booleans,
per-field questions via Field descriptions, and band-style confidence.
NO TypeSafe/Jev integration and NO logprob calibration (Weg B is a
future ADR).

The triage re-scores ConsistencyAgent issues on a CHEAP model
(LLMIntent.CONSISTENCY_TRIAGE, fast tier).
"""

from __future__ import annotations

from enum import IntEnum

from pydantic import BaseModel, Field

from narrare_core.agents.consistency_types import (
    ConsistencyIssue,
    ConsistencyOutput,
    ConsistencySeverity,
)

_SEVERITY_LEVELS = (
    "0 = NO_ISSUE: facts are consistent or the difference is an intentional "
    "stylistic choice. 1 = MINOR: trivial discrepancy a reader would not "
    "notice. 2 = WARNING: noticeable inconsistency that breaks immersion. "
    "3 = ERROR: impossible contradiction; the plot cannot hold as written."
)
_CONFIDENCE_LEVELS = (
    "0 = LOW: plausible but weakly supported. 1 = MEDIUM: supported by the "
    "quoted facts. 2 = HIGH: the contradiction is explicit in the quoted facts."
)


class SeverityRubric(IntEnum):
    """Described severity levels (level prose in every schema via Field description)."""

    NO_ISSUE = 0
    MINOR = 1
    WARNING = 2
    ERROR = 3


class ConfidenceBand(IntEnum):
    """Banded confidence — deliberately NOT a free-floating 0.0-1.0 self-report."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2


SEVERITY_TO_CONSISTENCY: dict[SeverityRubric, ConsistencySeverity] = {
    SeverityRubric.NO_ISSUE: ConsistencySeverity.INFO,
    SeverityRubric.MINOR: ConsistencySeverity.INFO,
    SeverityRubric.WARNING: ConsistencySeverity.WARNING,
    SeverityRubric.ERROR: ConsistencySeverity.ERROR,
}

BAND_TO_CONFIDENCE: dict[ConfidenceBand, float] = {
    ConfidenceBand.LOW: 0.3,
    ConfidenceBand.MEDIUM: 0.6,
    ConfidenceBand.HIGH: 0.9,
}


class TriageEvidence(BaseModel):
    """BoolCriteria pattern — yes/no questions, one boolean each."""

    facts_directly_contradict: bool = Field(
        description="Do the quoted conflicting facts state mutually exclusive things?"
    )
    both_facts_explicitly_stated: bool = Field(
        description="Are BOTH facts explicitly written in the text (not inferred)?"
    )
    contradiction_verifiable_without_external_knowledge: bool = Field(
        description="Can a reader detect the contradiction from the novel alone?"
    )
    could_be_intentional_stylistic_choice: bool = Field(
        description="Could the difference plausibly be an intentional authorial choice?"
    )


class TriageAssessment(BaseModel):
    """Per-field question set for ONE issue (indexed by position in the input list)."""

    issue_index: int = Field(ge=0, description="0-based index into the triaged issue list")
    severity: SeverityRubric = Field(description=_SEVERITY_LEVELS)
    evidence: TriageEvidence
    confidence: ConfidenceBand = Field(description=_CONFIDENCE_LEVELS)


class ConsistencyTriageOutput(BaseModel):
    """Structured triage result — one assessment per input issue."""

    assessments: list[TriageAssessment] = Field(default_factory=list)


def apply_triage(output: ConsistencyOutput, triage: ConsistencyTriageOutput) -> ConsistencyOutput:
    """Fold triage assessments back into a ConsistencyOutput (pure function).

    Rules:
    - NO_ISSUE assessments DROP the issue (false-positive suppression).
    - severity is re-mapped via SEVERITY_TO_CONSISTENCY.
    - confidence is re-mapped via BAND_TO_CONFIDENCE (band, not self-report).
    - assessments with an out-of-range issue_index raise ValueError (ADR-035
      deterministic invariant — caller-side validation retries at the agent
      boundary instead).
    """

    def _update(issue: ConsistencyIssue, assessment: TriageAssessment) -> ConsistencyIssue:
        return issue.model_copy(
            update={
                "severity": SEVERITY_TO_CONSISTENCY[assessment.severity],
                "confidence": BAND_TO_CONFIDENCE[assessment.confidence],
            }
        )

    for assessment in triage.assessments:
        if assessment.issue_index >= len(output.issues):
            raise ValueError(
                f"triage assessment index {assessment.issue_index} out of range "
                f"for {len(output.issues)} issues"
            )

    kept = [
        _update(issue, triage.assessments[i])
        for i, issue in enumerate(output.issues)
        if triage.assessments[i].severity is not SeverityRubric.NO_ISSUE
    ]
    return output.model_copy(update={"issues": kept})


class ConsistencyTriageDeps:
    """Deps for ConsistencyTriageAgent (plain class, ConsistencyDeps pattern)."""

    def __init__(self, language: str = "en", issues: list[ConsistencyIssue] | None = None) -> None:
        self.language = language
        self.issues = issues or []
```

Design note — DecisionModel output patterns covered (Weg A): IntEnum rubrics with described levels (`SeverityRubric` + `_SEVERITY_LEVELS`), BoolCriteria (`TriageEvidence`), per-field questions (every `Field(description=...)` is the question), and the optional `Choices` pattern is realized by the enum constraints themselves (`SeverityRubric`/`ConfidenceBand` are exactly the constrained choice sets — no free-text severity).

Note: `apply_triage` requires one assessment per issue in order. The agent validator (Task 11) enforces exactly that, so the list-index access above is safe.

- [ ] **Step 3: Run tests → PASS; export nothing from `agents/__init__.py` yet (agent lands in Task 11).**

```bash
uv run --all-packages pytest tests/unit/core/agents/test_consistency_triage_types.py -v
```

- [ ] **Step 4: Commit (Platform)**

```bash
git add packages/core/narrare_core/agents/consistency_triage_types.py tests/unit/core/agents/test_consistency_triage_types.py
git commit -m "feat(core/agents): decision-pattern triage types — severity rubric, evidence booleans, confidence bands"
```

**Acceptance criteria:** all rubric tests green; `apply_triage` pure (no I/O); NO_ISSUE drops issues; out-of-range raises.

### Task 11: `ConsistencyTriageAgent`

**Files:**
- Create: `packages/core/narrare_core/agents/consistency_triage_agent.py`
- Modify: `packages/core/narrare_core/agents/__init__.py` (export — SSOT agent list)
- Test: `tests/unit/core/agents/test_consistency_triage_agent.py`

**Interfaces:**
- Consumes: types from Task 10; `NarrareAgent` base (`agents/base.py`).
- Produces: `ConsistencyTriageAgent(model, system_prompt=None)` with `run(prompt: str, deps: ConsistencyTriageDeps) -> ConsistencyTriageOutput`; ADR-035 output validator enforcing one in-range assessment per issue.

**Assigned layer/subagent:** NarrareCoreSpecialist · **Est. LOC:** ~150

- [ ] **Step 1: Write the failing agent test** (TestModel pattern from `packages/core/AGENTS.md`):

`tests/unit/core/agents/test_consistency_triage_agent.py`:

```python
"""Agent-level tests for ConsistencyTriageAgent (TestModel, no LLM)."""

from __future__ import annotations

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models.test import TestModel

from narrare_core.agents.consistency_triage_agent import (
    ConsistencyTriageAgent,
    build_triage_prompt,
)
from narrare_core.agents.consistency_triage_types import ConsistencyTriageDeps
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyIssue,
    ConsistencySeverity,
)


def _deps() -> ConsistencyTriageDeps:
    issue = ConsistencyIssue(
        check_type=ConsistencyCheckType.CHARACTER,
        severity=ConsistencySeverity.WARNING,
        description="Anna is described as an only child in ch1 but has a brother in ch3.",
        locations=["ch1", "ch3"],
        conflicting_facts=["Anna is an only child", "Anna's brother Tomas"],
        confidence=0.5,
    )
    return ConsistencyTriageDeps(language="en", issues=[issue])


async def test_agent_returns_triage_output() -> None:
    agent = ConsistencyTriageAgent(model=TestModel())
    result = await agent.run(prompt=build_triage_prompt(_deps()), deps=_deps())
    assert len(result.assessments) == 1  # TestModel fills valid enum/bool values


def test_build_triage_prompt_contains_issue_facts() -> None:
    prompt = build_triage_prompt(_deps())
    assert "Anna is an only child" in prompt
    assert "Anna's brother Tomas" in prompt
    assert "0" in prompt  # index marker


async def test_validator_rejects_missing_assessment() -> None:
    """ADR-035: exactly one assessment per issue — gap triggers ModelRetry."""
    from pydantic_ai.models.test import TestModel

    agent = ConsistencyTriageAgent(model=TestModel(custom_output_args={}))
    # Empty assessments list violates the invariant -> ModelRetry surfaces as
    # UnexpectedModelBehavior after retries are exhausted.
    with pytest.raises(UnexpectedModelBehavior):
        await agent.run(prompt="Triage.", deps=_deps())
```

(The exact `custom_output_args` shape for an empty assessment list may need adjusting to whatever TestModel accepts on 2.52 — the invariant under test is "empty assessments → retry".)

Run: `uv run --all-packages pytest tests/unit/core/agents/test_consistency_triage_agent.py -v` → FAIL.

- [ ] **Step 2: Implement the agent** (deps-driven dynamic instructions live HERE, in `core/agents/` — RULE-02a §3; services pass no prompt text):

```python
"""ConsistencyTriageAgent — rubric-based re-scoring of ConsistencyAgent issues.

Decision-pattern pilot (Weg A): IntEnum rubric + evidence booleans +
confidence bands on a CHEAP model (LLMIntent.CONSISTENCY_TRIAGE).
Detection stays with ConsistencyAgent/ADR-044; this agent only re-scores.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import ModelRetry, RunContext

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.consistency_triage_types import (
    ConsistencyTriageDeps,
    ConsistencyTriageOutput,
)

if TYPE_CHECKING:
    pass


def build_triage_prompt(deps: ConsistencyTriageDeps) -> str:
    """Serialize the issues under review into the user channel (runtime input)."""
    lines = [f"Triage the {len(deps.issues)} consistency issues below.", ""]
    for i, issue in enumerate(deps.issues):
        lines.append(f"[{i}] ({issue.check_type.value}, current severity: {issue.severity.value})")
        lines.append(f"Description: {issue.description}")
        lines.append("Conflicting facts:")
        lines.extend(f"  - {fact}" for fact in issue.conflicting_facts)
        lines.append("")
    return "\n".join(lines)


class ConsistencyTriageAgent(
    NarrareAgent[ConsistencyTriageDeps, ConsistencyTriageOutput]
):
    """Re-scores severity/confidence of detected issues via described rubrics."""

    def __init__(self, model: Any, *, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=ConsistencyTriageDeps,
            output_type=ConsistencyTriageOutput,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[ConsistencyTriageDeps],
        output: ConsistencyTriageOutput,
    ) -> ConsistencyTriageOutput:
        """ADR-035 invariants: one in-range assessment per issue, no duplicates."""
        expected = len(ctx.deps.issues)
        indices = sorted(a.issue_index for a in output.assessments)
        if indices != list(range(expected)):
            raise ModelRetry(
                f"Expected exactly one assessment per issue (indices 0..{expected - 1}), "
                f"got {indices}"
            )
        return output

    async def run(
        self, prompt: str, deps: ConsistencyTriageDeps, **kwargs: Any
    ) -> ConsistencyTriageOutput:
        return await super().run(prompt, deps, **kwargs)
```

The rubric questions themselves reach the model through the **schema descriptions** (Task 10 Field descriptions — the DecisionModel pattern); `NarrareMeta`/`NarrareUniversalRules` capabilities inject the guaranteed instruction layer as with every NarrareAgent. No bundled cascade prompt (NON_ROUTEABLE, Task 9).

- [ ] **Step 3: Export from `agents/__init__.py`** following the existing export block style (`ConsistencyTriageAgent`, `ConsistencyTriageDeps`, `ConsistencyTriageOutput`).

- [ ] **Step 4: Run → PASS; architecture + agent suites**

```bash
uv run --all-packages pytest tests/unit/core/agents -q
just check-architecture
```

- [ ] **Step 5: Commit (Platform)**

```bash
git add packages/core/narrare_core/agents/consistency_triage_agent.py packages/core/narrare_core/agents/consistency_triage_types.py packages/core/narrare_core/agents/__init__.py tests/unit/core/agents/test_consistency_triage_agent.py
git commit -m "feat(core/agents): ConsistencyTriageAgent — rubric triage on cheap model (decision-pattern pilot)"
```

**Acceptance criteria:** TestModel agent tests green; validator enforces one-assessment-per-issue; export added; gates green.

### Task 12: Eval wiring — triage in the `consistency_staged` runtime suite

**Files:**
- Modify: `evals/tasks/consistency_runtime.py`
- Modify: `evals/tasks/runtime.py` (triage env config)
- Test: `tests/unit/evals/…` — none new; smoke coverage via the eval suite itself (`evals/tasks/smoke.py` gains nothing; smoke path stays triage-free)

**Interfaces:**
- Consumes: `ConsistencyTriageAgent` (Task 11), `apply_triage` (Task 10), `RuntimeTaskFactory` env pattern.
- Produces: `consistency_staged` runtime task optionally runs the triage stage when `NARRARE_EVAL_TRIAGE_MODEL` is set; results carry both raw and triaged severity for the evaluator. Env: `NARRARE_EVAL_TRIAGE_PROVIDER` (default `zai`), `NARRARE_EVAL_TRIAGE_MODEL` (default unset = skip), `NARRARE_EVAL_TRIAGE_API_KEY`.

**Assigned layer/subagent:** NarrareCoreSpecialist (evals are repo-level Core tooling) · **Est. LOC:** ~80

- [ ] **Step 1: Extend the runtime factory** — in `runtime.py` `from_env`, add:

```python
        triage_model=os.environ.get("NARRARE_EVAL_TRIAGE_MODEL", ""),
        triage_provider=os.environ.get("NARRARE_EVAL_TRIAGE_PROVIDER", "zai"),
        triage_api_key=os.environ.get("NARRARE_EVAL_TRIAGE_API_KEY"),
```

(as dataclass fields with defaults, keeping `from_env` the single env seam).

- [ ] **Step 2: Extend `consistency_staged_task`** — after the staged pipeline produces `ConsistencyOutput`, if `triage_model` is set: resolve the triage model through `ModelRegistry` (provider factory pattern already used in this file), run `ConsistencyTriageAgent`, apply `apply_triage`, and attach both variants to the eval output (e.g. a `triaged: bool` + triaged issues on the result model — extend `evals/consistency_models.py` accordingly, keeping it backward-compatible with default-off).

- [ ] **Step 3: Run the suites (smoke without keys; runtime with z.AI key if available)**

```bash
uv run --all-packages python -m evals run --suite consistency_staged --mode smoke
NARRARE_EVAL_PROVIDER=zai NARRARE_EVAL_MODEL=glm-4-plus \
NARRARE_EVAL_TRIAGE_PROVIDER=zai NARRARE_EVAL_TRIAGE_MODEL=glm-5.3-flash \
  uv run --all-packages python -m evals run --suite consistency_staged --mode runtime
```

Expected: smoke green; runtime produces a JSON report under `evals/results/consistency_staged.json` including triaged outputs. **This run is the pilot measurement** — production wiring of the triage into `consistency_orchestrator` is explicitly deferred until the eval shows rubric severity ≥ baseline self-reported severity quality (record the verdict; follow-up plan if positive).

- [ ] **Step 4: Commit (Platform) + phase gate**

```bash
git add evals/tasks/runtime.py evals/tasks/consistency_runtime.py evals/consistency_models.py
git commit -m "feat(evals): optional consistency triage stage in consistency_staged runtime suite (decision-pattern pilot measurement)"
just verify && just check-architecture
```

**Acceptance criteria:** smoke suite green; one runtime report artifact with triage enabled exists; default behavior (no triage env) unchanged.

---

## Phase 6 — Multi-Vector Rerank Tier (F5)

### Task 13: ADR-090 + sentence-transformers v6 pin

**Files:**
- Create: `docs/architecture/decisions/ADR-090-multi-vector-rerank-tier.md`
- Modify: `docs/architecture/decisions/INDEX.md`
- Modify: `packages/core/pyproject.toml:28` (embeddings extra)

**Interfaces:**
- Consumes: existing optional `embeddings` extra; mem0's `transformers>=5.3.0` floor (mem0 2.0.12+).
- Produces: pinned `sentence-transformers>=6.1,<7`; ADR-090 binding design for Tasks 14–16 (contract names, degradation pattern, no-index-change ruling).

**Assigned layer/subagent:** NarrareArchitectureSpecialist (ADR) + NarrareCoreSpecialist (pin) · **Est. LOC:** ~140 (prose) + 1 (pin)

- [ ] **Step 1: Write ADR-090** with these binding decisions:

1. **Rerank is a post-retrieval stage only**: pgvector dense top-K (existing) → local rerank → top-N. NO index change, NO pgvector schema change, NO change to embedding write paths (`MultiVectorEncoder` only scores query×document at rerank time).
2. **Dependency policy:** the `embeddings` extra pins `sentence-transformers>=6.1,<7` (was open `>=3.0` — drift risk). Verified alignment: mem0 2.0.12+ already requires `transformers>=5.3.0`, and ST v6 sits on the transformers v5 line — one coherent floor (validate with `uv pip check` in Step 4).
3. **Contract-first (RULE-03 + RULE-08):** `Reranker` Protocol + `RerankCandidate` live in `core/embeddings/rerank.py`; `sentence_transformers` is imported ONLY there (lazy, inside the class) — mirroring `core/memory/availability.py` for graceful degradation when the extra is absent (`NullReranker` passthrough + `is_rerank_available()`).
4. **Candidate text supply:** search rows carry no text (verified) — callers inject an async text fetcher; the Core contract stays pure.
5. **Opt-in:** `CoreSettings.embedding_rerank_enabled` default `False` (+ `embedding_rerank_model` name, default = the ADR-090 pinned checkpoint — candidate `lightonai/LateOn`; recorded verbatim after the Step 3 API check. User decision 2026-09-30: never the library default).
6. **Alternatives evaluated (≥3):** (a) cross-encoder reranker (higher precision, ~10-50× rerank latency on CPU, heavier model management — rejected for pilot); (b) hosted rerank API (Cohere/Jina — violates local-first ADR-006/Q-005 posture for an always-on retrieval path); (c) do nothing / tune hybrid weights only (no semantic precision gain on lexical-adjacent queries); chosen: ST v6 `MultiVectorEncoder` local reranker behind an extra.
7. **Pilot measurement:** rewrite-selection-derived retrieval comparison (Task 16) — no pgvector change means rollback = disable flag.

- [ ] **Step 2: Pin the extra**

`packages/core/pyproject.toml` line 28:
```diff
- embeddings = ["sentence-transformers>=3.0"]
+ embeddings = ["sentence-transformers>=6.1,<7"]
```

- [ ] **Step 3: Install the extra and verify the v6 API surface (records the exact names Task 14 uses)**

```bash
uv sync --all-packages --extra embeddings --extra narrare-core  # or: uv sync --all-packages && uv pip install -e packages/core[embeddings]
uv run --all-packages python -c "from sentence_transformers import MultiVectorEncoder; print(MultiVectorEncoder)"
uv run --all-packages python -c "import sentence_transformers as st; print(st.__version__)"
```
Record the verified constructor + scoring method signatures verbatim in ADR-090 (adjust Task 14's implementation to these exact names if they differ from the sketch — the ADR is the contract).

- [ ] **Step 4: Dependency coherence + ADR-033 cascade gates**

```bash
uv pip check
uv run --all-packages pytest tests/unit/core/memory/test_embedding_cascade.py tests/unit/core/memory/test_create_memory_client.py -q
```
Expected: no conflicts (ST v6 + mem0's transformers floor resolve together); Tier-3 cascade behavior unchanged. If a conflict appears, STOP and surface it against the parallel mem0 2.2.1 stream (see Risks) — do not force-pin around it.

- [ ] **Step 5: INDEX row + commit (Platform)**

```bash
git add docs/architecture/decisions/ADR-090-multi-vector-rerank-tier.md docs/architecture/decisions/INDEX.md packages/core/pyproject.toml uv.lock
git commit -m "docs(adr)+chore(deps): ADR-090 multi-vector rerank tier; pin sentence-transformers >=6.1,<7"
```

**Acceptance criteria:** ADR with verified v6 API signatures + alternatives; pin landed; `uv pip check` clean; cascade tests green.

### Task 14: Core rerank module

**Files:**
- Create: `packages/core/narrare_core/embeddings/rerank.py`
- Test: `tests/unit/core/embeddings/test_rerank.py`

**Interfaces:**
- Consumes: ADR-090 verified ST v6 API; `ScoredCandidate` (scoring.py).
- Produces (Task 15/16 rely on exactly these):

```python
@dataclass(frozen=True, slots=True)
class RerankCandidate:
    source_id: UUID
    text: str
    hybrid_score: float

class Reranker(Protocol):
    async def score(self, query: str, candidates: Sequence[RerankCandidate]) -> list[float]: ...

class NullReranker:            # passthrough: returns hybrid scores
class MultiVectorReranker:     # ST v6, lazy import, asyncio.to_thread
def is_rerank_available() -> bool
async def rerank_candidates(
    candidates: Sequence[RerankCandidate], scores: Sequence[float], *, keep: int | None = None
) -> list[RerankCandidate]     # stable sort desc by score, optional top-keep
```

**Assigned layer/subagent:** NarrareCoreSpecialist · **Est. LOC:** ~180

- [ ] **Step 1: Write the failing tests** (no ST install required — fake-based per ADR-030):

`tests/unit/core/embeddings/test_rerank.py`:

```python
"""Unit tests for core/embeddings/rerank.py (ADR-090) — fake-based, no ST needed."""

from __future__ import annotations

from uuid import uuid4

from narrare_core.embeddings.rerank import (
    NullReranker,
    RerankCandidate,
    is_rerank_available,
    rerank_candidates,
)


def _candidate(text: str, hybrid: float) -> RerankCandidate:
    return RerankCandidate(source_id=uuid4(), text=text, hybrid_score=hybrid)


class TestNullReranker:
    async def test_returns_hybrid_scores_unchanged(self) -> None:
        candidates = [_candidate("a", 0.9), _candidate("b", 0.1)]
        scores = await NullReranker().score("q", candidates)
        assert scores == [0.9, 0.1]


class TestRerankCandidates:
    async def test_sorts_by_rerank_score_desc(self) -> None:
        candidates = [_candidate("a", 0.9), _candidate("b", 0.1), _candidate("c", 0.5)]
        ranked = await rerank_candidates(candidates, [0.1, 0.9, 0.5])
        assert [c.text for c in ranked] == ["b", "c", "a"]

    async def test_keep_truncates_after_sort(self) -> None:
        candidates = [_candidate("a", 0.9), _candidate("b", 0.1)]
        ranked = await rerank_candidates(candidates, [0.2, 0.8], keep=1)
        assert [c.text for c in ranked] == ["b"]

    async def test_stable_order_on_ties(self) -> None:
        candidates = [_candidate("a", 0.9), _candidate("b", 0.9)]
        ranked = await rerank_candidates(candidates, [0.5, 0.5])
        assert [c.text for c in ranked] == ["a", "b"]


class TestAvailability:
    def test_returns_bool(self) -> None:
        assert isinstance(is_rerank_available(), bool)

    def test_multivector_reranker_absent_extra_degrades(self) -> None:
        """When ST is missing, MultiVectorReranker construction raises ImportError
        with a pointed message (RULE-11 graceful degradation contract)."""
        import pytest

        from narrare_core.embeddings.rerank import MultiVectorReranker

        try:
            MultiVectorReranker()
        except ImportError as exc:
            assert "embeddings" in str(exc)
        else:
            # ST installed in this environment — availability must be True.
            assert is_rerank_available() is True
```

Run: `uv run --all-packages pytest tests/unit/core/embeddings/test_rerank.py -v` → FAIL.

- [ ] **Step 2: Implement `rerank.py`** (ST import ONLY here, lazy — RULE-08; scoring call via `asyncio.to_thread`; exact ST method names from ADR-090 Step 3):

```python
"""Optional local multi-vector rerank tier (ADR-090).

Post-retrieval stage over the existing dense first stage: pgvector top-K
-> rerank -> top-N. No index/schema change. ``sentence_transformers`` is
imported lazily and ONLY in this module; callers degrade to
``NullReranker`` when the ``embeddings`` extra is absent.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

logger = structlog.get_logger(__name__)

__all__ = [
    "MultiVectorReranker",
    "NullReranker",
    "RerankCandidate",
    "Reranker",
    "is_rerank_available",
    "rerank_candidates",
]


@dataclass(frozen=True, slots=True)
class RerankCandidate:
    """A retrieval candidate with its text (search rows carry no text — caller supplies)."""

    source_id: UUID
    text: str
    hybrid_score: float


@runtime_checkable
class Reranker(Protocol):
    """Contract for rerank scoring (RULE-03) — one score per candidate."""

    async def score(self, query: str, candidates: Sequence[RerankCandidate]) -> list[float]: ...


class NullReranker:
    """Degraded passthrough — preserves first-stage ordering signal."""

    async def score(self, query: str, candidates: Sequence[RerankCandidate]) -> list[float]:
        return [c.hybrid_score for c in candidates]


def is_rerank_available() -> bool:
    """True when the ``embeddings`` extra (sentence-transformers v6) is installed."""
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


class MultiVectorReranker:
    """Local reranker on sentence-transformers v6 ``MultiVectorEncoder``.

    Encoding runs in a worker thread (sync ST API -> ``asyncio.to_thread``).
    Constructor/signature per ADR-090 Step 3 (verified against installed v6).
    """

    def __init__(self, model_name: str | None = None) -> None:
        try:
            from sentence_transformers import MultiVectorEncoder
        except ImportError as exc:  # pragma: no cover - extra absent
            raise ImportError(
                "MultiVectorReranker requires the 'embeddings' extra "
                "(sentence-transformers>=6.1,<7)."
            ) from exc
        self._encoder = MultiVectorEncoder(model_name) if model_name else MultiVectorEncoder()

    async def score(self, query: str, candidates: Sequence[RerankCandidate]) -> list[float]:
        texts = [c.text for c in candidates]
        return await asyncio.to_thread(self._score_sync, query, texts)

    def _score_sync(self, query: str, texts: list[str]) -> list[float]:
        # Exact scoring call per ADR-090 Step 3 (e.g. encoder.rank/similarity API).
        raise NotImplementedError  # replaced verbatim by the ADR-recorded call in Step 2 execution
```

Executor note: the `_score_sync` body is filled with the EXACT call recorded in ADR-090 Step 3 — do not invent an API; if the v6 API differs from any sketch here, the ADR wins. (This is the only intentionally open line in the plan; its source of truth is the ADR produced two tasks earlier.)

- [ ] **Step 3: `rerank_candidates` implementation is fully specified by the tests** (stable sort by score desc, optional `keep`).

- [ ] **Step 4: Run → PASS; export from `embeddings/__init__.py`** (`Reranker`, `RerankCandidate`, `NullReranker`, `is_rerank_available`, `rerank_candidates`, `MultiVectorReranker` behind no conditional import — the module import itself never imports ST).

```bash
uv run --all-packages pytest tests/unit/core/embeddings -q
just check-architecture
```

- [ ] **Step 5: Commit (Platform)**

```bash
git add packages/core/narrare_core/embeddings/rerank.py packages/core/narrare_core/embeddings/__init__.py tests/unit/core/embeddings/test_rerank.py
git commit -m "feat(core/embeddings): optional multi-vector rerank tier — Reranker protocol, Null/MultiVector impls, graceful degradation (ADR-090)"
```

**Acceptance criteria:** contract + both impls + pure reorder function tested without ST installed; ST import confined to `rerank.py`; architecture gate green.

### Task 15: Backend wiring — optional rerank stage in `EmbeddingService.search`

**Files:**
- Modify: `packages/core/narrare_core/settings.py` (2 flag fields, ADR-090 D5)
- Modify: `apps/api/narrare/embeddings/service.py`
- Modify: `apps/api/narrare/embeddings/dependencies.py`
- Test: `tests/unit/api/embeddings/test_rerank_wiring.py`

> Sizing deviation note: 4 files, but two of them are 6-line declarations (settings fields + their only consumer wiring) in one atomic unit — splitting the settings addition from its sole consumer would leave dead settings fields. Total ≈140 LOC, within the LOC budget.

**Interfaces:**
- Consumes: `Reranker`/`RerankCandidate`/`rerank_candidates` (Task 14), `CoreSettings.embedding_rerank_enabled` (added here, ADR-090 D5), KB text lookup for candidates.
- Produces: when flag ON and extra installed: over-fetch top-K (`limit * 4`, capped 100) → fetch candidate texts → rerank → cut to `limit`. Flag OFF or extra absent: byte-identical current behavior.

**Assigned layer/subagent:** NarrareBackendSpecialist · **Est. LOC:** ~140

- [ ] **Step 1: Add the settings fields** (`packages/core/narrare_core/settings.py`, ADR-090 D5):

```python
    embedding_rerank_enabled: bool = Field(
        default=False, validation_alias="NARRARE_EMBEDDING_RERANK"
    )
    """ADR-090 pilot: local multi-vector rerank stage on embedding search."""

    embedding_rerank_model: str = Field(default="", validation_alias="NARRARE_EMBEDDING_RERANK_MODEL")
    """Rerank model name; empty = ADR-090 pinned default checkpoint (never the library default)."""
```

- [ ] **Step 2: Write failing service tests** (`tests/unit/api/embeddings/test_rerank_wiring.py`, fake reranker + fake repo following existing embeddings service test conventions):

Three cases:
1. `test_rerank_disabled_is_byte_identical` — flag off → search returns exactly today's ordering (hybrid rank), reranker never called.
2. `test_rerank_enabled_overfetches_then_cuts` — flag on, 10 candidates for `limit=3`: repo receives `limit * 4`; final result has 3 entries ordered by FAKE rerank scores (not hybrid order).
3. `test_rerank_enabled_without_extra_degrades` — flag on, `is_rerank_available()` monkeypatched False → behaves like case 1 (NullReranker path, no crash, warning-free or single debug log).

Run: `uv run --all-packages pytest tests/unit/api/embeddings/test_rerank_wiring.py -v` → FAIL.

- [ ] **Step 3: Implement** — `EmbeddingService.__init__` gains `reranker: Reranker | None = None` and `text_fetcher: Callable[[Sequence[UUID]], Awaitable[dict[UUID, str]]] | None = None` (both default None → all three existing construction sites unchanged). In `search()`, when both are present AND settings flag on: request `min(limit * 4, 100)` from the repo, build `RerankCandidate`s from fetched texts (candidates without text fall back to `NullReranker`-style hybrid score), `await reranker.score(...)`, `await rerank_candidates(..., keep=limit)`. `dependencies.py`: when `get_core_settings().embedding_rerank_enabled and is_rerank_available()` build `MultiVectorReranker(settings.embedding_rerank_model or None)` and a text-fetcher closure over the session + KB repository; else pass nothing.

- [ ] **Step 4: Run → PASS; regression**

```bash
uv run --all-packages pytest tests/unit/api/embeddings -q
```

- [ ] **Step 5: Commit (Platform)**

```bash
git add packages/core/narrare_core/settings.py apps/api/narrare/embeddings/service.py apps/api/narrare/embeddings/dependencies.py tests/unit/api/embeddings/test_rerank_wiring.py
git commit -m "feat(embeddings): optional local rerank stage in search — overfetch top-K, rerank, cut to top-N (ADR-090)"
```

**Acceptance criteria:** default-off invariance test; overfetch/cut behavior proven with a fake reranker; degradation path proven; other `EmbeddingService(...)` construction sites untouched.

### Task 16: Pilot measurement — rewrite-selection-derived retrieval comparison

**Files:**
- Create: `evals/rerank_pilot.py`

**Interfaces:**
- Consumes: `evals/datasets/rewrite_selection.py` dataset (ADR-032 substrate), `MultiVectorReranker`, `rerank_candidates`.
- Produces: `evals/results/rerank_pilot.json` — per-case rank of the instruction-relevant context block with vs. without rerank + summary (MRR / recall@3), per the plan's measurement contract.

**Assigned layer/subagent:** NarrarePlatformSpecialist · **Est. LOC:** ~150

- [ ] **Step 1: Implement the measurement script**

Structure (self-contained `python evals/rerank_pilot.py`):
1. Load the `rewrite_selection` dataset (selection_text + context_before/after + instruction per case).
2. Per case, build a candidate pool: the case's own context blocks (gold-relevant, labeled by position) + N distractor blocks sampled from OTHER cases' contexts (deterministic seed).
3. Score two orderings: (a) baseline = hybrid-score surrogate (lexical-overlap score computed deterministically — same for both arms), (b) rerank arm = `MultiVectorReranker` scores blended via `rerank_candidates`.
4. Emit metrics: mean reciprocal rank of gold blocks, recall@3, per-case deltas; write `evals/results/rerank_pilot.json` (`write_report_json`-style atomic write; reuse `evals/reports.py` helpers where they fit).

- [ ] **Step 2: Run with the extra installed**

```bash
uv run --all-packages python evals/rerank_pilot.py
```
Expected: report written; console summary. If the rerank arm underperforms on this substrate, record it honestly — the flag stays default-off either way (ADR-090 rollback = disable flag).

- [ ] **Step 3: Optional end-to-end signal (only if a provider key is available)**

```bash
NARRARE_EVAL_PROVIDER=zai NARRARE_EVAL_MODEL=glm-4-plus NARRARE_EMBEDDING_RERANK=1 \
  uv run --all-packages python -m evals run --suite rewrite_selection --mode runtime
```
Compare against the Task 12-era baseline report (`evals/results/rewrite_selection.json`). Note: the rewrite runtime task may not consume the embedding search path — if it does not, rely on the Step 2 retrieval measurement and say so in the report (do not fabricate an end-to-end claim).

- [ ] **Step 4: Commit (Platform) + phase gate**

```bash
git add evals/rerank_pilot.py evals/results/rerank_pilot.json
git commit -m "feat(evals): rerank pilot measurement — rewrite-selection retrieval comparison (ADR-090)"
just verify && just check-architecture
```

**Acceptance criteria:** deterministic, re-runnable measurement script; report artifact committed; explicit verdict recorded (rerank helps / neutral / hurts on this substrate).

---

## Phase 7 — F6 Verification + Docs Gate

### Task 17: Free-ride verification (graph caching, prices freshness)

**Files:** none (verification + notes that feed Task 18)

**Assigned layer/subagent:** NarrarePlatformSpecialist · **Est. LOC:** 0

- [ ] **Step 1: Agent graph caching (v2.51)** — run the agent suites and confirm no behavioral regressions; optionally note wall-time before/after on the slowest agent suite:

```bash
time uv run --all-packages pytest tests/unit/core/agents -q
```
Verdict for CURRENT_STATE: "agent graph caching (v2.51) adopted passively — suite green; per-request agent instantiation unaffected."

- [ ] **Step 2: `pydantic_ai.prices.update_in_background()` (v2.40)** — verify there is no consumer:

```bash
rg -n "pydantic_ai.prices|update_in_background|usage.cost" apps packages -g '*.py'
```
Expected: no matches — Narrare cost estimation is our own models.dev pipeline (`core/llm/cost_rates.py`, 24h TTL, `refresh_models()` on the settings router). **Verdict: DEFER/REJECT** — enabling it would add a background thread with zero consumers and double-source pricing data. Record the decision (this satisfies F6's "otherwise defer with a note").

- [ ] **Step 3:** no commit; findings go into Task 18's CURRENT_STATE entry.

### Task 18: Documentation gate — TECH_STACK, CURRENT_STATE, ADR statuses

**Files:**
- Modify: `docs/_shared/TECH_STACK.md` (pydantic-ai section)
- Modify: `docs/_shared/CURRENT_STATE.md` (new dated entry)
- Verify: `docs/architecture/decisions/INDEX.md` (ADR-089/090 rows current), `CHANGELOG.md` untouched (auto-generated by Release Please — entries come from this plan's Conventional Commits; verify the merge later produces the release notes)

**Assigned layer/subagent:** NarrareDocsSpecialist · **Est. LOC:** ~60

- [ ] **Step 1: TECH_STACK.md pydantic-ai section** — keep the major-version-commitment style, no patch numbers in prose. Concretely:
  - In `### pydantic-ai (v2.x, slim variant)`: append one sentence to the v2 migration notes: "The 2.5x line added `SelectModel`/`DecisionModel` capabilities; Narrare adopts them behind opt-in flags (ADR-089/090)."
  - Fix the stale sentence at the "Intent → Model routing" line (currently claims routing is defined in `core/llm/intents.py`): replace with "Intent → model tier guidance lives in `core/llm/intent_profiles.py` (advisory); the actual model resolves through the user routing cascade (`ModelRoutingResolver`, ADR-086 lazy resolution); dynamic per-step tier selection is an opt-in pilot (ADR-089)."
  - `### Supported LLM Providers` z.ai row already points at the two live-list SSOT files — no change needed beyond confirming `glm-5.3-flash` flows from them.
  - sentence-transformers: under the embeddings/mem0 sections, note the `embeddings` extra pins `>=6.1,<7` with the rerank tier (ADR-090) — major-line commitment style, no patch prose.

- [ ] **Step 2: CURRENT_STATE.md** — add a dated entry (2026-10-…) at the top summarizing: family bump 2.35.3→2.52.0 (+pydantic-evals lockstep), compat-walkthrough verdicts (incl. the accepted Anthropic `max_tokens` default change), F1 regression test, glm-5.3-flash registration, ADR-089 pilot (flag off), triage pilot + eval verdict, ADR-090 rerank tier (flag off) + measurement verdict, F6 verdicts (graph caching passive; prices deferred — no consumer), links to ADR-089/090 and this plan. Follow the established dense entry style.

- [ ] **Step 3: ADR statuses** — ADR-089 ✅ (after Task 8), ADR-090 ✅ after Task 15; INDEX rows consistent.

- [ ] **Step 4: Final gates**

```bash
just verify && just check-architecture && just check-ssot
```

- [ ] **Step 5: Commit (Platform)**

```bash
git add docs/_shared/TECH_STACK.md docs/_shared/CURRENT_STATE.md
git commit -m "docs: pydantic-ai 2.52 upgrade + feature pilots — TECH_STACK/CURRENT_STATE (ADR-089/090)"
```

**Acceptance criteria:** docs gates green; no hand-edit of `CHANGELOG.md`; all flags documented as default-off.

---

## Risks (top risks + mitigations)

1. **SelectModel ↔ Gateway boundary (F3, highest architectural risk).** Mitigation: design task (ADR-089) precedes implementation; callback only picks between two registry-built models (no factory/env access at selection time); default-off flag; pilot scoped to chat. Fallback if the verified 2.52 `SelectModel` API proves unsuitable: ADR-089 documents a minimal custom `Model` wrapper delegating per request — decision recorded before Task 7 proceeds.
2. **sentence-transformers v6 dependency surface vs mem0.** mem0 2.0.12+ requires `transformers>=5.3.0`; ST v6 sits on transformers v5 — expected coherent. But the **parallel mem0 2.0.18→2.2.1 work stream** may move `transformers`/`tokenizers` floors concurrently. Mitigation: Task 13 Step 4 runs `uv pip check` + the ADR-033 cascade tests; any conflict is escalated to the coordinator for a joint resolution (single `uv.lock`), never force-pinned in one stream.
3. **Anthropic `max_tokens` default change (2.52)** raises the unconfigured output ceiling 4×→16k on Sonnet 4.5+ (cost headroom, fewer truncations). Mitigation: conscious accept documented in Task 3 + CURRENT_STATE; users with configured output limits are unaffected (limit forwarded as `max_tokens`).
4. **pydantic-evals/slim pin drift.** Two separate pins must move together; the plan bumps both in one commit (Task 2) and `uv pip check` guards the resolution. Risk of a future Dependabot PR moving only one — mitigation: CURRENT_STATE entry states the family-jump rule explicitly.
5. **Triage pilot quality (F4).** Rubric severity may not beat self-reported severity. Mitigation: pilot measured via `consistency_staged` eval (Task 12); production wiring explicitly deferred until the eval verdict is positive — no user-visible path depends on it.
6. **Rerank latency on CPU (F5).** Local reranking adds per-search latency. Mitigation: overfetch cap (100), flag default-off, Task 16 measurement decides promotion; rollback = disable flag.
7. **TestModel API drift across 2.35→2.52** (`custom_output_args`, instrumentation API). Mitigation: every task that sketches TestModel/instrumentation calls includes a verify-the-installed-API step first; sketches name the verified alternative where known.

## Rollback Strategy

- **Pin commits (Tasks 2, 13):** revert the pin commit(s) and `uv sync --all-packages` — `uv.lock` travels with the revert. All features are additive on top, so a pin revert requires reverting or disabling everything above it in the phase order.
- **F1–F5 features:** each lands behind a default-off env flag (`NARRARE_LLM_DYNAMIC_TIERING`, `NARRARE_EMBEDDING_RERANK`) or an optional extra / eval-harness env — production rollback for any pilot is "flag stays off" or `git revert` of the single feature commit (each task is one commit, independently revertible).
- **No data/schema migrations anywhere in this plan** — nothing to roll back at the database level.

## Verification Matrix (per-phase summary)

| Phase | Gate |
|---|---|
| 0 | baseline `just test-unit` green on 2.35.3 |
| 1 | family bump; walkthrough verdicts; `just verify` + `just check-architecture` |
| 2 | OTel leak regression + negative control green |
| 3 | provider + fallback tests green |
| 4 | ADR-089 → core module tests → chat wiring tests; `just verify` |
| 5 | intent guards green; types/agent tests green; `consistency_staged` smoke + runtime report |
| 6 | ADR-090; `uv pip check`; cascade tests; rerank unit tests; wiring invariance test; pilot report |
| 7 | F6 verdicts; docs gates (`just verify`, `check-architecture`, `check-ssot`) |

**Total: 18 tasks.**
