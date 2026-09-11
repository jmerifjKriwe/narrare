# Pydantic-AI Follow-Ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Close the two standing follow-ups from the structural fixes plan: (1) the 4 core-agent kwargs pass-through boundaries (writing_graph, BetaReader phase2, Worldbuilder phase2, WikiGenerationAgent), (2) usage_limits threading on all non-extraction prepare() paths that currently pass None.

**Architecture:** The core agents need `model_settings`/`usage_limits` kwargs on their run methods (2-line mechanical changes, forwarded to the internal agent.run()). The services need a `DefaultRunLimitResolver` injected and called before prepare() — the extraction service (commit f35c4568) is the pattern.

## Global Constraints
- Core agent changes: packages/core — Core specialist.
- Service changes: apps/api — Backend specialist.
- English; pyright strict; ruff clean; zero type-ignores.
- Full suite green after each task.

### Task 1: Core agent kwargs pass-through (4 agents) — Core specialist
`packages/core/narrare_core/agents/`:
1. `writing_graph_prompts.py` — the helper at line ~55 constructs an Agent and calls run(); it (or its 5 callers in writing_graph.py) need model_settings/usage_limits threading.
2. `beta_reader_agent.py` — `run_phase2` needs kwargs pass-through (like run_phase1 from 6d).
3. `worldbuilding_agent.py` — `run_phase2` needs kwargs pass-through (from 6c).
4. `wiki/agent.py` (or wherever WikiGenerationAgent lives) — run/generate method needs kwargs pass-through (from 6d).

Method: add `model_settings: ModelSettings | None = None, usage_limits: UsageLimits | None = None` params → forward to the internal pydantic-ai agent.run(). Unpin the boundary tests (currently skipped, expecting these params). Services that already have the prepared triple can now pass it.

### Task 2: Wire the prepared triple through to the 4 core agents — Backend specialist
The callers of these agents (writing_graph.py, beta_reader_service, worldbuilding_analyzer, wiki service) now pass `prepared.model_settings` + `prepared.usage_limits` to the agent calls.

### Task 3: usage_limits threading on all None paths — Backend specialist
Every service that calls `registry.prepare(..., usage_limits=None)` needs a `DefaultRunLimitResolver`:
- Inject `run_limit_resolver: DefaultRunLimitResolver` (None-defaulted, same pattern as extraction_service).
- Resolve: `resolved = self._run_limit_resolver.resolve(config=self._config, budget=None, invocation_id=uuid4())`.
- Pass: `registry.prepare(..., usage_limits=resolved.usage_limits)`.
- Services: analysis runners (3 voice), analysis services (readability, pov, coreference, beta_reader), planning (4), writing (2), memory, wiki, series (2), ai_assist, chat (already resolver-owned), kb worldbuilding/assist/improve/merge.

### Task 4: Sweep + guard update + CURRENT_STATE
- `rg -rn "usage_limits=None" apps/api/narrare/ | grep -v test` → only legitimate Nones (e.g., fallback paths).
- Update the prepare-coverage guard if needed.
- CURRENT_STATE entry.
- Benchmark rehearsal re-run.
