<!-- Context: narrare-dev/processes/quality-gates | Priority: high | Source: docs/development/testing-standards.md | Updated: 2026-05-31 -->

# Quality Gates

What must pass before code is considered "done." Every gate must pass for a feature to reach `status: stable`.

---

## Gate 1: Test Level Gates

| Level | Location | Scope | Time Target | Requirement |
|-------|----------|-------|-------------|-------------|
| **Unit** | `tests/unit/` | Fast, pure, no I/O | < 5s total | Every public service method: 3+ tests (happy path, domain error, edge case) |
| **Integration** | `tests/integration/` | Real DB + Redis, mocked LLM | < 60s total | Every repository method + router endpoint (200/201 schema validation, 401, 404, 422) |
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
- Enforces: RULE-01b, 02, 04, 06, 09, 11, 15, 19
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
- No untyped public functions
- `Any` forbidden except in approved adapters

---

## Gate 7: CI Summary

The full CI pipeline runs these gates in order. See `.github/workflows/ci.yml`
for the authoritative source.

### Gate Status in CI (Stand: 2026-06-03)

| # | Gate | CI Status | Notes |
|---|------|-----------|-------|
| 1 | `ruff` format + lint | ✅ Blocking | `lint` Job |
| 2 | `check_architecture.py` | ✅ Blocking | `architecture` Job |
| 3 | `check_exception_baseline.py` | ✅ Blocking | `architecture` Job |
| 4 | `check_adoption.py` + `check_prompt_structure.py` | ✅ Blocking | `architecture` Job |
| 5 | `check_streaming_compliance.py` (RULE-20) | ✅ Blocking | `architecture` Job |
| 6 | `check_locale_sync.py` | ✅ Blocking | `architecture` Job (previously: warning) |
| 7 | `check_doc_drift.py` | ✅ Blocking | `architecture` Job |
| 8 | `export_openapi.py --check` | ✅ Blocking | `architecture` Job |
| 9 | `pyright` | ⚠️ Partial | `pyright` in CI aktiv (RULE-09). Pyright is the sole type checker. |
| 10 | `pytest` unit tests | ✅ Blocking | `test-unit` Job |
| 11 | Coverage threshold | ⚠️ Warning (≥60%) | **Übergangsausnahme**: Hard floor 60%, Target 80% |
| 12 | `pytest` integration tests | ✅ Blocking | `test-integration` Job |
| 13 | `pnpm test` (frontend) | ✅ Blocking | `frontend` Job |
| 14 | `bandit` + `pip-audit` | ✅ Blocking | `security` Job |

### Übergangsausnahme: Coverage-Gate (Hart ab 60%, Warning ab 80%)

**Entscheidung:** Coverage läuft mit `--cov-fail-under=60` (harte Schwelle) und
einem separaten Check-Step, der bei 60-80% eine GitHub-Warning ausgibt.
Der Test-Job schlägt bei Unterschreitung von 60% **fehl** (< 60% = CI-Failure),
60-80% = Warning, ≥ 80% = Target erreicht.

**Begründung:** Die Test-Suite ist stabil (AUFG-02-01 behoben, 0 Failures).
Coverage liegt bei 76% — unter dem dokumentierten Target von 80% für api bzw.
90% für core. Die 60%-Schwelle verhindert weiteren Verfall, während der
Coverage schrittweise auf die dokumentierten Modul-Schwellen angehoben wird.

**Aufzuheben wenn:** Coverage stabil ≥ 80% global und modulare Schwellen
(core ≥ 90%, api ≥ 80%) in CI aktiv sind. Erfordert explizite User-Freigabe.

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

Jede Übergangsausnahme wird in `scripts/gate-exceptions.json` registriert:

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
      "status": "active",
      "approved_by": "user"
    }
  ]
}
```

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
but new missing variables, locale gaps, WARN categories, or inline fallback debt
fail until fixed or ADR/user-approved in the baseline.

Reads the adoption registry at `scripts/architecture/adoption-registry.yaml` and validates that every registered feature adopts its required core infrastructure. Computes a weighted adoption score per feature and overall.

### Thresholds

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
4. Verify `check_adoption.py` scores ≥ 0.85
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

`scripts/check_adoption.py` — reads registry, scans bundled prompts for variable presence, scans service files for infrastructure usage via import analysis, computes per-feature and overall scores, outputs JSON + human-readable summary, exits 0/1/2 based on thresholds.

**Spec**: `docs/architecture/decisions/025-feature-adoption-infrastructure.md` (Decision 5)

---

## Gate 9: AI Content Review Gate

Applies to features that involve prompt engineering, LLM interaction, or user-facing AI output. This gate supplements the technical architecture gates (Gates 3–7) with content-specific quality checks.

### Checklist (per feature)

- [ ] **Prompt uses PromptComposer** — not inline, unless registered in `adoption-registry.yaml` under `inline_fallbacks` (ADR-025 Decision 4)
- [ ] **No production inline fallback body** — if a bundled target exists, production code must not carry an alternate inline system/task prompt body; test-only fallbacks must be unreachable from production DI
- [ ] **PromptComposer routeability** — every routeable `_INTENT_TO_CATEGORY` + `_INTENT_TO_MODE` mapping resolves to a bundled EN target or has an explicit non-routeable rationale
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
- [ ] **Injection defence verified** — All user-content variables registered in `_USER_CONTENT_VARS` and wrapped in XML tags in prompt templates
- [ ] **Template variables registered** — New variables added to `_SYSTEM_VARS` in `variable_engine.py`
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

A feature must pass ALL gates (1–10) to reach `status: stable`.

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

**Reference**: `docs/development/testing-standards.md` (1224 lines)
**Related**: narrare-dev/guides/testing · narrare-dev/examples/testing-patterns · narrare-dev/constraints/rules
**Adoption Spec**: `docs/architecture/decisions/025-feature-adoption-infrastructure.md`
