---
name: check-constraints
description: Check if code changes violate Narrare's architecture constraints. Use when user asks "does this follow the rules", "is this compliant", "check constraints", "violates any rules", or before making structural changes.
---

## Check Constraints

Validates code changes against Narrare's 13 architecture rules defined in `docs/_shared/CONSTRAINTS.md`.

### Purpose

Ensure all code changes comply with the project's architecture constraints before implementation. This prevents technical debt and maintains consistency across the codebase.

### Steps

1. Read the relevant constraints from `docs/_shared/CONSTRAINTS.md`
2. Identify which rules apply to the planned changes
3. Check each applicable rule:
   - RULE-01: LLM calls go through Gateway only
   - RULE-02: Prompts built in core/prompts only
   - RULE-03: Contracts before implementation
   - RULE-04: File size limits
   - RULE-05: Module boundaries
   - RULE-06: One responsibility per file
   - RULE-07: Dependency direction
   - RULE-08: External integrations abstracted
   - RULE-09: Type signatures required
   - RULE-10: Tests not optional
   - RULE-11: No silent failures
   - RULE-12: Service Layer is only public API
   - RULE-13: Streaming and non-streaming share interface

4. Report any violations or concerns
5. Suggest compliant alternatives if violations found

### References

- `docs/_shared/CONSTRAINTS.md` — Full architecture rules
- `docs/development/coding-standards.md` — Python and TypeScript standards

### Common Violations to Check

- Direct LLM client imports outside `core/llm/`
- Prompt building via f-strings outside `core/prompts/`
- Missing Protocol definitions before implementation
- Files exceeding size limits (router: 150 lines, service: 300 lines)
- Business logic in routers
- Missing type annotations on public functions
- Silent exception handling (`except: pass`)

### Token Efficiency Rules

- Load only the relevant rules, not the entire CONSTRAINTS.md
- Focus on rules applicable to the specific change type
- Use `get_minimal_context` before checking code
