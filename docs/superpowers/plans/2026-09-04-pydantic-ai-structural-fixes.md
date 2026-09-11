# Pydantic-AI Structural Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Universal (provider-agnostic) structural fixes for Narrare's pydantic-ai integration, INCLUDING all auxiliary findings from the architecture audit: (1) tool-schema `$ref` inlining, (2) proper provider classes, (3) intent-aware thinking policy, (4) centralized runtime-settings assembly on ModelRegistry, (5) the 29 uncovered agent.run() call paths that never receive model_settings.

**Architecture:** These are ROOT-CAUSE fixes — not provider patches. The core insight: runtime-settings assembly is fragmented across 4 pipelines and most agent services never receive model_settings at all. The fix centralizes everything into a single `ModelRegistry.prepare(config, intent, usage_limits)` that produces (model, model_settings, usage_limits) as a coherent triple — every call site uses it.

**Analysis bases:**
- `.superpowers/sdd/2026-08-27-kb-benchmark-package3-runner/architecture-pydantic-ai-structural.md` (pydantic-ai structural audit)
- `.superpowers/sdd/2026-08-27-kb-benchmark-package3-runner/architecture-dual-output-analysis.md` (the 29 uncovered agent.run() sites)

**Tech Stack:** Python, pydantic-ai 2.31.0, existing Narrare agent infrastructure.

## Global Constraints

- Universal fixes ONLY — no `if provider_name == "X"` branching in the new code.
- The existing zai-specific fixes (`_ZAI_MODEL_PROFILE`, `thinking="low"` in `_model_settings.py`) are REPLACED, not extended.
- pydantic-ai API verified from the installed version — no doc-based assumptions.
- Per-task caps: ≤3 files / ≤250 LOC per delegation (split if needed).
- English; pyright strict; ruff clean; zero type-ignores.
- Full suite green after each task (`uv run pytest tests/unit/ -q`).

---

### Task 1: Schema-inlining transformer (universal)
Create `packages/core/narrare_core/llm/_schema_transformer.py` with `NarrareOpenAICompatJsonSchemaTransformer(OpenAIJsonSchemaTransformer)` that flips `prefer_inlined_defs=True` post-init. Inject via `Model(profile=...)` hook in every OpenAI-compat factory.

Files: `packages/core/narrare_core/llm/_schema_transformer.py` (new), `packages/core/narrare_core/llm/_providers/zai.py` (inject), tests.

### Task 2: Provider classes + openrouter cap fix
Replace generic `OpenAIProvider(...)` with pydantic-ai's own provider classes (`ZaiProvider`, `OllamaProvider`, `OpenRouterProvider` — all accept `openai_client=` so ADR-060 retry survives). Add registry-level capability fragments for deltas upstream doesn't set. Fix the openrouter silent output-cap drop.

Files: `packages/core/narrare_core/llm/_providers/zai.py` (refactor), possibly `_providers/openrouter.py` (fix), tests.

### Task 3: Intent-aware thinking policy
Create `packages/core/narrare_core/llm/thinking_policy.py` with a declarative `INTENT_CATEGORY_THINKING_LEVELS` table: extraction/KB → `"low"`, analysis/research/planning → `"medium"`, writing/chat → omit. Refactor `build_runtime_model_settings` to accept `intent` and use the table. DELETE the zai-specific branch.

Files: `packages/core/narrare_core/llm/thinking_policy.py` (new), `_model_settings.py` (refactor), tests.

### Task 4: Centralized ModelRegistry.prepare()
Add `ModelRegistry.prepare(config, intent, usage_limits=None) -> PreparedModelCall` where `PreparedModelCall` is a NamedTuple/dataclass holding (model, model_settings, usage_limits). This is THE single assembly point:
- resolves the model (get_model with credentials)
- builds runtime model_settings (thinking policy + cache settings + usage limits)
- returns the coherent triple

Every call site that currently does `get_model()` + separately builds `model_settings` migrates to `prepare()`. The extraction service's duplicate `get_model` fix falls out naturally.

Files: `packages/core/narrare_core/llm/gateway.py` (add prepare), `packages/core/narrare_core/llm/_prepared_call.py` (new types), tests.

### Task 5: Migrate extraction service to prepare()
`extraction_service.py` migrates to `registry.prepare(config, intent=LLMIntent.KB_EXTRACT, usage_limits=resolved.usage_limits)` — kills the duplicate get_model call AND ensures model_settings always flow. This is the pattern-setting migration.

Files: `apps/api/narrare/kb/extraction_service.py` (refactor), tests.

### Task 6: Migrate the 29 uncovered agent.run() call paths
The audit found 29 call paths that pass NO model_settings to agent.run() — thinking/caps/cache never reach them. These migrate to `registry.prepare()` + pass the triple. This is the biggest task — split by domain:

6a: analysis runners (5 agents) + analysis services (3)
6b: consistency (3) + planning (4)
6c: writing (2) + kb remaining (4: worldbuilding, assist, improve, merge)
6d: ai_assist + chat + series (2) + memory + setup + wiki

Files: the 29 service/runner files + their tests. Each sub-task ≤3 files.

### Task 7: Sweep + guard + gates + CURRENT_STATE
- Verify: no `provider_name == "zai"` conditionals in `_model_settings.py` or `thinking_policy.py`.
- Verify: schema transformer applied in every OpenAI-compat factory.
- Verify: no bare `agent.run()` without model_settings remains (sweep + guard test).
- Full gates: `just check`, `just test-unit`, pyright, ruff, architecture.
- CURRENT_STATE + memory.
- Rehearsal re-run.

---

## Plan Self-Review (executed)
- Coverage: all three audit recommendations + openrouter fix + duplicate get_model + 29 uncovered paths + centralized assembly + sweep/rehearsal.
- Universal-only constraint enforced.
- Task 6 is the volume task — split into 4 sub-tasks by domain, each ≤3 files.
- The `prepare()` API is the structural keystone — it makes it impossible to forget model_settings (the API doesn't let you get a model without getting the settings too).
