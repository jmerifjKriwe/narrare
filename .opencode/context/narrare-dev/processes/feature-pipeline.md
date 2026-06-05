<!-- Context: narrare-dev/processes/feature-pipeline | Priority: high | Source: .opencode/agents/subagents/narrare-dev/architecture.md + AGENTS.md | Updated: 2026-05-31 -->

# Feature Development Pipeline

How a feature goes from idea to committed code. Each stage has a defined owner, required artifacts, and handoff criteria.

---

## Stage 1: Idea → Architecture Pre-Assessment

**Owner**: Architecture Specialist
**Input**: User request or feature idea
**Artifacts**: Decision to proceed (with or without ADR)

| Trigger | Action |
|---------|--------|
| New module or structural change | Write ADR → ADR review |
| New feature within existing module | Skip to Stage 2 |
| Tech stack change | ADR + TECH_STACK.md update |
| RULE-XX exception request | ADR + CONSTRAINTS.md exception entry |

**Gate**: Architecture Specialist confirms scope is clear. If unclear → back to user for clarification (Thinking Partner mode).

---

## Stage 2: Architecture → Specification

**Owner**: Architecture Specialist
**Input**: Scoped feature request
**Artifacts**: Feature spec (in `docs/features/`)

Spec must include:
- Feature ID, Name, Status
- Scope (what is IN and OUT)
- Root Cause / Motivation
- Layer breakdown (Core / Backend / Frontend)
- Module Boundaries (exact file paths per layer)
- Contracts (`Protocol` signatures)
- Data Model (Pydantic schemas, SQLAlchemy models)
- RULE-XX Compliance Matrix
- Definition of Done per layer

**Phases within this stage** (Architecture Specialist workflow):
1. **Analyze** — Understand requirements, check existing patterns
2. **Root Cause** — Identify the underlying problem (ask "why" 2x)
3. **Options** — Evaluate minimum 2 alternatives
4. **Specify** — Create the spec artifact
5. **Validate** — Check against all RULE-XX
6. **Handoff** — Document which specialist implements what

**Gate**: Spec passes Architecture Validation Checklist (all RULE-XX checked).

---

### Stage 2.5: Architecture → Semantic Review (NEW)

**Owner**: Architecture Specialist
**Input**: Validated feature spec
**Artifacts**: Semantic Review Checklist (signed off)

Vor der Implementation prüft der Architecture Specialist die Cross-Feature-Kohärenz:

- [ ] **Cross-Feature-Datenflüsse identifiziert?** — Welche Daten teilt das Feature mit anderen Features? (KB, Storyboard, Frontmatter, wiki, memory, settings, etc.)
- [ ] **Integration Contract definiert?** — Was passiert bei shared-data Änderung/Löschung? (Siehe RULE-03 Integration Contracts)
- [ ] **Intent-Semantik geprüft?** — Falls neuer LLMIntent: Scope-Beschreibung dokumentiert? Falls existierender Intent: gleiche Semantik?
- [ ] **i18n-Parität geprüft?** — Bundled Feature-Prompts: EN-only (ADR-026 Phase 5). Deklarierte lokalisierte Prompt-Familien (meta, universal): alle deklarierten Locales vorhanden. UI-i18n: en/de/fr (RULE-16).
- [ ] **Injection-Defense geprüft?** — Neue user-content Variablen in _USER_CONTENT_VARS? XML-Wrapping in Templates?
- [ ] **Template-Variablen registriert?** — Neue Variablen als user-authored, system-generated, oder feature-dynamic klassifiziert und in der passenden Registry erfasst?
- [ ] **PromptComposer-Routeability geprüft?** — Routeable Intent/Mode-Mappings haben ein bundled EN target oder explizite non-routeable rationale?
- [ ] **ADR-026 Capability-Erbe geprüft?** — Produktions-Agent-Pfade erben `NarrareMeta` + `NarrareUniversalRules` über `NarrareAgent`?
- [ ] **Kontext-Precedence geprüft?** — Current author instruction > project writing profile/manual override > current scene/storyboard/timeline > curated KB > learned memory/mem0 > generated suggestions; Konflikte werden nicht still gelöst.
- [ ] **KB-Status-Filtering beachtet?** — Falls KB-Daten: deprecated ausgeschlossen?
- [ ] **Token-Budget definiert?** — String-Truncation oder echtes Token-Counting?
- [ ] **ADR CI Impact dokumentiert?** — Betroffene Checker/Baselines/Tests/Derived Docs im ADR oder Feature Spec benannt?
- [ ] **Migration Completion geplant?** — Legacy-Pfade, stale comments/docstrings, Registry-Einträge und Regressionstests als Cleanup-DoD definiert?
- [ ] **RULE-22 Compliance?** — Cross-Feature Coherence Gate bestanden?

**Gate**: Semantic Review bestanden → Stage 3 (Implementation) freigegeben.

---

## Stage 3: Spec → Implementation

**Owner**: Implementation Specialist (per layer)
**Input**: Validated feature spec
**Artifacts**: Production code + tests

**Layer order** (dependencies flow downward):

| Order | Layer | Location | What gets built |
|-------|-------|----------|----------------|
| 1 | **Core** | `packages/core/narrare_core/` | Domain logic, contracts, LLM agents, prompts |
| 2 | **Backend** | `apps/api/narrare/` | Service, repository, router, schemas, models |
| 3 | **Frontend** | `packages/web/` | Components, stores, API client, i18n |

Each layer handoff includes:
- What was implemented
- What tests were written
- Any deviations from spec (with rationale)
- Risks or remaining work

---

## Stage 3.5: UX Review Gate

**Owner**: Coordinator or Testing Specialist
**Applies to**: Features with AI-powered interactions ONLY. Non-AI features skip.

### Does this feature need UX Review?

Answer YES if ANY apply:
- Feature calls an LLM endpoint
- Feature displays AI-generated content
- Feature has stop/cancel/abort for async operation
- Feature streams via SSE

### Checklist (all must pass before merge)

#### Streaming
- [ ] SSE used where backend provides SSE endpoint (§16.1)
- [ ] No REST-only fallback for SSE-capable endpoints

#### User Controls
- [ ] Cancel/Abort present for operations >2s (§16.2)
- [ ] Accept/Reject flow from `studio.aiActions.*` (§16.4, §16.6)
- [ ] No auto-apply without user confirmation
- [ ] Undo available after accepting

#### Loading
- [ ] Visual feedback <200ms (§16.3)
- [ ] Three-state lifecycle: Idle → Loading → Streaming → Complete

#### Action Labels
- [ ] Canonical `studio.aiActions.*` vocabulary used
- [ ] No deprecated key references
- [ ] 3-locale parity (de/en/fr)

#### Error Handling
- [ ] Actionable error messages (§16.5)
- [ ] Retry available after errors

#### Connection Resilience
- [ ] Connection loss preserves partial output (§16.7)
- [ ] Retry offered

#### Onboarding
- [ ] Feature discoverable from logical location
- [ ] Tooltip present if non-obvious pattern
- [ ] Keyboard shortcuts documented in SettingsView

#### Accessibility
- [ ] ARIA labels on AI indicators
- [ ] Focus management after AI output

**Gate**: All applicable items resolved. "N/A" items have written justification.
**Escalation**: Unsatisfiable items require Architecture Specialist exception approval.

---

## Stage 4: Implementation → Validation

**Owner**: Testing Specialist
**Input**: Implemented code
**Artifacts**: Test results, coverage report

Must pass all quality gates (see `processes/quality-gates.md`):
- Unit tests with coverage minimums
- Integration tests (if DB/router changes)
- Cross-layer contract tests (if API changes)
- Architecture constraint check
- Fake conformance (if new Fakes added)
- Type checking (`mypy --strict`)

**Gate**: All quality gates pass. No coverage gaps below minimums.

---

## Stage 5: Validation → Documentation Gate

**Owner**: Documentation Specialist
**Input**: Validated implementation
**Artifacts**: Updated documentation

Documentation Gate checklist (14 items):
- `ui_tooltip`, `ui_help_short`, `ui_help_long`
- i18n strings extracted
- Feature file frontmatter accurate
- CHANGELOG entry (if needed)
- Cross-references correct
- No TODO/FIXME placeholders
- API schemas documented
- Failure-state documentation

**Gate**: Documentation Gate passed. Feature file status updated.

---

## Stage 6: Documentation → Commit

**Owner**: Coordinator (orchestrator)
**Input**: All gates passed
**Artifacts**: Git commit

Before committing:
1. Verify all gates passed
2. Stage only intended files
3. Verify no secrets in diff
4. Commit with conventional message

---

## Specialist Ownership Summary

| Specialist | Owns Stages | Key Artifacts |
|-----------|-------------|---------------|
| Architecture | 1, 2 | ADR, Feature Spec, Contracts |
| Implementation | 3 | Production code (per layer) |
| Testing | 4 | Tests, coverage report |
| Documentation | 5 | Feature docs, i18n, CHANGELOG |
| Coordinator | 6 (oversight) | Git commit |

---

**Reference**: `.opencode/agents/subagents/narrare-dev/architecture.md`, `AGENTS.md`
**Related**: narrare-dev/processes/quality-gates · narrare-dev/processes/adr-process · narrare-dev/templates/feature-scaffold
