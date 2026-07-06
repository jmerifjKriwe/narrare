<!-- Context: narrare-dev/constraints/rules | Priority: critical | Source: docs/_shared/CONSTRAINTS.md | Updated: 2026-06-21 -->

# Architecture Constraints — Rules Summary

**Core Idea**: 23 machine-enforced rules governing all Narrare code. Enforced via `scripts/check_architecture.py` (pre-commit + CI). Changes require ADR + PR approval.

**Reference**: `docs/_shared/CONSTRAINTS.md` (995 lines, full rationale + examples)

---

## Cardinal Rules (No exceptions without documented ADR)

### RULE-01b: Agents via NarrareAgent, Models via ModelRegistry
- `pydantic_ai.Agent` only in `core/agents/`
- Model/provider classes only in `core/llm/`
- No direct `openai`/`anthropic` imports anywhere; no HTTP calls to LLM endpoints
- Everywhere else: `from narrare_core.agents.base import NarrareAgent`

### RULE-02: Prompts built only in `core/prompts/`
- No f-string prompt assembly outside `core/prompts/`
- No cascade resolution logic outside `core/prompts/`
- Use `PromptComposer.build(intent=..., context=...)` everywhere else

### RULE-02a: Prompt Content Categories (ADR-026)
Three categories with distinct injection mechanisms. Wrong mechanism = RULE-02 violation:

1. **User-customizable content** — MUST go through `core/prompts/` cascade (PromptComposer).
   Includes: role descriptions, task instructions, output format specs, mode-specific instructions.
   Users can override via cascade (project/user/bundled). PromptComposer is the ONLY valid path.

2. **Architecturally guaranteed content** — MAY use `AbstractCapability.get_instructions()` in
   `core/agents/capabilities/`. Includes: fiction guidelines, conflict resolution, injection defense,
   meta-prompt identity. Must ALWAYS be present, NEVER user-customizable.
   Must load from canonical source (typically `core/prompts/_bundled/`) — no f-string assembly.

3. **Dynamic per-invocation content** — MAY use `@agent.instructions` or `AbstractCapability.for_run()`.
   Includes: KB data, style profiles, voice profiles. Varies per invocation (depends on Deps).
   Is data not instructions. Assembled from runtime data, not prompt templates.

### RULE-02b: Prompt-Resolution-Path Compliance (ADR-046)
Prompt-Resolution is exclusively the responsibility of `core/prompts/`. No
app-layer module may load, resolve, substitute, or construct prompts directly.
RULE-02 governs the assembly METHOD, RULE-02a the content CATEGORY, RULE-02b
the resolution PATH. What constitutes a violation:

1. **Direct `PromptRegistry` access outside `core/prompts/`** — apps/ or
   agents/ calling `PromptRegistry.resolve()` instead of `PromptComposer.build()`.
2. **App-layer prompt loaders** — files in `apps/` that load templates from disk
   (`importlib.resources`, `Path.read_text()`) and do manual `.replace()`/`.format()`
   variable substitution. App layer must delegate to core, not reimplement cascade.
3. **Feature prompts injected into user-channel** — resolving a feature system
   prompt via PromptComposer but concatenating `composed.system` into the user
   prompt instead of passing it as agent system/instructions.
4. **Inline fallback prompts in production code** — hardcoded prompt string used
   as degraded fallback when PromptComposer fails/unavailable. Production must
   fail-fast on config errors.
5. **`MetaPromptLoader` usage outside `core/prompts/` and `core/agents/capabilities/`** —
   `core/prompts/` internal that must not be imported by agents, services, graph helpers.

**Enforcement boundary:** `core/prompts/` is the ONLY module that may import
`PromptRegistry`, load `_bundled/` template files, perform `{{variable}}`
substitution, or cascade-resolve prompts. Approved exceptions are dual-registered
in `pyproject.toml [tool.narrare.architecture]` with inline
`# narrare: allow-prompt-path reason="..."` comments (ADR-028).

### RULE-03: Contracts before implementation
- Every service needs a `Protocol` in `contracts.py` or `_types.py` FIRST
- Enables mocking, testing, client-switching (MCP/A2A/CLI)
- **Cross-feature contracts**: When a feature consumes data from another feature, an Integration
  Contract MUST define behavior on data change/deletion. Documents: shared data + direction,
  change behavior (propagated/stale/blocked), deletion behavior (cascade/nullify/block),
  expected version/schema. Enforced during Stage 2.5 (Semantic Review).

### RULE-04: Split before you squeeze — hard file limits

| File type | Hard limit | Soft target |
|-----------|-----------|-------------|
| Any Python module | 400 lines | 250 lines |
| Router file | 150 lines | 80 lines |
| Service file | 300 lines | 200 lines |
| Agent definition | 200 lines | 150 lines |
| Test file | 400 lines | 300 lines |
| Config / schema | 200 lines | 150 lines |

Approaching limit → extract a new module. NEVER compress code to fit.

**Split strategy:**
- **Routers:** one file per resource sub-group (`router_sessions.py`, `router_drafts.py`)
- **Services:** extract focused sub-services (`draft_service.py`, `session_service.py`)
- **Agents:** separate system prompt logic / tool definitions / run logic

**Explicitly FORBIDDEN:** removing whitespace, shortening names, collapsing multi-line expressions, code golf.

### RULE-15: No `middleware.ts` — use `proxy.ts`
- Next.js 16+ uses `packages/web/proxy.ts` exclusively
- `middleware.ts` anywhere in `packages/web/` causes hard build failure
- Includes `packages/web/src/middleware.ts` and all subdirectories

---

## Structural Rules

### RULE-05: Module boundaries are ownership boundaries
- Each domain module owns its own: DB models, Pydantic schemas, service contracts, service
  implementations, router, tests
- No cross-domain `_internal` imports
- Cross-domain communication through public `__init__.py` exports only

### RULE-06: One responsibility per file
- Each file has exactly one role: router/service/repository/schema/contract/model/agent/config/utils
- Routers **delegate immediately** to services — no business logic in routers
- Services **delegate DB operations** to repositories — no raw SQLAlchemy in services

### RULE-07: Dependency direction is one-way
- `router → service → repository → database`
- Arrows point down only. Repository never imports service. `core/` never imports `apps/`.
- Services access `core/llm/gateway` and `core/prompts/composer` via DI

### RULE-08: All external integrations abstracted
- PostgreSQL: `*/repository.py` only | Redis: `core/cache/client.py` only
- pgvector: `core/embeddings/store.py` only | mem0: `core/memory/client.py` only
- SMTP: `core/notifications/email.py` only | Web search: `core/research/search_client.py` only
- Langfuse: not allowed in core runtime (ADR-031) | OpenTelemetry: `_app/telemetry.py` + approved Pydantic-AI runtime instrumentation only
- Event bus: `apps/api/.../events.py` only

### RULE-14: Every model column needs a migration
- Column add/rename/type-change/remove requires Alembic migration in same task
- Model change without migration = build failure
- Cross-table check: when adding column to one table in a shared concern, check ALL tables

### RULE-18: No hardcoded configuration in routers
- No hardcoded provider names, model IDs, API keys in router endpoints
- All runtime config via DI or settings cascade (`resolve_ai_settings`)
- Regression test: `test_generation_router_contract.py`

### RULE-18b: Configuration Effect Integrity (ADR-051)
- RULE-18 governs WHERE config is resolved; RULE-18b governs WHETHER the resolved value takes effect at the runtime boundary with regression proof.
- A configurable value is not "implemented" until its resolved value is consumed at the runtime boundary it affects, with a test proving changed value → changed effect (or documented warning/error).
- Every material setting needs a Configuration Adoption Matrix row (`docs/architecture/governance/configuration-adoption-matrix.yaml`) with exactly one lifecycle classification (adopted / governed_default / operator_default / covered_by_existing / not_applicable).
- `user`/`project` classifications require `runtime_consumer` + `enforcement_evidence`; `adopted` requires `enforcement_evidence`. No exposed setting without a runtime consumer; no "implemented" claim without regression evidence.
- Governed code defaults are allowed only with rationale, owner, tests, and review trigger.
- Enforced by `check_configuration_matrix.py` (CI-blocking) + review-finding coverage gate. See CONSTRAINTS.md RULE-18b.

### RULE-19: Dependency factories use `SessionDep`, not bare `AsyncSession`
- Bare `AsyncSession` treated as query param by FastAPI → 422 in production
- Always use `SessionDep` = `Annotated[AsyncSession, Depends(get_async_session)]`

---

## Quality Rules

### RULE-09: Every public function has type signature
- Return type annotation mandatory. `Any` forbidden except approved adapters.
- Enforced by `mypy --strict` + `pyright`

### RULE-10: Tests are not optional
- Every service method → unit test. Every endpoint → integration test.
- Coverage: `core/` ≥ 90%, `apps/api/` ≥ 80%
- Test naming mirrors source: `core/prompts/composer.py` → `tests/unit/core/prompts/test_composer.py`
- Tests live in `tests/unit/` and `tests/integration/` — never in source packages

### RULE-11: No silent failures
- Every `except` block re-raises, logs with structlog, or converts to domain error
- Bare `except: pass` = build failure

### RULE-16: i18n namespace registration
- Every `useTranslations("X")` needs `"X"` in `request.ts` namespaces array
- AND `X.json` must exist in all 3 locale dirs (`en`, `de`, `fr`)
- Regression test: `i18n-namespace-registry.test.ts`

### RULE-17: API-Frontend contract consistency
- Pydantic response schema field names must exactly match TypeScript interface names
- Backend/frontend type updates must be in same commit
- Regression test: `test_prompt_contract.py`

---

## Implementation Quality

### RULE-20: No half-implementations
- Build properly or don't build. Each increment must be complete and tested.
- Forbidden: "Phase 1 only" without Phase 2, stub implementations, missing error handling,
  skipped migrations, feature flags for incomplete features, deferred streaming
- Incremental path acceptable if each step is a complete working subsystem

### RULE-21: Architecture review invalidated by material plan changes
- Material changes (new files/modules, boundary changes, new deps, API changes) require re-review
- Coordinator must include `CHANGES FROM PREVIOUS REVIEW` section when resubmitting
- Non-material: typos, formatting, rewording, line count corrections

### RULE-22: Cross-Feature Coherence Gate
- Any feature sharing data with other features must pass coherence check before merge
- **Checklist:**
  1. Shared data identification — list all shared sources explicitly
  2. Change/deletion behaviour — propagated? cached? breaks consumer?
  3. Intent/prompt semantic check — no duplicate `LLMIntent` IDs with different scope
  4. Variable registration — new template vars in `variable_registry.USER_CONTENT_VARS`, `SYSTEM_VARS`, or `FEATURE_DYNAMIC_VARS`
   5. i18n parity — bundled feature prompts are EN-only by default (ADR-026 Phase 5); declared localized families (meta, universal) must have all declared locale variants
  6. User-content variable registration — user-authored content vars MUST be in
     `variable_registry.USER_CONTENT_VARS` and wrapped with approved XML tags
- Enforced by Architecture Specialist during Stage 2 (Specification) and Stage 2.5 (Semantic Review)

### RULE-23: No undisciplined type suppressions
- `# type: ignore` is a last resort, not a workaround tool — no naked suppressions, no suppress-and-forget, no silencing instead of fixing
- **Requirements:**
  1. Every suppression MUST include a specific error code — bare `# type: ignore` (suppresses ALL errors) is forbidden
  2. `arg-type` / `call-arg` to silence Mock/fake protocol violations is forbidden — fakes MUST implement the Protocol (see RULE-TEST-01)
  3. `union-attr` / `assignment` is forbidden — use `isinstance()` narrowing or `cast()` instead
  4. Every permitted suppression MUST carry an inline reason comment (`# reason: ...`) explaining why + removal condition
  5. Permitted error codes: `import-untyped` / `reportMissingTypeStubs` (no stubs), `attr-defined` (dynamic third-party attrs); all others require architecture-review exception
  6. Ratchet principle — suppression count must not increase vs. baseline (`pyproject.toml [tool.narrare.architecture.type_ignore_baseline]`); a PR that increases the count is blocked
- Enforced by `check_architecture.py` — `# type: ignore` scan + baseline comparison in CI

---

## Future-Compatibility

| Rule | Summary |
|------|---------|
| RULE-12 | Service Layer is the only public API. WebUI/MCP/A2A/CLI are all clients — they never call each other |
| RULE-13 | Streaming and non-streaming share one interface (`stream: bool = False`) |

---

## Enforcement

| Rule | Enforced by |
|------|-------------|
| RULE-01b imports | `check_architecture.py` — import scan |
| RULE-01b instantiation | `check_architecture.py` — AST scan (Agent(), .run(), .run_sync()) |
| RULE-01b LLM URLs | `check_architecture.py` — string scan |
| RULE-02 prompt building | `check_architecture.py` — AST scan |
| RULE-02a content categories | `check_architecture.py` — AST scan (Capability f-string) + PR review |
| RULE-02b prompt-resolution-path | `check_architecture.py` — AST scan (registry access, app-layer loaders, user-channel injection, inline fallbacks, off-scope MetaPromptLoader) + PR review |
| RULE-04 file size | `check_architecture.py` — line count |
| RULE-06 router purity | `check_architecture.py` — complexity heuristic |
| RULE-09 type signatures | `mypy --strict` + `pyright` in CI |
| RULE-10 test coverage | `pytest --cov` with minimum thresholds |
| RULE-11 silent failures | `check_architecture.py` — bare except scan |
| RULE-14 model-migration | Integration tests + PR review |
| RULE-15 no middleware.ts | `check_architecture.py` — file existence scan |
| RULE-16 i18n | `i18n-namespace-registry.test.ts` + `validate-i18n.ts` |
| RULE-17 API-Frontend | `test_prompt_contract.py` + PR review |
| RULE-18 no hardcoded config | `test_generation_router_contract.py` + PR review |
| RULE-18b configuration effect integrity | `check_configuration_matrix.py` (CI-blocking matrix + review-finding coverage gate) + PR review |
| RULE-19 SessionDep | `check_architecture.py` — AST scan bare AsyncSession |
| RULE-20 no half-implementations | PR review by Architecture Agent + test coverage audit |
| RULE-22 coherence gate | Stage 2.5 Semantic Review by Architecture Specialist |
| RULE-23 type suppressions | `check_architecture.py` — `# type: ignore` scan + baseline comparison |
| All rules | PR review by Architecture Agent |

---

## Approved Exceptions (14)

**Canonical source:** `pyproject.toml [tool.narrare.architecture.exceptions]` — machine-readable.
This section mirrors it. Both MUST be kept in sync. See ADR-028.

Every exception requires: (1) registered in `pyproject.toml`, (2) documented here,
(3) inlined as `# narrare: allow` comment in source file.

### RULE-01 Exceptions (direct LLM/client access)

| # | File | Reason |
|---|------|--------|
| 1 | `packages/core/narrare_core/llm/embedding_providers.py` | Batch embedding API needs direct client for performance |
| 2 | `packages/core/narrare_core/memory/mem0_client.py` | mem0 AsyncMemory needs own LLM client for memory extraction |
| 5 | `packages/core/narrare_core/wiki/agent.py` | WikiGenerationAgent uses RunContext for pydantic_ai internals |
| 6 | `packages/core/narrare_core/wiki/agent_chapter.py` | WikiChapterGenerator wraps internal PydanticAgent (ADR-015) |
| 13 | `apps/api/narrare/setup/provider_service.py` | Setup-phase provider validation needs direct Agent import (ADR-015) |

### RULE-01b Exceptions (Agent instantiation)

| # | File | Reason |
|---|------|--------|
| 4 | `packages/core/narrare_core/planning/remap.py` | Injected agent, not instantiated here |
| 7 | `packages/core/narrare_core/wiki/agent_chapter.py` | WikiChapterGenerator wraps PydanticAgent (ADR-015) |
| 12 | `packages/core/narrare_core/llm/gateway.py` | Gateway._make_agent() is the approved boundary crossing (ADR-015) |
| 14 | `apps/api/narrare/setup/provider_service.py` | Setup-phase provider validation needs direct Agent (ADR-015) |

### RULE-TEST-01 Exceptions (test mocking without domain contract)

| # | File | Reason |
|---|------|--------|
| 8 | `tests/unit/api/memory/test_analysis_service.py` | Mocking for service unit tests |
| 9 | `tests/unit/api/memory/test_feedback_service.py` | Mocking for service unit tests |
| 10 | `tests/unit/api/memory/test_repository.py` | Mocking for repository unit tests |
| 11 | `tests/unit/api/metrics/test_metrics_router.py` | Mocking SQLAlchemy Engine |

---

## SSOT Hierarchy (Section 8)

**When a derived source contradicts the authoritative source, the authoritative source wins.**
Derived sources MAY reference but MUST NOT reproduce, paraphrase, or contradict rules.

| Topic | Authoritative Source | Derived Sources (reference only) |
|-------|---------------------|----------------------------------|
| Architecture rules (RULE-XX) | `docs/_shared/CONSTRAINTS.md` | `AGENTS.md`, `.opencode/context/`, `coding-standards.md` |
| Technology versions | `docs/_shared/TECH_STACK.md` | README, `deployment-guide.md`, devcontainer config |
| Architecture decisions | `docs/architecture/decisions/ADR-*.md` | `AGENTS.md`, feature specs |
| Feature specifications | `docs/features/{domain}/{id}.md` | Implementation code |
| Coding standards | `docs/development/coding-standards.md` | `.opencode/context/examples/` |
| Testing standards | `docs/development/testing-standards.md` | `.opencode/context/examples/` |
| UI principles | `docs/development/ui-principles.md` | `.opencode/context/concepts/` |
| Glossary | `docs/_shared/GLOSSARY.md` | All other docs |
| Module structure | `docs/reference/directory-structure.md` | `AGENTS.md`, `.opencode/context/domain/module-map.md` |
| Agent instructions | Root `AGENTS.md` | `apps/api/AGENTS.md`, `packages/core/AGENTS.md`, `tests/AGENTS.md` |

**Derived source rules:** Reference not reproduce. Never contradict. Code examples are illustrative.
Sub-AGENTS.md may add context-specific guidance but may NOT relax rules. Path references must resolve.

---

**Related**: `lookup/adr-index.md`, `lookup/current-state.md`
