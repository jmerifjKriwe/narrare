<!-- Context: narrare-dev/processes/quality-gates | Priority: high | Source: docs/development/testing-standards.md | Updated: 2026-07-06 -->

# Quality Gates

What must pass before code is considered "done." Every gate must pass for a feature to reach `status: stable`.

---

## Gate 1: Test Level Gates

| Level | Location | Scope | Time Target | Requirement |
|-------|----------|-------|-------------|-------------|
| **Unit** | `tests/unit/` | Fast, pure, no I/O | < 5s total | Every public service method: 3+ tests (happy path, domain error, edge case) |
| **Integration** | `tests/integration/` | Real DB (PostgreSQL/pgvector), mocked LLM | < 60s total | Every repository method + router endpoint (200/201 schema validation, 401, 404, 422) |
| **E2E** | `tests/e2e/` | Full stack, Playwright | < 5min total | Critical user flows. Main branch CI only |

**Never** use a real DB in unit tests. **Never** mock the DB in integration tests.

---

## Gate 2: Coverage Minimums

| Module | Level | Min | Target |
|--------|-------|-----|--------|
| `core/llm/`, `core/prompts/` | Unit | 95% | 100% |
| All other `core/` | Unit | 90% | 95% |
| `apps/api/*/service.py` | Unit | 85% | 90% |
| `apps/api/*/repository.py` | Integration | 80% | 90% |
| `apps/api/*/router*.py` | Integration | 80% | 85% |
| i18n namespace registry | Integration | 100% | 100% |

Coverage below minimum = CI failure. No exceptions.

---

## Gate 3: Architecture Constraint Gate

- Runs `scripts/check_architecture.py` as a pytest test
- Enforces the rules reported by `python scripts/check_architecture.py --list-rules`
  (see the `ENFORCED_RULES` constant — do not maintain a separate list here)
- Fails on: wrong import locations, file size violations, bare except, wrong `middleware.ts`

---

## Gate 4: Fake Conformance Gate

- Location: `tests/unit/test_fake_conformance.py`
- Every Fake class verified via `isinstance()` against its `@runtime_checkable` Protocol
- When adding a new Fake, add a conformance test

---

## Gate 5: Cross-Layer Contract Gates

| Test | Rule | File Pattern | What It Catches |
|------|------|-------------|-----------------|
| i18n namespace registry | RULE-16 | `packages/web/__tests__/i18n-namespace-registry.test.ts` | Missing namespace in `request.ts` |
| API response contracts | RULE-17 | `tests/unit/api/test_*_contract.py` | Frontend/backend field name drift |
| Router configuration | RULE-18 | `tests/unit/api/test_*_router_contract.py` | Hardcoded provider/model strings |

---

## Gate 6: Type Checking

- `pyright` in CI (RULE-09); pyright is the sole type checker (no other checker configured)
- **Two scopes:** the main config (`pyproject.toml`, strict) covers production code (`apps/`, `packages/`, `scripts/`) and excludes `tests/` for performance; test files are type-checked by `tests/pyrightconfig.json` (basic mode) via the pre-commit `pyright-tests` hook AND the `just check` gate (step "Typecheck (Tests)", also runnable as `just typecheck-tests`)
- No untyped public functions
- `Any` forbidden except in approved adapters

---

## Gate 7: CI Summary

The full CI pipeline runs these gates in order. See `.github/workflows/ci.yml`
for the authoritative source.

### Gate Status in CI

> Authoritative source: `.github/workflows/ci.yml`. The job/gate mapping below can drift;
> verify against the workflow file for the current set and blocking behavior.

| # | Gate | CI Status | Notes |
|---|------|-----------|-------|
| 1 | `ruff` format + lint | ✅ Blocking | `lint` Job |
| 2 | `check_architecture.py` | ✅ Blocking | `architecture` Job |
| 3 | `check_exception_baseline.py` | ✅ Blocking | `architecture` Job |
| 4 | `check_adoption.py` + `check_prompt_structure.py` | ✅ Blocking | `architecture` Job — adoption PASS requires runtime-adopted evidence where required (ADR-045) |
| 4a | `check_prompt_surface.py` (ADR-037) | ✅ Blocking | `architecture` Job — P0 Prompt Surface Manifest conformance |
| 5 | `check_streaming_compliance.py` (RULE-20) | ✅ Blocking | `architecture` Job |
| 6 | `check_locale_sync.py` | ✅ Blocking | `architecture` Job (previously: warning) |
| 7 | `check_doc_drift.py` | ✅ Blocking | `architecture` Job |
| 8 | `export_openapi.py --check` | ✅ Blocking | `architecture` Job |
| 9 | `pyright` | ✅ Blocking (full, strict) | `pyright` in CI aktiv (RULE-09). Pyright is the sole type checker. Runs in the `typecheck` job with no `continue-on-error`. |
| 10 | `pytest` unit tests | ✅ Blocking | `test-unit` Job |
| 11 | Coverage threshold | ✅ Blocking (≥80%) + Modul-Ratchet | Global `--cov-fail-under=80` (`ci.yml`) + `check_module_coverage.py --fail` (RULE-10 Targets) + ratcheted Baselines (`scripts/coverage_baselines.json`, siehe `_coverage_model.py`) |
| 12 | `pytest` integration tests | ✅ Blocking | `test-integration` Job |
| 13 | `pnpm test` (frontend) | ✅ Blocking | `frontend` Job |
| 14 | `bandit` + `pip-audit` | ✅ Blocking | `security` Job |

### Coverage-Gate (Global 80% + Regelbasierte Modul-Schwellen + Ratchet)

**Entscheidung:** Der `test-unit` Job erzwingt global `--cov-fail-under=80`
(harte Schwelle, blocking). Anschließend prüft `scripts/check_module_coverage.py
--fail` die modularen RULE-10-Targets aus `docs/_shared/CONSTRAINTS.md` (Core
90% bzw. 95% für `llm`/`prompts`, API 80%, shared 80%) als harte Untergrenze
und zusätzlich einen Ratchet (`scripts/coverage_baselines.json`): ein Modul,
das zwischenzeitlich deutlich über seinem Target lag, wird gegen seinen
High-Water-Mark geprüft – ein Rückfall unter die Baseline (aber noch über dem
Target) liefert eine `REGRESSION`-Warning. Der `--update-baselines`-Aufruf
wird durch einen Subset-Guard in `_coverage_model.py::save_baselines` davor
bewahrt, die Baselines bei versehentlich reduziertem Scope stillschweigend zu
verwerfen (siehe `_audit/results/technical-review/review-02-testing.md`
AUFG-02-05).

**Frühere Übergangsausnahme `coverage-threshold`:** Resolved am 2026-06-14
(`scripts/gate-exceptions.json`). Damals galt ein temporärer 60%-Hard-Floor;
die Aufhebungsbedingung (Coverage stabil ≥ 80% global + modulare Schwellen
in CI aktiv) ist erfüllt.

### Additional CI-only Gates

These checks run in CI but are not part of the numbered gate system:

| Check | CI Status | Notes |
|-------|-----------|-------|
| `check_frontend_file_size.py` (RULE-04) | ✅ Blocking | `frontend` Job |
| `biome check` (frontend lint/format) | ✅ Blocking | `frontend` Job |
| i18n validation | ✅ Blocking | `frontend` Job |
| E2E tests | ✅ Blocking | `test-e2e` Job, main branch only |

All gates must pass. No skipping, no `--no-cov` workarounds.

---

## Gate 11: Übergangsausnahme-Ablaufmanagement

Übergangsausnahmen (Warning-only Gates, deaktivierte Checks) müssen ein Ablaufdatum
haben. Das Script `scripts/check_gate_expirations.py` prüft konfigurierte Fristen
und warnt/failt bei Überschreitung.

### Registrierung

Jede Übergangsausnahme wird in `scripts/gate-exceptions.json` registriert (read
that file for the live set and status — the block below is the historical shape of the
now-resolved `coverage-threshold` exception, kept only as a field-reference example):

```json
{
  "exceptions": [
    {
      "id": "coverage-threshold",
      "gate": "G2",
      "description": "Coverage < 80% warning-only, hard floor at 60%",
      "set_date": "2026-06-04",
      "expires": "2026-09-01",
      "review_after": "2026-07-15",
      "status": "resolved",
      "approved_by": "user"
    }
  ]
}
```

> **Historical note:** The `coverage-threshold` exception above is **resolved**
> (lifted 2026-06-14, see the Coverage-Gate section). It is shown only to document the
> JSON schema. Do not treat it as an active exception.

### CI Integration

Der `architecture` Job in CI führt `scripts/check_gate_expirations.py` aus:
- Vor `review_after`: Info-Message
- Nach `review_after`, vor `expires`: Warning
- Nach `expires`: **CI Failure** (Ausnahme muss verlängert oder aufgehoben werden)

### When to add

Jede neue Übergangsausnahme muss einen Eintrag in dieser Datei haben. Ohne Eintrag
gilt die Ausnahme als nicht autorisiert.

---

## Running Locally

```bash
just check          # Architecture + lint + type check
just test           # Parallel unit + integration (xdist)
just test-unit      # Unit tests only
just test-single    # Single-threaded for debugging
pnpm test           # Frontend tests
```

---

## Gate 8: Feature Adoption Gate

Runs `scripts/check_adoption.py` in CI. WARN-level adoption debt is ratcheted
against `scripts/architecture/ai-gate-baseline.json`: existing debt may shrink,
but new missing variables, locale gaps, WARN categories, runtime-evidence gaps,
or inline fallback debt fail until fixed or ADR/user-approved in the baseline.

Reads the adoption registry at `scripts/architecture/adoption-registry.yaml` and
validates that every registered feature adopts its required core infrastructure.
Per ADR-045, static adoption is necessary but not sufficient: modes with
`requires_runtime_evidence: true` must also have correlated runtime evidence before
the gate can report `PASS`.

### Runtime status semantics (ADR-045)

| Status | Meaning | CI Behavior |
|--------|---------|-------------|
| `PASS` | Static checks pass and all required runtime modes are runtime-adopted. | CI continues |
| `GOVERNED_DEBT` / `WARN` | Static checks pass; only baseline-approved runtime/adoption debt remains. | CI follows ratchet policy; new debt fails |
| `STATIC_ONLY` | Explicit static-only report; cannot be treated as adoption PASS. | Not sufficient for stable feature claims |
| `FAIL` | Static failure, malformed/missing evidence, or new/unapproved runtime gap. | CI stops |

### Static score thresholds

These thresholds still apply to the static/adoption score, but `PASS` is capped by
the runtime status semantics above when runtime evidence is required.

| Score | Result | CI Behavior |
|-------|--------|-------------|
| ≥ 0.85 | PASS | CI continues |
| 0.70 – 0.85 | WARN | CI continues, but reports gaps in output |
| < 0.70 | FAIL | CI stops |
| (new, unregistered feature) | WARN | Automatic WARN until registered in the adoption registry |

### Scoring Weights

| Item | Weight | Notes |
|------|--------|-------|
| `required` infrastructure | 1.0 | FAIL-level if missing |
| `partial` infrastructure | 0.5 | 0.5 credit if missing, 1.0 if present |
| `should` context variables | 0.3 | Warned, not failed |
| `must` context variables | 1.0 | FAIL-level if missing |
| Registered inline fallback | -0.1 each | Slight penalty per registered fallback |

### When adding a new feature

1. Register it in `scripts/architecture/adoption-registry.yaml` under the correct feature category
2. Include all required infrastructure entries
3. List all `must` and `should` context variables
4. Verify `check_adoption.py` scores ≥ 0.85 and, where required, reports runtime-adopted evidence
5. If the feature uses an inline prompt fallback, register it under `inline_fallbacks` with a migration target

### CI Pipeline Position

```
1. ruff format + lint
2. check_architecture.py        (RULE enforcement)
3. check_adoption.py             ← Gate 8: adoption score
4. check_prompt_structure.py     (prompt variable validation)
5. pyright
6. pytest -m unit
7. pytest -m integration
8. pnpm test
9. bandit
```

### Validated by

`scripts/check_adoption.py` — reads registry, scans bundled prompts for variable presence, scans service files for infrastructure usage via import analysis, loads runtime evidence from the configured file/repository source, computes per-feature and overall scores, and outputs JSON + human-readable status using `PASS`/`GOVERNED_DEBT`/`STATIC_ONLY`/`FAIL` semantics.

**Spec**: `docs/architecture/decisions/025-feature-adoption-infrastructure.md` (Decision 5)

---

## Gate 9: AI Content Review Gate

Applies to features that involve prompt engineering, LLM interaction, or user-facing AI output. This gate supplements the technical architecture gates (Gates 3–7) with content-specific quality checks.

### Checklist (per feature)

- [ ] **Prompt uses PromptComposer** — not inline, unless registered in `adoption-registry.yaml` under `inline_fallbacks` (ADR-025 Decision 4)
- [ ] **No production inline fallback body** — if a bundled target exists, production code must not carry an alternate inline system/task prompt body; test-only fallbacks must be unreachable from production DI
- [ ] **PromptComposer routeability** — every routeable `_INTENT_TO_CATEGORY` + `_INTENT_TO_MODE` mapping resolves to a bundled EN target or has an explicit non-routeable rationale
- [ ] **Prompt Surface Manifest conformance (ADR-037)** — every production LLM intent has a manifest entry; routeable entries have correct template path, variables, provenance, security, and fallback policy; non-routeable entries have rationale; missing manifest entry is a P0 CI blocker
- [ ] **All MUST variables present** — `check_prompt_structure.py --strict` passes for the feature's category
- [ ] **Meta/Universal validated separately** — Narrare identity is guaranteed by `NarrareMeta`; fiction rules, conflict rules, and injection defense are guaranteed by `NarrareUniversalRules` (ADR-026). Do not validate as one monolithic meta prompt.
- [ ] **Production agent capability inheritance** — every production agent path uses `NarrareAgent` and therefore inherits both `NarrareMeta` and `NarrareUniversalRules`, except ADR-approved exceptions
- [ ] **Injection defense: user content XML-wrapped** — all UNSAFE_USER_VARS wrapped in `<tag>...</tag>` in prompt templates
- [ ] **Variable provenance** — every template variable is classified as user-authored content, system-generated data, or feature-dynamic data; new unregistered variables fail CI
- [ ] **i18n: prompt locale policy** — Bundled feature prompts are EN-only (output language via `{{writing_language}}`); declared localized families (meta, universal) must exist in all declared locale directories under `_bundled/{category}/`
- [ ] **Token budget enforced** — ContextAssembler (or WritingContextAssembler) used with TokenBudgetManager
- [ ] **Memory layer included** — `{{user_preferences}}` and `{{avoidance_patterns}}` variables present
- [ ] **Error handling: LLM failures don't crash** — proper exception handling per RULE-11 (no bare except, no silent failures)
- [ ] **Streaming: SSE where backend supports it** — SSE used for AI features with streaming capability per RULE-13

### Automation Status

| Checklist Item | Automated? | Tool |
|----------------|------------|------|
| PromptComposer usage / no inline production fallback | Yes | `check_adoption.py` + inline fallback registry |
| PromptComposer routeability | Yes | `check_architecture.py --prompt-integrity` / intent checker |
| Prompt Surface Manifest conformance | Yes | `check_prompt_surface.py` (ADR-037) — manifest/route/template/variable conformance |
| MUST variables | Yes | `check_prompt_structure.py` |
| Meta/Universal capabilities | Yes | `check_adoption.py` + `check_prompt_structure.py` + production-agent regression tests |
| Injection defense | Yes | `check_prompt_structure.py` |
| Variable provenance | Yes | `check_prompt_structure.py` + variable checker |
| i18n locales | Yes | `check_adoption.py` (i18n evidence check) |
| Token budget | Yes | `check_adoption.py` (import analysis) |
| Memory layer | Yes | `check_prompt_structure.py` (variable check) |
| Error handling | Partial | `check_architecture.py` (RULE-11 enforcement) |
| Streaming | Partial | `check_streaming_compliance.py` discovers backend SSE endpoints and frontend `connectSSE()` coverage; gaps are ratcheted in `ai-gate-baseline.json` |

### Validated by

`check_adoption.py` + `check_prompt_structure.py` + `check_architecture.py` together enforce items 1–7. `check_exception_baseline.py` prevents approved exception growth, `check_frontend_file_size.py` reports TS/TSX RULE-04 hard-limit debt, and `check_streaming_compliance.py` conservatively ratchets frontend SSE coverage gaps. Manual review remains required where static matching is inconclusive.

**Spec**: `docs/architecture/decisions/025-feature-adoption-infrastructure.md` (Decision 6)

### Prevention Lessons (from CR-06 §5.1)

These checklist items are explicitly tied to resolved findings (CR-06 §5.1 "Review-Erkenntnisse"). The prevention for each is automated — reviewers should know which checker backs each lesson.

| Lesson (CR-06 §5.1) | Backing automation | Finding |
|---------------------|--------------------|---------|
| KB-context variables non-empty at runtime | `check_doc_drift.py` §7-stub detector (CI-blocking + pre-commit) | FIND-002 (Coreference without characters) |
| TokenBudget actually applied (not just template-present) | `accepted_risk`: name/import-based static check rejected as systematically wrong; per-service regression tests are the real enforcement (FIND-003/004) | FIND-006 (Adoption-Scorer `token_budget` without code proof) |
| ConsistencyDeps complete (incl. `kb_relationships`) | FIND-001 fix + regression tests in `consistency/checker_context.py` | FIND-001 (Consistency-Check without KG-Relationships) |
| Preference-injection gate tested | FIND-005 fix + `PreferenceContextEnricherImpl` wiring + regression tests (`dependencies_prompts.py`) | FIND-005 (mem0 Preference-Injection-Gate) |
| No false-control claims | `scripts/doc_drift/removed_governance_refs_checks.py` (WARNING-only, ratcheted baseline) | FIND-014 (RULE-18b toolchain removed, CONSTRAINTS stale) |

---

## Gate 10: Semantic Review Gate (NEW)

Applies to features that share data with other features. Supplements Gates 3–9
with cross-feature coherence checks.

### Owner

Architecture Specialist during Stage 2.5 (Semantic Review).

### Checklist (per feature)

- [ ] **Cross-Feature data flows identified** — Shared data sources listed (KB, Storyboard, Frontmatter, wiki, memory/preferences, prompt registry, settings, etc.)
- [ ] **Integration Contract defined** — For each shared source, behaviour on change and deletion is documented per RULE-03 Integration Contracts
- [ ] **Intent semantic scope verified** — No existing intent/prompt has the same ID with different semantic scope. New intents have Scope/Input/Output/NOT documented
- [ ] **i18n parity checked** — Bundled feature prompts: EN-only by default (ADR-026 Phase 5). Declared localized prompt families: all declared locales exist and are in sync. UI i18n: en/de/fr required per RULE-16.
- [ ] **Injection defence verified** — All user-content variables registered in `variable_registry.USER_CONTENT_VARS` and explicitly wrapped with approved XML tags in prompt templates
- [ ] **Template variables registered** — New variables classified in `variable_registry.USER_CONTENT_VARS`, `SYSTEM_VARS`, or `FEATURE_DYNAMIC_VARS`
- [ ] **Prompt Surface Manifest conformance** — Intent registered in manifest with correct routeable/non-routeable status, variables, provenance, security class, and fallback policy (ADR-037)
- [ ] **KB status filtering considered** — If feature reads KB data, deprecated/archived entities are excluded
- [ ] **Token budget defined** — String-truncation limits or TokenBudgetManager usage defined
- [ ] **RULE-22 compliance** — Cross-Feature Coherence Gate passed
- [ ] **Context precedence applied** — Current author instruction > explicit project writing profile/manual override > current scene/storyboard/timeline plan > curated KB > learned memory/mem0 preferences > generated suggestions/inferred extraction. High-impact conflicts are surfaced, not silently resolved.

### Automation Status

| Checklist Item | Automated? | Tool |
|----------------|------------|------|
| Data flows | Manual | Requires architectural review |
| Integration Contract | Manual | Template in architecture-rules.md |
| Intent semantics | Partial | `check_intent_consistency()` in prompt_integrity.py |
| i18n parity | Partial | `check_i18n_parity()` in prompt_integrity.py |
| Injection defence | Yes | `check_template_variables()` in prompt_integrity.py |
| Variable registration | Yes | `check_variable_registration()` in prompt_integrity.py |
| Prompt Surface Manifest | Yes | `check_prompt_surface.py` (ADR-037) |
| KB status filtering | Manual | Requires architectural review |
| Token budget | Manual | Requires architectural review |
| RULE-22 | Manual | Stage 2.5 checklist |
| Context precedence | Manual + prompt tests | Stage 2.5 checklist + feature-specific regression scenarios |

### CI Pipeline Position

```
1. ruff format + lint
2. check_architecture.py --prompt-integrity  (RULE enforcement + prompt integrity)
3. check_adoption.py
4. check_prompt_structure.py
5. pyright
6. pytest -m unit
7. pytest -m integration
8. pnpm test
9. bandit
```

### Validated by

`check_architecture.py --prompt-integrity` + manual Stage 2.5 review by Architecture Specialist.

---

## Relationship: Gates 8–10 vs. Existing Gates

Gates 8–10 are **additive** — they do not replace Gates 1–7. The relationship is:

| Gate | Scope | What it catches |
|------|-------|-----------------|
| 1–2 | Test quality | Missing tests, low coverage |
| 3 | Architecture rules | RULE-01b through RULE-19 violations |
| 4 | Fake conformance | Protocol violations in test doubles |
| 5 | Cross-layer contracts | API drift, i18n namespace gaps |
| 6 | Type safety | Untyped code, `Any` misuse |
| 7 | CI pipeline | Orchestrates all gates |
| **8** | **Feature adoption** | **Missing infrastructure: no TokenBudget, no PromptComposer, no KB entities** |
| **9** | **AI content quality** | **Missing prompt variables, no injection defense, no i18n, no streaming** |
| **10** | **Semantic Review** | **Cross-feature incoherence: missing Integration Contract, unregistered variables, unimplemented i18n, intent scope drift** |
| **12** | **ADR Implementation Completeness** | **ADRs marked "Implemented" without DI wiring, tests, consumer migration, or documentation** |
| **13** | **Quarterly Content Review** | **Stale findings, missing cross-feature audit, prompt surface drift** |

A feature must pass ALL gates (1–13) to reach `status: stable`.

---

## Process Prevention Checklists

### ADR CI Impact Checklist

Every ADR or ADR update that changes runtime architecture must identify the CI
surface it affects before implementation starts:

- [ ] Which architecture/prompt/adoption/streaming checkers must change?
- [ ] Which baselines must shrink, stay fixed, or be invalidated?
- [ ] Which tests prove the new guarantee?
- [ ] Which existing exceptions are removed, revalidated, or forbidden from growth?
- [ ] Which derived docs/context summaries must be updated to prevent stale guidance?

### Migration Completion / Legacy Cleanup Checklist

A migration is not complete until old production paths and old guidance are closed:

- [ ] Old production path removed or unreachable from production DI.
- [ ] Stale comments/docstrings/examples describing old behavior removed.
- [ ] Adoption/exception registries no longer list migrated production fallbacks.
- [ ] Regression tests fail if the legacy path is reintroduced.
- [ ] Docs and extracted context reflect the new source of truth.

### AI Content Review Gate Integration

- Stage 2.5 Architecture: verify PromptComposer routeability, variable provenance,
  context precedence, ADR-026 capability inheritance, and prompt language policy.
- Stage 4 Platform: validate machine checks, baselines, and regression tests.
- Stage 5 Docs: verify no derived guide weakens RULE-02/RULE-02a/ADR-026.

---

## Gate 12: ADR Implementation Completeness

Before marking any ADR as "✅ Implemented", ALL of the following must be verified:

- [ ] **Code complete**: All code artifacts specified in the ADR exist and compile/pass
- [ ] **DI wired**: If the ADR introduces a service/component, it is wired into the application DI container
- [ ] **Tests pass**: Unit AND integration tests cover the ADR's behavioral requirements
- [ ] **Consumers updated**: All existing consumers that should use the new pattern are migrated
- [ ] **Documentation updated**: CURRENT_STATE.md, relevant feature specs, and architecture-rules.md reflect the change
- [ ] **No dead code**: Old patterns that the ADR replaces are removed or explicitly registered as exceptions
- [ ] **CI reflects change**: Any new architecture checks or baselines are updated

**Exception**: ADRs that are purely declarative (no code changes) may skip code/DI/test items but must still update documentation.

### Root Cause

This gate was introduced because ADR-033 (mem0) was marked "Implemented" but the DI wiring was never completed (FIND-003 from CR-03). The root cause was the absence of a verification gate between "code exists" and "fully integrated." Without this gate, an ADR can appear complete while its integration path is dead — silently degrading the feature it was supposed to enable.

### CI Integration

This gate is manual (checked by the Coordinator during Stage 6 commit), but the following automated checks support it:

| Item | Automated Support |
|------|------------------|
| Code complete | `pytest` + `pyright` |
| DI wired | Integration tests that exercise the DI path |
| Tests pass | `pytest` coverage gates |
| Consumers updated | `check_adoption.py` + `check_architecture.py` |
| Documentation updated | `check_doc_drift.py` |
| No dead code | `check_architecture.py` + `check_exception_baseline.py` |
| CI reflects change | CI pipeline runs on every PR |

### Validated by

Coordinator during Stage 6 (Commit). Architecture Specialist during Architecture Review.
Reported by: CR-04 audit (FIND-003 root cause).

---

## Gate 13: Quarterly Content Review

Re-run the full content review (CR-00 through CR-08) every quarter, or when:
- A new AI feature is added
- A cross-feature integration point changes
- The prompt template surface grows by > 10%

### Cadence by Development Phase

| Phase | Cadence | Minimum Scope |
|-------|---------|---------------|
| Active development | Per new AI feature | CR-01, CR-04, Gate 9 checklist |
| Stabilization | Monthly | CR-01 through CR-04 |
| Maintenance | Quarterly | Full CR-00 through CR-08 |

### Ad-hoc Triggers

- New AI agent or intent registered
- Prompt template format changes
- Context assembly pipeline changes
- KB context contract updates

### Review Scope

| Review | Focus | Tool |
|--------|-------|------|
| CR-01 | Prompt quality & completeness | Manual + `check_prompt_structure.py` |
| CR-02 | System prompt architecture | `check_adoption.py` + `check_architecture.py --prompt-integrity` |
| CR-03 | Feature adoption (mem0, budget, KG) | `check_adoption.py` + probes |
| CR-04 | Cross-feature coherence | Manual + `check_registry_drift.py` |
| CR-07 | AI-UX compliance | `check_streaming_compliance.py` + manual |
| CR-08 | Hardcoded values & configurability | Manual + `check_model_registry.py` |

### Outcome

After each review:
1. Update `_audit/results/content-review/findings/cr-05-initial-findings.md`
2. Register new findings in `_audit/results/content-review/findings/`
3. Create remediation tasks for any new ❌ Open findings
4. Update `docs/_shared/CURRENT_STATE.md` if findings status changed

### Quarterly Audit Cross-References (from CR-06 §5.3)

Two audit items recommended in CR-06 §5.3 are already automated — they run in every CI cycle, so the quarterly review re-confirms their currency rather than performing them manually.

| Quarterly item (CR-06 §5.3) | Backing automation | CI position |
|-----------------------------|--------------------|-------------|
| Adoption-Verifikation: did new AI features actually wire TokenBudget, PromptComposer, mem0, KG-Relationships — or only drop a template file? | `check_adoption.py` (Gate 8) — scans service code for infrastructure usage via import analysis; computes per-feature + overall scores; `PASS`/`GOVERNED_DEBT`/`STATIC_ONLY`/`FAIL` semantics | Runs in CI on every PR; quarterly review re-checks the score trend + `unverified_count` |
| False-Control-Audit: do CONSTRAINTS.md / ADRs / Remediation-Specs make enforcement claims whose toolchain still exists and is CI-blocking? | `scripts/doc_drift/removed_governance_refs_checks.py` — detects stale references to deleted governance artefacts (WARNING-only, ratcheted baseline) | Runs in CI on every PR; quarterly review re-checks the baseline trend |

---

## Umgang mit Gate-Verletzungen

Wenn ein CI-Gate/Hook fehlschlägt:

1. **FIXEN, nicht forschen.** Ob der Fehler "pre-existing" ist oder nicht, ist irrelevant.
   Der Commit ist blockiert → der Fehler wird behoben. Punkt.

2. **Keine Ausreden.** "Das war schon vorher kaputt" ist keine akzeptable Rechtfertigung.
   Wenn es kaputt ist, wird es jetzt repariert.

3. **Keine Root-Cause-Analyse.** Bei einfachen Lint/Test-Fehlern gibt es keine
   mehrstufige Ursachenforschung. Der Fehler wird an der Fundstelle behoben.

4. **Scope:** Fixiere NUR die gemeldeten Violations. Keine Architektur-Diskussionen,
   keine ADR-Vorschläge, keine "eigentlich müsste man ganz anders"-Exkurse.

5. **Priorität:** Geschwindigkeit > Eleganz. Ein `MagicMock(spec=...)` ist besser
   als ein Fake-Refactoring, das 30 Minuten dauert. Der perfekte Fix kann im
   nächsten Commit nachgereicht werden.

Diese Regel gilt für den NarrarePlatformSpecialist und wird vom Coordinator
durchgesetzt. Wiederholte Verstöße (Forschen statt Fixen) sind ein Prozessverstoß.

---

## Baseline Process for New Gates

When a new gate is introduced, the following process MUST be followed to prevent
governance gaps and ensure deterministic CI behavior from day one.

### Step 1: Baseline Scan

When a new gate is introduced, a **full scan of all existing files** MUST be
performed. The scan captures every current violation against the new rule — not
a sample, not a subset.

### Step 2: Baseline Documentation

All existing violations are recorded as a **baseline snapshot** with:
- File path, line count or range, violation reason
- Stored in a versioned baseline file (e.g. `scripts/architecture/<gate>-baseline.json`)
- Committed alongside the gate implementation

### Step 3: Ratchet Integration

The baseline is loaded by the gate's ratchet mechanism:
- **No reduction** without an explicit tracking task (proves the fix)
- **No growth** without coordinator approval (prevents silent regression)
- Baseline count = current known debt ceiling

### Step 4: Tracking Tasks

Every baseline violation gets a **tracking task** (`AUFG-XX-YY`) so that:
- Debt is visible in the task system
- Progress is measurable (open tasks → resolved tasks)
- No violation is forgotten or silently accepted

### Step 5: Grace Period

New gates start with a **warning phase** (non-blocking in CI) until:
- The baseline is validated against the actual codebase
- The ratchet file is reviewed and approved
- The gate transitions to **blocking** after one successful validation cycle

### Responsibilities

| Step | Owner |
|------|-------|
| Baseline scan + documentation | Architecture Specialist |
| Ratchet integration + CI wiring | Platform Specialist |
| Tracking task creation | Coordinator |
| Grace period → blocking transition | Platform Specialist (CI) + Coordinator (approval) |

### Step 6: Grace-Period-Exit Gate (MANDATORY)

A new gate MUST NOT transition from warning to blocking without explicit Coordinator
approval.

**Exit criteria (ALL must be met):**

1. Full baseline scan completed and stored in versioned baseline file
2. All baseline violations have tracking tasks (AUFG-XX-YY)
3. At least one full CI cycle completed with the gate in warning mode
4. Coordinator has reviewed the baseline and approved blocking transition
5. The gate is added to the Coordinator's active gate register

**Process:**

1. Platform Specialist proposes transition with baseline report
2. Coordinator reviews: Are all baseline items tracked? Is the ratchet correct?
3. Coordinator approves or requests baseline cleanup first
4. Platform Specialist flips gate to blocking in CI
5. Coordinator creates handoff note documenting the transition

**This exists because:** Silent gate transitions create invisible baseline gaps.
New code passes the gate, but pre-existing violations persist untracked.

### Why This Exists

Without a baseline, a new gate either (a) blocks CI immediately on pre-existing
violations (halting all work), or (b) runs as warning forever (ignored). The
baseline process ensures new gates are introduced with controlled, visible debt
that shrinks over time.

---

**Reference**: `docs/development/testing-standards.md` (1224 lines)
**Related**: narrare-dev/guides/testing · narrare-dev/examples/testing-patterns · narrare-dev/constraints/rules
**Adoption Spec**: `docs/architecture/decisions/025-feature-adoption-infrastructure.md`
