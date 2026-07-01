---
id: PROMPT-001
title: "File-based Prompt Overrides"
status: implemented
area: prompts
mvp: false

ui_tooltip: "Customize AI prompts by editing files in your project directory."
ui_help_short: |
  Override any AI prompt by creating a file in your project's `.narrare/prompts/`
  directory. Changes take effect immediately and apply to all AI operations in
  that project.
ui_help_long: |
  ## File-based Prompt Overrides

  Create custom versions of any AI prompt by placing files in your project's
  `.narrare/prompts/` directory. This is the second-highest priority in the
  prompt cascade — only DB templates (saved via the UI) override file-based
  overrides.

  **How it works:**

  1. Create .narrare/prompts/{category}/{language}/{mode}/system.md
  2. The file must be valid Markdown with YAML frontmatter
  3. Use `{{variables}}` from the variable registry (shown in UI sidebar)
  4. Include `override_of_version` in frontmatter to track which bundled version you modified
  5. Changes take effect on next AI call

  **Override tracking:**
  When you copy a bundled prompt to create an override, the system tracks which
  version you started from. If a Narrare update changes the bundled prompt, the
  UI shows an update badge so you can compare and merge changes.

  **Diff comparison:**
  Use Settings → AI Prompts to see a side-by-side comparison between your
  override and the current bundled version. This helps you understand what
  changed and whether to merge updates.

  **When to use file overrides:**
  - Project-specific genre conventions
  - Language-specific style rules
  - Culture definitions for name generation
  - Custom system personas for specific workflows

  File overrides are version-control friendly — commit your `.narrare/` directory
  to share custom prompts with collaborators.
ui_available_in: [settings]

service: packages/core/narrare_core/prompts/registry.py
contract: ~
router: apps/api/narrare/prompts/router.py
prompt: packages/core/narrare_core/prompts/_bundled
requires: [INFRA-002]
---

# PROMPT-001 — File-based Prompt Overrides

## What it does

Allows writers to customize any AI prompt by creating override files in their
project's `.narrare/prompts/` directory. These overrides sit in the prompt
cascade between bundled defaults and DB templates.

## Why it exists

Every writer has different preferences for how the AI should behave. Genre
conventions, tone, language style, and worldbuilding rules vary by project.
File-based overrides give writers direct, version-control-friendly control
over AI behavior without needing the UI.

## How it works (User perspective)
1. Create .narrare/prompts/{category}/{language}/{mode}/system.md

2. Write your custom prompt (Markdown with YAML frontmatter)
3. Optionally add `override_of_version` to track the source version
4. The override is detected automatically on next prompt resolution
5. Check Settings → AI Prompts to see your override with source indicator
6. Use diff comparison to see differences from bundled version
7. If Narrare updates the bundled prompt, an update badge appears

## How it works (Technical)

**Resolution order in cascade:**
1. DB templates (highest priority, saved via API)
2. **Project file**: {project}/.narrare/prompts/{category}/{lang}/{mode}/system.md ← this feature
3. Global user file: {user}/.narrare/prompts/{category}/{lang}/{mode}/system.md
4. Bundled: packages/core/narrare_core/prompts/_bundled/{category}/{lang}/{mode}/system.md

**Override detection:**
`PromptRegistry` scans for override files during resolution. If a file exists
at the project or global path, it's loaded instead of the bundled version.

**Version tracking:**
Override files can include `override_of_version` in frontmatter:
```yaml
---
prompt_type: generation
prompt_language: en
prompt_version: "1.0.0"
override_of_version: "1.0.0"  # Which bundled version this was based on
---
```

**Update detection:**
`PromptManagementService` compares `override_of_version` with the current
bundled version. If they differ, the override is flagged as having a pending
update. The API endpoint `GET /prompts/{id}/updates` returns this status.

**Diff comparison:**
`GET /prompts/{id}/diff` returns a side-by-side comparison of the override
content vs. the current bundled content, allowing users to review and merge
changes from Narrare updates.

**Frontend UI:**
- `packages/web/components/studio/settings/PromptsTab.tsx` — Shows all prompts with source indicators (bundled, file override, DB override)
- `packages/web/components/studio/settings/PromptEditor.tsx` — Edit mode with variables sidebar showing available `{{variables}}`
- `packages/web/components/studio/settings/PromptDiff.tsx` — Side-by-side diff comparison between override and bundled version

## Constraints & Edge Cases

- Override files must be valid Markdown with YAML frontmatter
- Variables that can't be substituted are left as-is with a warning
- Malformed overrides cause fallback to bundled version with error log
- Override detection requires file system access (works in local mode, may be limited in hosted mode)
- Version tracking is informational — no automatic migration when bundled prompts change
- File overrides are not visible in the DB template system — they're separate layers in the cascade

## Related Features

- [INFRA-002](../infra/INFRA-002-prompt-system.md) — Parent prompt system
- [PROMPT-002](PROMPT-002-db-templates.md) — DB templates (higher priority in cascade)
- [SET-002](../settings/SET-002-project-settings.md) — Settings UI for prompts

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-15` — Prompt management API implemented with override detection, update badges, diff comparison, and frontend editor UI
