<!-- Context: narrare-dev/lookup/current-state | Priority: critical | Source: docs/_shared/CURRENT_STATE.md | Updated: 2026-06-03 -->

# Current State — Live Project Status

**Core Idea**: Phase 6 (Post-MVP) in progress. Every agent reads this at session start.

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

- Knowledge Graph: 15,407 nodes, 112,382 edges, risk medium
- Backend tests: 4,273 (3,750 unit + 495 integration) across 396 test files
- Frontend tests: ~5,000 across 165 test files
- Total tests: ~9,200+
- Architecture rules: 22 (RULE-01 through RULE-21 + RULE-01b)
- ADRs: 24+ (ADR-001 through ADR-023, plus ADR-027)
- Feature specs: 76 files + INDEX.md

---

## Architecture

| Layer | Contents |
|-------|----------|
| `packages/core/` | 17 submodules, 18 AI agents (pydantic-ai) |
| `apps/api/` | 20 domain modules, 38 router files, Alembic 0001-~0023 |
| `packages/web/` | Next.js 16, TipTap v3, 3 demo novels, 3 locales |
| `docs/` | 22 ADRs, 8 open questions, 76 feature specs |

---

## Phase 6 Completed

34+ items including WRITE-003/004/007, INFRA-004, KB-002/003/005/006a/007/009, ANAL-001/002/003/004, CONS-001, SET-005, WIKI-001, PLAN-004/006, CR-01 to CR-04, ADR-016 through ADR-023, and INFRA-011 stabilization slices in progress.

---

## What's Next

1. Finish INFRA-011 Docs/Governance drift cleanup and AI feature freeze-lift review.
2. E2E test patterns
3. ANAL-005 Coreference Analysis — resumes only after INFRA-011 gates pass or Architecture-approved exception.

---

## Open Questions

| ID | Question | Status |
|----|----------|--------|
| Q-001 | MCP auth strategy | Open |
| Q-002 | A2A streaming requirement | Open |
| Q-003 | Embedding provider abstraction | Open |
| Q-007 | Writing context data loader | Open |
| Q-008 | Auth store hydration | Open |

Resolved: Q-004 (TaskIQ), Q-005 (OpenAI-compatible), Q-006 (Runtime cascade)

---

## Known Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Python 3.14 missing type stubs | Low | Documented in pyproject.toml |
| TipTap v3 API changes | Medium | Pin exact version |
| Editor h-full in flex container | Low | Follow DashboardView pattern |

---

**Related**: `constraints/rules.md`, `lookup/adr-index.md`, `lookup/feature-index.md`
