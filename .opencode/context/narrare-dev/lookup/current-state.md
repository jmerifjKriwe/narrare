<!-- Context: narrare-dev/lookup/current-state | Priority: critical | Source: docs/_shared/CURRENT_STATE.md | Updated: 2026-07-06 -->

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

## Codebase Stats

> **Counts below are intentionally not pinned here** — they drift within days. Run the cited command or read the cited SSOT for the current value.

- Knowledge Graph: Run `just check-architecture` or query the code-review-graph MCP for current node/edge counts.
- Backend tests: Run `just test --collect-only -q | tail -1` or `pytest --collect-only -q` for the current test count.
- Frontend tests: Run `pnpm test --list` or see Review 02 for the current frontend test count.
- Architecture rules: RULE-01b through RULE-23 (plus sub-rules 02a/02b/18b); see `constraints/rules.md` for the authoritative rule list.
- ADRs: See `docs/architecture/decisions/INDEX.md` for the authoritative ADR list (`ls docs/architecture/decisions/ADR-*.md | wc -l` for the count).
- Feature specs: See `docs/features/INDEX.md` for the authoritative feature-spec list.
- Open questions: See the open-questions index for the current set and status.

---

## Architecture

| Layer | Contents |
|-------|----------|
| `packages/core/` | Submodules + AI agents (pydantic-ai); see `packages/core/narrare_core/agents/__init__.py` for the authoritative agent registry |
| `apps/api/` | Domain modules + routers; Alembic migrations. See `apps/api/narrare/` and the Alembic `versions/` directory for the current structure |
| `packages/web/` | Next.js 16, TipTap v3, 3 demo novels, 3 locales (en/de/fr) |
| `docs/` | ADRs + impl plans, open questions, feature specs; see `docs/architecture/decisions/INDEX.md` and `docs/features/INDEX.md` for the authoritative lists |

---

## AI Feature Freeze / Post-Freeze Governance

- **Status:** Freeze fully lifted (2026-06-03). Ratcheted post-freeze governance retained.
- **Resolved blockers:** AUFG-02-01 (backend unit failures 7→0), AUFG-02-03 (frontend tests stable <120s), AUFG-03-01 (prompt warnings 79→35), AUFG-03-02 (KB adoption 0.78→0.90 PASS).
- **Ratcheted debt:** Frontend RULE-04 legacy violations are ratcheted (no growth allowed); run `just check-frontend-size` for the current baseline count.
- **Still blocked:** new prompt/adoption warning growth, new architecture exceptions without ADR, new frontend file-size violations, REST-only frontend paths for SSE-capable backends, workaround/quick-fix implementations.

---

## Phase 6 Completed

34+ items including WRITE-003/004/006/007, INFRA-004, KB-002/003/005/006a/007/009, ANAL-001/002/003/004, CONS-001, SET-005, WIKI-001, PLAN-004/006, CR-01 to CR-04, ADR-016 through ADR-023, ADR-027, INFRA-011 stabilization slices, ADR-037 Prompt Surface Contract Manifest (INFRA-012 CR-01).

---

## What's Next

1. ✅ AI Feature Freeze lifted — new AI work may resume under ratcheted governance
2. ✅ AUFG-02-01, AUFG-02-03, AUFG-03-01, AUFG-03-02 resolved
3. ⏳ Frontend RULE-04 debt — continue modularizing (ratcheted baseline; run `just check-frontend-size` for the remaining count)
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
| System Health (score/score band) | Medium | Metric floor/baseline artifact. Run `just check-health` for the current score. CI warning-only for DEGRADED; CRITICAL blocks. Baseline debt must shrink for ≥0.85. |
| Frontend RULE-04 legacy violations | Medium | Ratcheted: no new violations; reductions only unless ADR/user-approved exception. Run `just check-frontend-size` for the current baseline. |

---

**Related**: `constraints/rules.md`, `lookup/adr-index.md`, `lookup/feature-index.md`
