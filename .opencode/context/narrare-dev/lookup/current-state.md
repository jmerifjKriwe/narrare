<!-- Context: narrare-dev/lookup/current-state | Priority: critical | Source: docs/_shared/CURRENT_STATE.md | Updated: 2026-06-05 -->

# Current State — Live Project Status

**Core Idea**: Phase 6 (Post-MVP) in progress. AI Feature Freeze fully lifted; post-freeze ratcheted governance retained. Every agent reads this at session start.

**Reference**: `docs/_shared/CURRENT_STATE.md` (always check for latest)

---

## Phase Status

| Phase | Status |
|-------|--------|
| 0: Repository Foundation | COMPLETE |
| 1: Core Infrastructure | COMPLETE |
| 2: API Foundation | COMPLETE |
| 3: Setup Wizard Backend | COMPLETE |
| 4: Frontend Foundation | COMPLETE |
| 5: Integration & Polish | COMPLETE |
| 6: Post-MVP Features | IN PROGRESS |

---

## Codebase Stats (verified 2026-06-03)

- Knowledge Graph: 15,527 nodes, 112,368 edges, risk medium
- Backend tests: 4,273 (3,750 unit + 495 integration) across 396 test files
- Frontend tests: 1,683 across 186 test files (Vitest + MSW)
- Total tests: ~5,900+
- Architecture rules: 22 (RULE-01 through RULE-21 + RULE-01b)
- ADRs: 37 (ADR-001 through ADR-037)
- Feature specs: 75 individual files + INDEX.md
- Open questions: 11 (Q-001 through Q-011)

---

## Architecture

| Layer | Contents |
|-------|----------|
| `packages/core/` | 17 submodules, 18 AI agents (pydantic-ai) |
| `apps/api/` | 20 domain modules, 38 router files, Alembic 0001-~0023 |
| `packages/web/` | Next.js 16, TipTap v3, 3 demo novels, 3 locales (en/de/fr) |
| `docs/` | 22 ADRs + 2 impl plans, 11 open questions in 6 files, 75 feature specs |

---

## AI Feature Freeze / Post-Freeze Governance

- **Status:** Freeze fully lifted (2026-06-03). Ratcheted post-freeze governance retained.
- **Resolved blockers:** AUFG-02-01 (backend unit failures 7→0), AUFG-02-03 (frontend tests stable <120s), AUFG-03-01 (prompt warnings 79→35), AUFG-03-02 (KB adoption 0.78→0.90 PASS).
- **Ratcheted debt:** Frontend RULE-04 legacy violations ratcheted 53→38; no new violations allowed.
- **Still blocked:** new prompt/adoption warning growth, new architecture exceptions without ADR, new frontend file-size violations, REST-only frontend paths for SSE-capable backends, workaround/quick-fix implementations.

---

## Phase 6 Completed

34+ items including WRITE-003/004/006/007, INFRA-004, KB-002/003/005/006a/007/009, ANAL-001/002/003/004, CONS-001, SET-005, WIKI-001, PLAN-004/006, CR-01 to CR-04, ADR-016 through ADR-023, ADR-027, INFRA-011 stabilization slices, ADR-037 Prompt Surface Contract Manifest (INFRA-012 CR-01).

---

## What's Next

1. ✅ AI Feature Freeze lifted — new AI work may resume under ratcheted governance
2. ✅ AUFG-02-01, AUFG-02-03, AUFG-03-01, AUFG-03-02 resolved
3. ⏳ Frontend RULE-04 debt — continue modularizing (38 ratcheted legacy violations remain)
4. ⏳ E2E test patterns
5. ⏳ ANAL-005: Coreference Analysis — resumes under post-freeze governance

---

## Open Questions

| ID | Question | Status |
|----|----------|--------|
| Q-001 | MCP auth strategy | Open |
| Q-002 | A2A streaming requirement | Open |
| Q-003 | Embedding provider abstraction | Resolved → ADR-020 |
| Q-004 | Celery vs arq | Resolved → TaskIQ |
| Q-005 | GLM/Z.AI compatibility | Resolved → OpenAI-compatible |
| Q-006 | Configurable Model Routing | Resolved → Runtime cascade |
| Q-007 | Writing context data loader | Resolved → WritingContextAssembler |
| Q-008 | Auth store hydration | Resolved → AuthProvider.tsx |
| Q-009 | Chat conversations: project-scoped vs user-scoped | Open |
| Q-010 | Chat prompt i18n: EN-only v1 vs full i18n | Open |
| Q-011 | Distribution strategy for non-technical users | Open |

---

## Known Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Python 3.14 missing type stubs | Low | Documented in pyproject.toml |
| TipTap v3 API changes | Medium | Pin exact version |
| Editor h-full in flex container | Low | Follow DashboardView pattern |
| System Health 0.73 (DEGRADED) | Medium | Metric floor/baseline artifact. CI warning-only for DEGRADED; CRITICAL blocks. Baseline debt must shrink for ≥0.85. |
| 38 frontend RULE-04 legacy violations | Medium | Ratcheted: no new violations; reductions only unless ADR/user-approved exception. |

---

**Related**: `constraints/rules.md`, `lookup/adr-index.md`, `lookup/feature-index.md`
