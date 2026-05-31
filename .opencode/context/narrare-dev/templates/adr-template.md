<!-- Context: narrare-dev/templates/adr-template | Priority: medium | Source: docs/architecture/decisions/_TEMPLATE.md | Updated: 2026-05-31 -->

# ADR Template

Copy this template to `docs/architecture/decisions/ADR-NNN-short-title.md` and fill in all sections.

---

```markdown
# ADR-NNN — [Short Decision Title]

> **Status:** Proposed | Accepted | Superseded by ADR-NNN | Deprecated
> **Date:** YYYY-MM-DD
> **Deciders:** [Architecture Agent | + who else]
> **Supersedes:** ADR-NNN (if applicable)

---

## Context

What is the situation that requires a decision?
What problem are we solving? What constraints exist?
Keep this factual — no opinions yet.

---

## Decision Drivers

- [Driver 1]
- [Driver 2]

---

## Options Considered

### Option A — [Name]

Brief description.

**Pros:**
- ...

**Cons:**
- ...

### Option B — [Name]

Brief description.

**Pros:**
- ...

**Cons:**
- ...

---

## Decision

**We choose Option [X].**

One paragraph explaining the choice. Be direct.

---

## Rationale

Deeper explanation of why this option over the others.
What tradeoffs are we consciously accepting?

---

## Consequences

**Positive:**
- ...

**Negative / Tradeoffs:**
- ...

**Constraints introduced:**
- [Reference to CONSTRAINTS.md rule if applicable]

---

## Implementation Notes

Anything a developer needs to know to implement this correctly.
Links to relevant files, patterns, or examples.

---

## Review Trigger

When should this decision be revisited?

- [ ] After X months
- [ ] When [specific condition] occurs
```

---

**After creating the ADR:**
1. Add entry to `docs/architecture/decisions/INDEX.md`
2. Reference in code with `# See ADR-NNN`
3. If superseding an older ADR, update old ADR's status

**Reference**: `docs/architecture/decisions/_TEMPLATE.md` (93 lines)
**Related**: narrare-dev/processes/adr-process · narrare-dev/lookup/adr-index
