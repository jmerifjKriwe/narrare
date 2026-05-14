# ADR-014 — TDD Agent Workflow & Regression-First Fixes

> **Status:** ✅ Accepted
> **Date:** 2026-05-14
> **Deciders:** Antigravity (Orchestrator)

---

## Context

The Narrare AI agent system was previously designed with a strict "Waterfall" separation of labor:
1. Implementers (Backend, Core, Frontend) were explicitly forbidden from writing tests.
2. Testers (Platform) were the sole owners of test creation but forbidden from writing production code.
3. This separation made Test-Driven Development (TDD) impossible, as the agent fixing a bug or adding a feature could not see the failing test case before implementing the fix.

## Decision Drivers

- **Quality**: Bug fixes without regression tests are prone to recurrence.
- **Speed**: TDD provides a tight feedback loop that reduces total cycle time.
- **Agent Efficiency**: Modularizing implementation and testing within the same specialist reduces context switching between agents.
- **Consistency**: RULE-10 ("Tests are not optional") is easier to enforce if the implementer writes the tests.

---

## Options Considered

### Option A — Status Quo (Waterfall)
Maintain strict separation. Implementer fixes, then hand off to Tester.
**Cons:** High context switching, no TDD, regression tests often skipped.

### Option B — TDD Loop (Selected)
Allow specialists to write unit tests for their own implementation. Require regression tests before bug fixes.
**Pros:** Enables TDD, ensures every fix has a test, reduces handoff overhead.

---

## Decision

**We choose Option B.**

We are relaxing the strict "stay in your lane" rule for test creation. Implementers (Backend, Core, Frontend) are now *required* to write unit and regression tests for their work. The Platform specialist transitions from "sole test writer" to "Quality Gatekeeper," focusing on integration tests, architecture validation, and infrastructure.

---

## Rationale

TDD is a core engineering standard that cannot be effectively outsourced to a separate agent without significant context loss. By making the implementer responsible for the unit tests, we ensure that the code is testable and that the "Happy Path," "Error," and "Edge Case" scenarios (mandated in `testing-standards.md`) are covered immediately.

---

## Consequences

**Positive:**
- Every bug fix now starts with a failing regression test.
- TDD cycle (Red -> Green -> Refactor) is now possible for agents.
- Higher immediate test coverage.

**Negative / Tradeoffs:**
- Specialists spend more time on tests (increased token usage per specialist task).
- Boundary between "Implementation" and "Platform" is slightly blurred for unit testing.

**Constraints introduced:**
- New Coordinator Rule: `regression_first_fix`.
- Modified Coordinator Constraint #8: Specialists responsible for their own unit tests.

---

## Implementation Notes

Updated files:
- `.opencode/agents/narrare-dev-coordinator.md`
- `.opencode/agents/subagents/narrare-dev/backend.md`
- `.opencode/agents/subagents/narrare-dev/core.md`
- `.opencode/agents/subagents/narrare-dev/frontend.md`
- `.opencode/agents/subagents/narrare-dev/platform.md`

---

## Review Trigger

[X] After 3 months of implementation to evaluate agent performance.
[ ] When test coverage fails to meet thresholds despite specialists writing tests.
