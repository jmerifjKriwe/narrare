<!-- Context: narrare/navigation | Priority: critical | Updated: 2026-06-03 -->

# Narrare Context Navigation

> Project-specific context for the Narrare AI writing tool.

---

## Quick Start

New here? → `.opencode/context/narrare-dev/navigation.md`

---

## Structure

```
.opencode/context/
├── narrare-dev/         ← Narrare development context (PRIMARY)
│   ├── constraints/     — Architecture rules (RULE-XX)
│   ├── concepts/        — Core ideas (glossary, vision, design)
│   ├── processes/       — Feature lifecycle (quality gates, ADR, pipeline)
│   ├── domain/          — Architecture knowledge (module map, concepts)
│   ├── examples/        — Code patterns (Python, TypeScript, testing)
│   ├── guides/          — How-to (testing, deployment, agent creation)
│   ├── templates/       — Scaffolds (ADR, feature spec)
│   ├── lookup/          — Quick reference (current state, tech stack, ADR index)
│   └── standards/       — Mandatory practices (arch discipline, graph-first)
├── narrare/             ← Narrare documentation rules
├── project/             ← Project-level context
└── navigation.md        ← This file
```

---

## Priority Reading Order

1. `narrare-dev/lookup/current-state.md` + `narrare-dev/constraints/rules.md` — every session
2. `narrare-dev/standards/architectural-discipline.md` + `narrare-dev/standards/code-graph-first.md` — quality gates
3. `narrare-dev/domain/architecture-concepts.md` + `narrare-dev/domain/module-map.md` — before creating files
4. `narrare-dev/standards/python-standards.md` or `narrare-dev/standards/typescript-standards.md` — before writing code

---

## Archived

Legacy OpenAgents Control assets are preserved in `.opencode/_archived/oac-legacy/`.
