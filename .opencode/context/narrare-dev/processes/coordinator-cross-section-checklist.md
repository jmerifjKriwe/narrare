<!-- Context: narrare-dev/processes/coordinator-cross-section-checklist | Priority: high | Updated: 2026-06-12 -->

# Coordinator Cross-Section Checklist (Querschnitts-Checkliste)

Apply at every feature set of 3+ related tasks, or at minimum quarterly.
Catches systemic gaps that the specialist layer workflow does not naturally see.

---

## When to Apply

| Trigger | Frequency | Owner |
|---------|-----------|-------|
| Feature set of 3+ related tasks | Per feature set | Coordinator |
| End of a development phase | Per phase | Coordinator |
| Quarterly (minimum) | Calendar | Coordinator |
| After adding a new AI agent | Per agent | Coordinator |

---

## Checklist

### AI Surface Coverage

| # | Check | How | Severity |
|---|-------|-----|----------|
| 1 | New AI agents have eval suites? | Compare agents in `core/agents/` against suites in `evals/datasets/`. Gap = MUST-FIX before merge. | Must-fix |
| 2 | New prompt surfaces registered in manifest? | `check_prompt_surface.py` passes. Gap = MUST-FIX. | Must-fix |

### Test Quality

| # | Check | How | Severity |
|---|-------|-----|----------|
| 3 | Frontend tests isolated (no real network calls)? | `pnpm test` output has zero `ECONNREFUSED` lines. Noise = should-track. | Should-track |
| 4 | New tests collection-friendly? | `pytest --collect-only -q` time not regressed > 2s from last check. Heavy imports at module level = should-track. | Should-track |
| 5 | Coverage trend: rising, stagnant, or falling? | Compare README badge vs last check. Falling = MUST-FIX. Stagnant for 2+ checks = should-track. | Must-fix if falling |

### Performance Budget

| # | Check | How | Severity |
|---|-------|-----|----------|
| 6 | Frontend test time within budget? | `pnpm test` < 120s. Over = should-track (see AUFG-02-05). | Should-track |
| 7 | Pytest collection time within budget? | `pytest --collect-only -q` < 20s. Over = should-track (see AUFG-02-07). | Should-track |
| 8 | Pyright time within budget? | `pyright --stats` < 60s. Over = nice-to-have (monitor only). | Nice-to-have |

### Documentation Accuracy

| # | Check | How | Severity |
|---|-------|-----|----------|
| 9 | CURRENT_STATE.md reflects current reality? | Run `check_current_state_facts.py`. Any drift = should-track. | Should-track |
| 10 | quality-gates.md reflects current CI? | Compare gate table vs `.github/workflows/ci.yml`. Mismatch = should-track. | Should-track |
| 11 | SSOT docs consistent (CONSTRAINTS, TECH_STACK, GLOSSARY)? | Spot-check after ADR changes. Mismatch = should-track. | Should-track |

### Gate Governance

| # | Check | How | Severity |
|---|-------|-----|----------|
| 12 | New gates have complete baselines? | Baseline file exists in `scripts/architecture/`. Missing = MUST-FIX before blocking. | Must-fix |
| 13 | Grace-period exits follow Step 6 process? | See quality-gates.md Step 6. Unapproved transition = MUST-FIX. | Must-fix |
| 14 | Transition exceptions have clear exit criteria? | `gate-exceptions.json` has `expires` date. Missing/expired = should-track. | Should-track |

---

## Severity Definitions

| Severity | Action | Timeline |
|----------|--------|----------|
| **Must-fix** | Blocks merge of current feature set. Create AUFG task if not fixable immediately. | Before merge |
| **Should-track** | Does not block merge. Create tracking task. Review at next checkpoint. | Next checkpoint |
| **Nice-to-have** | Acknowledge. No task required unless pattern repeats 3+ times. | Discretionary |

---

## Integration with Stage Workflow

| Stage | Where This Checklist Applies |
|-------|------------------------------|
| Stage 1 (Planning) | Item 1: Confirm eval coverage planned for new AI agents |
| Stage 2 (Architecture) | Items 1-2: Spec must include eval suite design for new agents |
| Stage 4 (Platform) | Items 3-8: Validate test quality and performance during implementation |
| Stage 6 (Commit) | Items 9-14: Verify docs and gates before merge |
| Stage 8 (Review) | Full checklist as retrospective |

---

## Record Keeping

After each application, note:
- Date, trigger, items checked, items flagged, tasks created.
- Store in `_audit/results/coordinator-checks/` as `YYYY-MM-DD-cross-section.md`.
