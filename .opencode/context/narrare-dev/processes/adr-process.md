<!-- Context: narrare-dev/processes/adr-process | Priority: medium | Source: docs/architecture/decisions/INDEX.md + _TEMPLATE.md | Updated: 2026-06-17 -->

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

## Mandatory Retrofit-Plan for Prompt-Mechanics ADRs (D.4)

> **Source:** ADR-046 §Prevention Infrastructure D.4

Any ADR that changes prompt mechanics MUST include a **Retrofit-Plan** section.
This requirement addresses root cause C.1 from ADR-046 (the temporal gap): an
ADR must not only describe the correct end state but also explicitly list what
existing code must change to reach it. ADR-026 lacked such a plan for feature-
prompt path compliance, which is why four drift paths survived its adoption.

An ADR without a Retrofit-Plan for prompt-mechanics changes is **rejected** at
Stage 5 (Validate).

### When a Retrofit-Plan is Required

A Retrofit-Plan section is mandatory for any ADR that does any of the following:

| Trigger | Example |
|---------|---------|
| Adds, modifies, or removes a prompt injection mechanism | New Capability, new `@agent.instructions` pattern, removing `MetaPromptLoader` |
| Changes how PromptComposer resolves prompts | New cascade step, new route-table semantics, new substitution engine |
| Introduces a new `LLMIntent` or route | Adding `LLMIntent.NEW_FEATURE` to the intent-to-category mapping |
| Modifies the Capability system | Changing `AbstractCapability` contract, adding/renaming a Capability |
| Changes template variable substitution | New `{{variable}}` syntax, new variable-engine behaviour, new `PromptContext` field semantics |

### Retrofit-Plan Section Contents

The Retrofit-Plan section must contain all five of the following:

1. **Inventory of affected paths** — List every existing code path that uses
   the mechanism being changed (file + symbol, with line references where
   applicable). The CR-Audit process and `check_architecture.py` output are the
   primary inputs.

2. **Migration steps per path** — For each affected path: what changes, in
   which file, and in what order. Each step should be atomic and independently
   testable.

3. **Breaking-change assessment** — Which paths break during migration, and
   how backward compatibility is maintained (or why a hard cutover is safe).
   Call out any `Deps`/`Protocol`/schema changes explicitly.

4. **Checker update plan** — How `check_architecture.py` (or
   `check_prompt_structure.py` / `check_adoption.py`) is updated to enforce
   the new mechanism. Identify which checker module changes and what new
   baseline (if any) is ratcheted.

5. **Test update plan** — How existing tests are updated to verify the new
   path, and which new Prompt-Path-Compliance tests (ADR-046 §D.1) are added.
   Call out any currently-untested paths that gain coverage.

### Enforcement

The Architecture Specialist verifies the Retrofit-Plan exists during ADR review
(Stage 5 — Validate). An ADR that meets any trigger above and omits the
Retrofit-Plan is rejected with an explicit request to add it.

**Example:** ADR-046 is the reference implementation — its §Retrofit Plan
section provides the migration specification that ADR-026 was missing for
feature-prompt path compliance.

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
