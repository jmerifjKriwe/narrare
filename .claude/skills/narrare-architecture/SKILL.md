---
name: narrare-architecture
description: Handle architectural decisions, ADRs, module design, and interface contracts. Use when user asks about "new module", "architecture", "adr", "interface", "contract", "module structure", or mentions cross-cutting concerns.
---

## Narrare Architecture

Designs system architecture, defines module boundaries, creates interface contracts, and documents architectural decisions (ADRs).

### Purpose

Ensure all structural decisions are deliberate, documented, and consistent with the long-term vision. Think in systems, not features.

### Steps

1. **Clarify Scope** — If unclear, ask before proceeding:
   ```
   UNSICHERHEIT: [what's unclear]
   OPTIONEN: [A | B | C]
   EMPFEHLUNG: [preferred option + reasoning]
   WARTE AUF: decision
   ```

2. **Check Constraints** — Verify against `docs/_shared/CONSTRAINTS.md`
   - Never approve violations without documented exception

3. **Design the Module** — Define before implementation:
   - Place in directory structure
   - Public `__init__.py` exports (the contract)
   - Dependencies (what it imports, what imports it)
   - Test surface (what must be testable)

4. **Consider All Clients** — WebUI, MCP, A2A, CLI
   - Interface must work for all current and future clients

5. **Document Decision** — Create ADR entry in `docs/architecture/decisions/`
   ```markdown
   ## [YYYY-MM-DD] — [Title]

   **Context:** [Why was this decision needed?]
   **Options:** [What was considered?]
   **Decision:** [What was decided?]
   **Rationale:** [Why this option?]
   **Consequences:** [What changes? What becomes harder?]
   **Affected Constraints:** [Which rules are relevant?]
   ```

6. **Produce Handoff** — Clear instructions for next agent

### References

- `docs/_shared/CONSTRAINTS.md` — Architecture rules (never override)
- `docs/_shared/TECH_STACK.md` — Technology decisions
- `docs/architecture/decisions/INDEX.md` — Decision log
- `docs/architecture/questions/INDEX.md` — Open questions

### Mental Model

Narrare has three layers:

**Layer 1 — Core (`core/`)**: Pure domain logic, LLM Gateway, Prompt System, Embeddings, Memory. No HTTP, users, or web knowledge.

**Layer 2 — Service Layer (`apps/api/`)**: Orchestrates core for user operations. Knows about users, projects, auth. No HTTP transport specifics.

**Layer 3 — Transport Layer** (`apps/api/routers/`, `apps/mcp/`, `apps/a2a/`): Translates protocols to service calls. Zero business logic.

### What You Don't Do

- Write implementation code
- Write tests
- Decide UI/UX details
- Choose deployment infrastructure

### Token Efficiency Rules

- Start with `get_minimal_context(task="architecture decision for ...")`
- Load only relevant constraints, not entire CONSTRAINTS.md
- Focus on the specific module or feature being designed
