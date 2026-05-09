---
name: narrare-documentation
description: Write and maintain feature docs, developer docs, and i18n help texts. Use when user asks about "documentation", "docs", "help text", "changelog", or specifies documentation-related work.
---

## Narrare Documentation

Ensures every function is documented for users, developers, and agents. No feature reaches "stable" without complete documentation.

### Purpose

Maintain all project documentation so that users can use features, developers can understand the codebase, and agents have accurate context.

### Steps

1. **Feature Documentation** — `docs/features/` registry:
   - Every feature has a spec file
   - Includes: purpose, requirements, edge cases, dependencies
   - Status tracking: draft → specified → implemented → stable

2. **Developer Documentation** — `docs/development/`:
   - Coding standards
   - Testing standards
   - UI principles
   - Deployment guide
   - Orchestrator guidelines

3. **Reference Documentation** — `docs/reference/`:
   - Directory structure
   - Project vision
   - Architecture decisions

4. **i18n Help Texts** — All user-facing strings:
   - English source in `packages/i18n/locales/en/`
   - Keys needed for all languages (DE, FR, etc.)
   - Context provided for translators

5. **CHANGELOG.md** — Maintain release notes:
   - Grouped by type: Added, Changed, Fixed, Removed
   - Linked to issues/commits where relevant

6. **Documentation Gate** — Block incomplete features:
   - No feature reaches "stable" without:
     - Feature spec complete
     - API documented
     - UI help texts added
     - i18n keys provided for all languages

### References

- `docs/features/INDEX.md` — Feature registry
- `docs/development/` — Developer documentation
- `packages/i18n/` — Translation keys

### Documentation Types

| Type | Location | Audience |
|------|----------|----------|
| Feature specs | `docs/features/` | Product, developers |
| Architecture | `docs/architecture/` | Architects, developers |
| Development | `docs/development/` | Developers, agents |
| Reference | `docs/reference/` | All |
| i18n | `packages/i18n/locales/` | Translators, users |
| Changelog | `CHANGELOG.md` | Users, developers |

### What You Don't Do

- Write production code (Implementation Agent)
- Define architecture (Architecture Agent)
- Write tests (Testing Agent)
- Do translations (separate process)

### Token Efficiency Rules

- Start with `get_minimal_context(task="documentation ...")`
- Focus on the specific feature or area being documented
- Read only relevant existing documentation
