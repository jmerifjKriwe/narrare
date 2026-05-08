# Architecture Decision Records — Index

> **How to use this index:**
> Load this file to get an overview. Load individual ADR files only when you need
> the full reasoning. This keeps the context window clean.
>
> Location: `docs/agents/architecture/decisions/INDEX.md`
> Maintained by: Architecture Agent

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Accepted — in effect |
| 🔄 | Proposed — under discussion |
| ⛔ | Superseded — replaced by newer ADR |
| 🗄️ | Deprecated — no longer relevant |

---

## Decision Log

| ID | Title | Status | Date | Affects |
|----|-------|--------|------|---------|
| [ADR-001](ADR-001-llm-gateway.md) | Single LLM Gateway for all model calls | ✅ | init | `core/llm/` |
| [ADR-002](ADR-002-prompt-system.md) | Unified prompt system replacing three parallel implementations | ✅ | init | `core/prompts/` |
| [ADR-003](ADR-003-contracts-first.md) | Protocol-first development — contracts before implementation | ✅ | init | all domains |
| [ADR-004](ADR-004-file-size-limits.md) | Hard file size limits with enforcement | ✅ | init | all files |
| [ADR-005](ADR-005-directory-structure.md) | Module structure and ownership boundaries | ✅ | init | all modules |
| [ADR-006](ADR-006-tech-stack.md) | Technology choices and explicit exclusions | ✅ | init | all |

---

## How to Create a New ADR

1. Copy `_TEMPLATE.md` to `ADR-NNN-short-title.md`
2. Fill in all sections
3. Add a row to this index
4. Reference the ADR in any related code with: `# See ADR-NNN`
5. If the decision supersedes an older one, update the old ADR's status

---

## ADR Template

See `_TEMPLATE.md` in this directory.
