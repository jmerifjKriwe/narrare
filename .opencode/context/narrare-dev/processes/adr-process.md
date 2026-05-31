<!-- Context: narrare-dev/processes/adr-process | Priority: medium | Source: docs/architecture/decisions/INDEX.md + _TEMPLATE.md | Updated: 2026-05-31 -->

# ADR Process — Architecture Decision Records

How to create, maintain, and retire Architecture Decision Records in Narrare.

---

## When to Write an ADR

| Trigger | ADR Required? |
|---------|--------------|
| New architectural pattern or module | Yes |
| New external dependency | Yes |
| RULE-XX exception | Yes |
| Tech stack change | Yes |
| Interface/API change affecting multiple modules | Yes |
| Bug fix < 20 lines | No (root cause in commit message) |
| Feature within existing patterns | No (feature spec suffices) |

---

## ADR Creation Steps

1. **Copy template**: `_TEMPLATE.md` → `ADR-NNN-short-title.md`
2. **Fill all sections** (see template overview below)
3. **Add row to INDEX.md**: ID, title, status, date, affected modules
4. **Reference in code**: `# See ADR-NNN` where the decision applies
5. **If superseding**: update old ADR's status to "Superseded by ADR-NNN"

---

## Template Section Overview

| Section | Purpose | Required |
|---------|---------|----------|
| **Status** | Current lifecycle state | Yes |
| **Context** | Factual situation requiring a decision | Yes |
| **Decision Drivers** | Forces shaping the decision | Yes |
| **Options Considered** | Minimum 2 alternatives with pros/cons | Yes |
| **Decision** | Chosen option with direct rationale | Yes |
| **Rationale** | Deeper explanation of tradeoffs accepted | Yes |
| **Consequences** | Positive, negative, constraints introduced | Yes |
| **Implementation Notes** | Developer-facing guidance, links | Recommended |
| **Review Trigger** | When to revisit this decision | Yes |

---

## Naming Convention

```
ADR-NNN-short-kebab-title.md
```

- `NNN`: three-digit sequential number (pad with zeros)
- Title: short, descriptive, kebab-case
- Example: `ADR-015-agents-first-class.md`

---

## Status Lifecycle

```
Proposed → Accepted → (active)
                    → Superseded (by newer ADR)
                    → Deprecated (no longer relevant)
```

| Status | Symbol | Meaning |
|--------|--------|---------|
| Proposed | :arrows_counterclockwise: | Under discussion, not yet approved |
| Accepted | :white_check_mark: | Approved and in effect |
| Superseded | :no_entry_sign: | Replaced by a newer ADR |
| Deprecated | :card_file_box: | No longer relevant |

---

## INDEX.md Update Requirement

Every new or status-changed ADR **must** update the Decision Log table in `docs/architecture/decisions/INDEX.md`:

| Column | Content |
|--------|---------|
| ID | Link to ADR file |
| Title | Short description |
| Status | Current status symbol |
| Date | YYYY-MM-DD or "init" |
| Affects | Modules/domains impacted |

---

## Current ADR Count: 22

See `docs/architecture/decisions/INDEX.md` for the full list.

---

**Reference**: `docs/architecture/decisions/INDEX.md` (64 lines), `docs/architecture/decisions/_TEMPLATE.md` (93 lines)
**Related**: narrare-dev/templates/adr-template · narrare-dev/lookup/adr-index
