---
id: INFRA-002
title: "Unified Prompt System"
status: stable
area: infra
mvp: true

ui_tooltip: "Customizable AI prompts with cascade override system for genre and style."
ui_help_short: |
  Narrare's prompt system controls how the AI behaves when writing, analyzing,
  or working with your Knowledge Base. You can customize prompts per project
  to match your genre, style, or language preferences.
ui_help_long: |
  ## Unified Prompt System

  Every AI feature in Narrare uses prompts — instructions that tell the AI
  what to do. The prompt system manages these instructions in a unified way.

  **How prompts are organized:**
  - **Bundled prompts**: Default prompts built into Narrare
  - **User prompts**: Your custom prompts in `.narrare/prompts/`
  - **Project prompts**: Project-specific overrides (highest priority)

  **Prompt cascade:**
  When Narrare needs a prompt, it checks in this order:
  1. Project level (your project's `.narrare/prompts/`)
  2. Global level (your user-wide configuration)
  3. Bundled level (Narrare's defaults)

  **What you can customize:**
  - Genre-specific instructions (sci-fi vs fantasy behavior)
  - Tone guidelines (formal vs casual)
  - Language preferences (German vs English style)
  - Feature behavior (how aggressive rewriting should be, etc.)

  **Creating custom prompts:**
  1. Create a `.narrare/prompts/` directory in your project
  2. Copy the prompt you want to modify from the bundled prompts
  3. Edit it to match your preferences
  4. Changes take effect immediately

  Custom prompts work across all interfaces — Web UI, CLI, and MCP (Claude Desktop).

  If something goes wrong, you can reset to defaults by deleting your custom
  prompt files.
ui_available_in: [settings]

service: core/prompts/composer.py
contract: ~
router: ~
prompt: core/prompts/_bundled
requires: []
---

# INFRA-002 — Unified Prompt System

## What it does

Central prompt management system that assembles, customizes, and delivers
instructions to the LLM for every feature. Supports a cascade override system
(bundled → global → project) for genre-specific and user-specific customization.

## Why it exists

Without a unified prompt system, prompts would be scattered across features,
making it impossible to customize AI behavior globally. Writers need control
over how the AI writes — genre conventions, tone, language style — without
editing each feature individually.

## How it works (User perspective)

1. Most users never see the prompt system — it just works
2. To customize: Create `.narrare/prompts/` directory in your project
3. Find the prompt you want to override in Narrare's bundled prompts
4. Copy and modify it
5. Your custom prompt is used automatically

Advanced users can view and edit all prompts in Settings → Prompts.

## How it works (Technical)

**Entry point:** `core/prompts/composer.py`
**Primary class:** `PromptComposer`
**Registry:** `PromptRegistry` — discovers and loads all prompt files
**Variable engine:** Substitutes `{{project_title}}`, `{{language}}`, etc.
**Meta prompts:** Persona prompts in `prompts/_bundled/meta/{lang}/system.md`

**Prompt structure:**
```yaml
---
prompt_type: writing
prompt_language: en
prompt_version: "1.0.0"
---

## System Prompt
[Instructions with {{variables}}]

## First Message
[For interactive prompts only]
```

**Intent mapping:**
Each `LLMIntent` maps to:
- Category: `writing`, `kb`, `analysis`, `planning`
- Mode: `new_chapter`, `create`, `general`, `scene_planning`, etc.
- Language: `en`, `de`, `fr`

**Resolution order:**
1. `{project}/.narrare/prompts/{category}/{lang}/{mode}/system.md`
2. `{user}/.narrare/prompts/{category}/{lang}/{mode}/system.md`
3. `{bundled}/prompts/_bundled/{category}/{lang}/{mode}/system.md`

**Variable substitution:**
Supported variables: `{{project_title}}`, `{{genre}}`, `{{language}}`,
`{{tone}}`, `{{author}}`, `{{current_date}}`, `{{chapter_count}}`, etc.

## Constraints & Edge Cases

- Prompt files must be valid Markdown with YAML frontmatter
- Variables that can't be substituted are left as-is (with warning)
- Circular references in prompt includes are detected and rejected
- Prompt version is informational — no automatic migration
- Malformed prompts cause fallback to bundled version with error log

## Related Features

- [INFRA-001](INFRA-001-llm-gateway.md) — Gateway consumes composed prompts
- [INFRA-003](INFRA-003-context-assembly.md) — Context provides prompt variables
- [SET-002](../settings/SET-002-project-settings.md) — Settings exposes prompt UI

## Status & History

- `project-init` — Implemented as core infrastructure
- `2025-01-09` — Stable, fully implemented with variable engine
