<!-- Context: narrare-dev/navigation | Priority: critical | Updated: 2026-05-30 -->

# Narrare Dev Context — Navigation

Extracted context for the Narrare AI writing tool project.

**Source docs**: `docs/` (135 files) → **Extracted context**: 31 files (all <200 lines)

---

## constraints/ — Architecture Rules

| File | Source | Priority | Description |
|------|--------|----------|-------------|
| `rules.md` | CONSTRAINTS.md (766 lines) | critical | 23 machine-enforced rules, enforcement summary, approved exceptions |

---

## concepts/ — Core Ideas

| File | Source | Priority | Description |
|------|--------|----------|-------------|
| `glossary.md` | GLOSSARY.md (478 lines) | high | 50+ domain terms: architecture, prompts, domain, AI agents, frontend, wiki |
| `design-philosophy.md` | ui-principles.md (820 lines) | high | 6 design principles, sidebar layout paradigm, view routing, component conventions |
| `project-vision.md` | project-vision.md (212 lines) | medium | Why Narrare exists, target users, KB core, interface strategy |

---

## processes/ — Feature Lifecycle

| File | Source | Priority | Description |
|------|--------|----------|-------------|
| `quality-gates.md` | testing-standards.md (1224 lines) | high | 7 quality gates: test levels, coverage minimums, architecture, fakes, contracts, types, CI |
| `feature-pipeline.md` | architecture.md + AGENTS.md | high | 6-stage pipeline: idea → architecture → spec → implementation → validation → commit |
| `adr-process.md` | INDEX.md + _TEMPLATE.md | medium | ADR triggers, creation steps, naming, status lifecycle, INDEX.md requirements |

---

## domain/ — Architectural Knowledge

| File | Source | Priority | Description |
|------|--------|----------|-------------|
| `architecture-concepts.md` | CONSTRAINTS.md + TECH_STACK.md | high | Layer architecture, 4-client model, key patterns, event-driven, streaming, observability |
| `module-map.md` | directory-structure.md (788 lines) | high | Compact module location reference with cross-reference table for common tasks |

---

## examples/ — Code Patterns

| File | Source | Priority | Description |
|------|--------|----------|-------------|
| `python-patterns.md` | coding-standards.md (601 lines) | high | Python 3.14 typing, async, error handling, Result type, DI, SQLAlchemy, migration |
| `typescript-patterns.md` | coding-standards.md (601 lines) | high | React conventions, Tailwind v4, API client, i18n, proxy.ts (not middleware.ts) |
| `testing-patterns.md` | testing-standards.md (1224 lines) | high | Fake class pattern, TestModel, FunctionModel, capture_run_messages, fixtures |

---

## guides/ — How-To

| File | Source | Priority | Description |
|------|--------|----------|-------------|
| `testing.md` | testing-standards.md (1224 lines) | high | 3-level architecture, what gets tested, cross-layer contracts |
| `deployment.md` | deployment-guide.md (442 lines) | medium | Dev environment, CI/CD, Docker, env variables |
| `agent-creation.md` | how-to-add-an-agent.md (285 lines) | medium | 7-step NarrareAgent creation process |
| `prompt-quality.md` | prompt-content-standards.md (140 lines) | high | Mandatory prompt elements, quality checklist, ADR-037 manifest conformance |
| `orchestrator.md` | orchestrator.md (246 lines) | medium | Thinking Partner vs Router modes, agent mapping, briefing format |

---

## templates/ — Copy-Paste Scaffolds

| File | Source | Priority | Description |
|------|--------|----------|-------------|
| `adr-template.md` | _TEMPLATE.md (93 lines) | medium | ADR template with all required sections, ready to copy |
| `feature-scaffold.md` | architecture.md + INDEX.md | medium | Feature spec scaffold with frontmatter, compliance matrix, definition of done |

---

## lookup/ — Quick Reference

| File | Source | Priority | Description |
|------|--------|----------|-------------|
| `current-state.md` | CURRENT_STATE.md (181 lines) | critical | Phase 6 status, codebase stats, what's next, open questions |
| `directory-structure.md` | directory-structure.md (788 lines) | high | Canonical file locations for all modules |
| `design-tokens.md` | ui-principles.md (820 lines) | high | Color palette (light/dark), radii, typography, CSS architecture |
| `tech-stack.md` | TECH_STACK.md (343 lines) | medium | All dependencies with rationale, explicitly NOT used table |
| `justfile-commands.md` | deployment-guide.md (442 lines) | medium | All `just` commands |
| `adr-index.md` | architecture/decisions/INDEX.md | medium | 50 ADRs with status and affected modules |
| `feature-index.md` | features/INDEX.md (234 lines) | medium | Feature registry grouped by status |
| `mvp-plan.md` | mvp-plan.md (748 lines) | medium | Phases 0-6 summary, definition of done |

---

## standards/ — Mandatory Practices

| File | Source | Priority | Description |
|------|--------|----------|-------------|
| `architectural-discipline.md` | Project conventions | critical | Quality mandate, root cause first, no workarounds, sustainability check, streaming required |
| `architecture-rules.md` | CONSTRAINTS.md (766 lines) | critical | 23 machine-enforced rules with enforcement summary and approved exceptions |
| `code-graph-first.md` | AGENTS.md (MCP Tools) | critical | ALWAYS query graph before Read/Glob/Grep; tool selection guide, workflow, fallback rules |
| `prompt-standards.md` | prompt-standards.md (641 lines) | high | Prompt quality standards: system prompt consistency, evaluation framework, template patterns, ADR-037 manifest conformance |
| `python-standards.md` | coding-standards.md (Python) | high | Python 3.14 typing, naming, async, error handling, DI, SQLAlchemy, docstrings |
| `typescript-standards.md` | coding-standards.md (TypeScript) | high | React conventions, Tailwind v4, API client, i18n, RULE-15 (no middleware.ts) |

---

## Priority Reading Order

1. `constraints/rules.md` + `lookup/current-state.md` — every session
2. `standards/architectural-discipline.md` + `standards/architecture-rules.md` + `standards/code-graph-first.md` — architectural quality & graph discipline
3. `concepts/glossary.md` — when unclear on terminology
4. `domain/architecture-concepts.md` + `domain/module-map.md` — before creating files or understanding architecture
5. `standards/python-standards.md` / `standards/typescript-standards.md` — before writing code
6. `guides/testing.md` + `examples/testing-patterns.md` + `processes/quality-gates.md` — before writing tests
7. `lookup/design-tokens.md` + `concepts/design-philosophy.md` — before UI work
8. `processes/feature-pipeline.md` + `processes/adr-process.md` — before starting a new feature
9. `templates/adr-template.md` / `templates/feature-scaffold.md` — when creating ADRs or feature specs
