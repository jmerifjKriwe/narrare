<!-- Context: narrare-dev/templates/feature-scaffold | Priority: medium | Source: .opencode/agents/subagents/narrare-dev/architecture.md + docs/features/INDEX.md | Updated: 2026-05-31 -->

# Feature Spec Scaffold

Copy this scaffold when creating a new feature spec. Fill in all sections. Place in `docs/features/{domain}/`.

---

```markdown
# [FEATURE-ID] — [Feature Name]

---
id: [DOMAIN]-[NNN]
name: "[Feature Name]"
status: planned          # planned | in-progress | stable | deprecated
area: [domain]           # writing | kb | analysis | planning | setup | etc.
mvp: false               # included in first running version?

# UI text — consumed by frontend help system
ui_tooltip: "Short help text (max 80 chars)"
ui_help_short: |
  One-line description for UI (max 120 chars).
ui_help_long: |
  Detailed help for UI (1-3 paragraphs). Markdown supported.
ui_available_in: [editor, chapter-list]  # where the help icon appears

# Developer reference
service: [domain]/[service_file].py
contract: [domain]/contracts.py#[ProtocolName]
router: [domain]/router.py
prompt: core/prompts/_bundled/[domain]/[prompt_file]
requires: [INFRA-001, INFRA-002, ...]  # feature IDs this depends on
---

## Scope

### In Scope
- [What this feature does]

### Out of Scope
- [What this feature explicitly does NOT do]

## Root Cause / Motivation

What user problem does this solve? Connect to project vision.
Min 2x "Why?" to reach the fundamental need.

## Layer Breakdown

### Core (packages/core/narrare_core/)
- [Domain logic, contracts, agent definitions]
- Files: [list exact paths]

### Backend (apps/api/narrare/)
- [Service, repository, router, schemas, models]
- Files: [list exact paths]

### Frontend (packages/web/)
- [Components, stores, API client, i18n]
- Files: [list exact paths]

## Module Boundaries

| Layer | File Path | Responsibility |
|-------|-----------|----------------|
| Core | `packages/core/narrare_core/[domain]/contracts.py` | Protocol definitions |
| Core | `packages/core/narrare_core/[domain]/[service].py` | Domain logic |
| Backend | `apps/api/narrare/[domain]/service.py` | Business logic |
| Backend | `apps/api/narrare/[domain]/repository.py` | DB queries |
| Backend | `apps/api/narrare/[domain]/router.py` | HTTP endpoints |
| Backend | `apps/api/narrare/[domain]/schemas.py` | Request/response models |
| Frontend | `packages/web/components/[area]/Component.tsx` | UI component |
| Frontend | `packages/web/lib/api/[domain].ts` | API client |

## Contracts (Protocol Signatures)

[Domain]/contracts.py:

[Protocol definitions with full type annotations]
[Async signatures for I/O operations]
[Error types (Result[T, E] where appropriate)]
[Streaming/non-streaming shared interface (RULE-13)]

## Data Model

### Pydantic Schemas
[Request and response models]

### SQLAlchemy Models
[DB table definitions]

### Migrations Required
[Alembic migration files needed (RULE-14)]

## RULE-XX Compliance Matrix

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | [status] | [how satisfied] |
| RULE-02 | [status] | [how satisfied] |
| RULE-03 | [status] | [how satisfied] |
| RULE-04 | [status] | [how satisfied] |
| RULE-05 | [status] | [how satisfied] |
| RULE-06 | [status] | [how satisfied] |
| RULE-07 | [status] | [how satisfied] |
| RULE-10 | [status] | [how satisfied] |
| RULE-11 | [status] | [how satisfied] |
| RULE-12 | [status] | [how satisfied] |
| RULE-13 | [status] | [how satisfied] |
| RULE-16 | [status] | [how satisfied] |
| RULE-17 | [status] | [how satisfied] |

## Definition of Done

### Core Layer
- [ ] Contracts defined (Protocol classes)
- [ ] Domain logic implemented
- [ ] Unit tests: 3+ per public method
- [ ] Coverage: core minimum 90%

### Backend Layer
- [ ] Service, repository, router implemented
- [ ] Schemas with full type annotations
- [ ] Alembic migration (if DB changes)
- [ ] Integration tests for router endpoints
- [ ] Coverage: API minimum 80%
- [ ] Contract tests (RULE-17, RULE-18)

### Frontend Layer
- [ ] Components implemented
- [ ] API client typed
- [ ] i18n strings extracted (RULE-16)
- [ ] Namespace registered in request.ts
- [ ] UI tests for key interactions

### Cross-Cutting
- [ ] All quality gates pass
- [ ] Documentation gate passed
- [ ] Feature file frontmatter accurate
- [ ] INDEX.md updated
```

---

**After creating the feature spec:**
1. Add entry to `docs/features/INDEX.md` in the appropriate area
2. If MVP=true: add to `MVP_PLAN.md` implementation list
3. Submit to Architecture Agent for review before implementation

**Reference**: `.opencode/agents/subagents/narrare-dev/architecture.md`, `docs/features/INDEX.md`
**Related**: narrare-dev/processes/feature-pipeline · narrare-dev/processes/adr-process · narrare-dev/constraints/rules
