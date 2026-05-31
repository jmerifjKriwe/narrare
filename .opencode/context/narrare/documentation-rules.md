<!-- Context: narrare/documentation-rules | Priority: medium | Source: docs/features/INDEX.md + project conventions | Updated: 2026-05-31 -->

# Documentation Rules

Standards for all Narrare documentation — feature docs, help texts, i18n, CHANGELOG.

---

## Feature Doc Structure

Every feature file lives in `docs/features/{domain}/` and follows this schema:

| Section | Required | Purpose |
|---------|----------|---------|
| Frontmatter (YAML) | Yes | ID, status, area, MVP flag, UI text, developer refs |
| What it does | Yes | 1-3 sentences. Precise, no jargon. Becomes UI help text. |
| Why it exists | Yes | User problem solved. Connects to project vision. |
| How it works (User) | Yes | Step-by-step from user perspective. No implementation. |
| How it works (Technical) | Yes | Services, contracts, agent, prompt. Implementation details. |
| Constraints & Edge Cases | Yes | Limitations, failure behavior. |
| Related Features | Yes | IDs of interacting features. |
| Status & History | Yes | When added, significant changes. |

---

## Feature Frontmatter Required Fields

```yaml
id: WRITE-002              # Unique feature identifier
title: "Feature Name"
status: planned             # planned | in-progress | stable | deprecated
area: writing               # Feature area
mvp: false                  # MVP inclusion flag
ui_tooltip: "Max 80 chars"  # Short help text
ui_help_short: "Max 120 chars"  # One-line UI description
ui_help_long: |             # Detailed help (1-3 paragraphs)
  Full help text...
ui_available_in: [editor]   # UI contexts where help appears
service: domain/service.py  # Developer reference
contract: domain/contracts.py#ProtocolName
router: domain/router.py
prompt: core/prompts/_bundled/...
requires: [INFRA-001, ...]  # Dependency feature IDs
```

---

## INDEX.md Update Requirements

When adding or changing a feature:

1. Add row to appropriate area table in `docs/features/INDEX.md`
2. Include: ID (linked), Feature name, Status symbol, MVP flag
3. Update "Last updated" date at bottom of INDEX.md
4. Keep status symbols consistent: stable, in-progress, planned, idea, deprecated

---

## i18n Documentation Rules

- Every user-facing string must use `useTranslations()` — zero hardcoded English
- New translation keys must be added to **all 3 locales** (en, de, fr) in the same commit
- New namespaces must be registered in `lib/i18n/request.ts` (RULE-16)
- Validate with `packages/web/__tests__/i18n-namespace-registry.test.ts`

---

## Help Text Guidelines

| Field | Max Length | Voice | Purpose |
|-------|-----------|-------|---------|
| `ui_tooltip` | 80 chars | Knowledgeable friend | Hover help |
| `ui_help_short` | 120 chars | Knowledgeable friend | One-line description |
| `ui_help_long` | 3 paragraphs | Knowledgeable friend | Full help panel |

**Voice**: Write as a knowledgeable friend, not a technical manual. Explain outcomes, not mechanisms. Use the user's language (not developer jargon).

---

## CHANGELOG Conventions

- Every user-visible change gets a CHANGELOG entry
- Format: conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)
- Group by: Added, Changed, Fixed, Deprecated
- Include feature IDs where applicable

---

## Documentation Quality Checklist

Before any feature reaches `status: stable`:

- [ ] `ui_tooltip` exists (max 80 chars)
- [ ] `ui_help_short` exists (max 120 chars)
- [ ] `ui_help_long` exists (1-3 paragraphs)
- [ ] All user-facing strings extracted to i18n message files
- [ ] `ui_available_in` lists correct UI contexts
- [ ] Technical section is complete
- [ ] All public functions have docstrings (Google style)
- [ ] CHANGELOG entry exists (if user-visible change)
- [ ] Cross-references to related features are accurate
- [ ] Constraint references (RULE-XX) are accurate
- [ ] No TODO/FIXME placeholders in stable docs
- [ ] Failure-state documentation included
- [ ] API request/response schemas documented with examples
- [ ] Feature file frontmatter is accurate

---

## Documentation Debt Tracking

Incomplete documentation tracked in `docs/DEBT.md`. Goal: zero debt at every release.

| Entry | Content |
|-------|---------|
| Feature ID | Which feature has incomplete docs |
| Missing items | Specific doc items not yet done |
| Priority | blocking / non-blocking |
| Date filed | When the debt was identified |

---

**Reference**: `docs/features/INDEX.md`, `docs/development/coding-standards.md`
**Related**: narrare-dev/guides/prompt-quality · narrare-dev/lookup/feature-index
