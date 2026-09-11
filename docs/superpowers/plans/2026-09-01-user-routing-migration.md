# User-Routing Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all remaining dependency factories from the system-default model pattern (`build_system_default_config(SystemModelCategory.ANALYSIS)`, no user context, operator env only) to the per-user model-routing cascade (`ModelRoutingResolverImpl.resolve(intent, user_id, novel_id?)` → ResolvedModel with decrypted provider key), so every user-facing LLM capability serves the model/provider the user configured in the setup wizard.

**Architecture:** The target pattern is established and production-proven (19 files: `writing/summary_deps.py`, `deps_writing.py`, `deps_coauthor.py`, series deps...): dependency factory takes `user_id: str = Depends(get_current_user_id)` + session, resolves via `get_model_routing_resolver(session)`, awaits `resolver.resolve(LLMIntent.<intent>, UUID(user_id), novel_id?)` → `ResolvedModel(config, api_key)`, passes both to `ModelRegistry.get_model(config, api_key=...)`. Per-domain intents already exist in `LLMIntent` (the routers pass `context_mode`/feature ids). Each migration preserves the service constructor signatures except swapping `config`/`model` wiring — services themselves are untouched (RULE-06: routers delegate, services unchanged).

**Trigger:** KB-benchmark rehearsal finding #7 — the benchmark's build path 500s because kb-extraction ignores the user's wizard-configured provider (zai) and falls back to system-default anthropic with no operator key. 21 files across 9 domains remain on the legacy pattern.

**Tech Stack:** Existing infrastructure only — `ModelRoutingResolverImpl` (cascade: project intent → project category → user intent → user category → user default → ConfigurationError), `get_model_routing_resolver` factory, `LLMIntent` enum. No new modules in packages/core.

## Global Constraints

- **Regression-first per file:** before each migration, a failing unit test proving the factory now resolves via the resolver (fake resolver asserting intent + user_id + returned config/key flow into the registry call). The existing fake-session/fake-repo conventions in `tests/unit/api/` apply.
- **Pattern fidelity:** follow `writing/summary_deps.py` verbatim — Depends(get_current_user_id), resolver per-request, `await resolver.resolve(...)`, temperature overrides preserved via `dataclasses.replace(config, temperature=...)` where the legacy code set one (consistency deps sets temperature=0.3).
- **Cascade fallback is an ERROR when unconfigured:** resolver raises ConfigurationError if the user has no provider (cascade ends). Legacy endpoints with OPTIONAL auth (chat? verify per router) keep unauthenticated paths on the operator/system-default plane — verify per task; where a router is auth-mandatory, let ConfigurationError propagate as 4xx/5xx per existing error mapping.
- **Intent mapping:** each migrated dependency uses its REAL LLMIntent (the one its agents/prompt registry already use — check the service's intent, not the category). List per task below; verify against `llm/intents/_enums.py` and adjust if the service uses a different intent.
- **novel_id threading:** where the router has a novel_id path parameter, thread it into resolve() (project-level overrides — that's the cascade's top tier). Where not, resolve without it.
- **No service-signature churn:** factories build the same service objects; only model acquisition changes. If a service takes `config` + registry separately and internally calls get_model, prefer passing the resolved `ResolvedModel` model object directly if the service accepts it — otherwise pass config + api_key per the summary_deps pattern.
- **Operator plane stays:** `build_system_default_config` + its operator env (ADR-071 fallback) remain for SYSTEM services (wiki startup listeners, memory background) — migrate only request-scoped, user-facing dependencies. wiki/dependencies.py serves a user-facing refresh endpoint → migrate; the startup wiki listener (lifespan) stays operator-routed.
- Per-task caps: ≤3 files (dependency file + its test file + possibly router signature) / RULE-04 per-file limits; English; pyright strict; ruff.

---

### Task 1: kb domain (the benchmark's build path — extraction first)
Files: `kb/dependencies_extraction.py`, `kb/dependencies_improve.py`, `kb/dependencies_session.py`, `kb/dependencies_worldbuilding.py`, `kb/_consistency_deps.py` + tests. Split into 1a (extraction + improve: 2 files + tests) and 1b (session + worldbuilding + _consistency_deps) if needed for caps.
Intents: extraction → `LLMIntent.KB_EXTRACT` (verify: extraction service feature_id "kb_extract"); improve → KB intent used by KBImproveAgent; session (KB assist) → its intent; worldbuilding → its intent; _consistency_deps → the staged-consistency intents (fact_extractor + checker — TWO configs in consistency/deps.py style).
Routers: kb routers are auth-mandatory (novel-scoped) → thread novel_id where present.

### Task 2: analysis domain (8 files)
`dependencies.py` (sentiment? readability/pov — check which service), beta_reader, character_voice, coreference, voice_check, voice_drift, author_voice, author_voice_drift. Group 2a/2b/2c as needed. All ANALYSIS category → their real intents (ANALYSE-family). Auth-mandatory, novel-scoped.

### Task 3: consistency domain
`consistency/deps.py` — TWO configs (consistency_config temp 0.3, fact_extractor_config). Both migrate to resolver with their intents; temperature preserved via replace().

### Task 4: ai_assist + chat
`ai_assist/dependencies.py` + `_agent_runner.py` (runner takes config — migrate the dependency, runner signature if it must receive api_key/model); `chat/dependencies.py` — VERIFY chat auth posture (chat may have anonymous/optional path — if optional-auth, keep a system-default branch for the anonymous case, resolver for authenticated).

### Task 5: series domain (3 files)
`dependencies_voice.py`, `dependencies_consistency.py`, `dependencies_voice_drift.py` — novel-scoped (series novels), thread novel_id; intents per their services. NOTE: `dependencies_context_preview.py` and `dependencies.py` already migrated (in the 19).

### Task 6: memory + wiki
`memory/analysis_service.py` (request-scoped usage — verify; if it's a background/system path, DOCUMENT and leave, migrating only user-facing calls); `wiki/dependencies.py` (user-facing refresh, WRITING category → its intent; startup listener stays operator).

### Task 7: sweep + guard
- `rg build_system_default_config apps/api/narrare/ -l | grep -v test` → must list ONLY sanctioned survivors (the `_app/dependencies_services.py` definition + documented system services).
- A guard test pinning the survivor list (fails if a new file adopts the legacy pattern for a user-facing dependency — list-match against a sanctioned constant).
- Full gates: `just check`, targeted suites per touched domain; benchmark suite still 455+.

### Task 8: rehearsal re-run + docs
- Re-run the benchmark smoke (`--variant clean --mode incremental --capabilities CAP-IN-01,CAP-OUT-03`) WITH the operator env pins REMOVED from the config (set a flag or temporarily comment — the point: the USER path must now work). Verify extraction gets real zai candidates → entry ids → OUT-03 driven.
- CURRENT_STATE entry + ADR note: model-routing cascade now covers all user-facing dependencies (amend/extend the routing cascade ADR if one exists — check; else record in CURRENT_STATE + the resolver's module docstring).

---

## Plan Self-Review (executed)
- Coverage: 21 legacy files → tasks 1–6 (all enumerated); guard (7); validation via real rehearsal (8). Two special cases explicitly handled (chat auth posture, memory background vs user-facing).
- No placeholders: intents marked "verify" have a concrete verification step (read the service's intent/feature_id) — the migration pattern itself is fully specified via summary_deps.
- Type consistency: ResolvedModel/resolve() signatures per model_routing_resolver.py; api_key threading per ModelRegistry.get_model(config, api_key=...).
- Risk: some services may internally re-resolve via registry without api_key (like the setup bug) — Task 1a must TRACE the full path (factory → service → agent → registry call) and pass the key at the actual resolution point.
