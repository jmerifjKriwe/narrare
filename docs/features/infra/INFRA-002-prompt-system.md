---
id: INFRA-002
title: "Unified Prompt System"
status: in-progress
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
  - **DB templates**: Runtime overrides saved via the UI (highest priority)
  - **Project prompts**: Project-specific overrides

  **Prompt cascade:**
  When Narrare needs a prompt, it checks in this order:
  1. DB templates (saved via Settings → Prompts)
  2. Project level (your project's `.narrare/prompts/`)
  3. Global level (your user-wide configuration)
  4. Bundled level (Narrare's defaults)

  **What you can customize:**
  - Genre-specific instructions (sci-fi vs fantasy behavior)
  - Tone guidelines (formal vs casual)
  - Language preferences (German vs English style)
  - Culture guidelines (naming conventions, worldbuilding patterns)
  - Feature behavior (how aggressive rewriting should be, etc.)

  **Managing prompts:**
  1. Open Settings → AI Prompts
  2. Browse prompts grouped by category (writing, generation, analysis, etc.)
  3. See which prompts have overrides (source indicators)
  4. Edit any prompt — variables are shown in a sidebar
  5. Compare your version with the original via side-by-side diff
  6. Reset to default when needed

  Custom prompts work across all interfaces — Web UI, CLI, and MCP (Claude Desktop).

  If something goes wrong, you can reset to defaults at any time.
ui_available_in: [settings]

service: core/prompts/composer.py
contract: ~
router: apps/api/narrare/prompts/router.py
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
**Management:** `PromptManagementService` — CRUD for overrides, update detection, diff comparison
**Variable engine:** Substitutes `{{project_title}}`, `{{language}}`, etc.
**Variable metadata:** `variable_metadata.py` — registry of variable descriptions for the UI
**Meta prompts:** Persona prompts in `prompts/_bundled/meta/{lang}/system.md`

### Culture Injection

The prompt system supports culture-aware generation via the `{{culture_guidelines}}`
placeholder. Culture definition files live in `prompts/_bundled/generation/{culture}/{lang}/`
and define naming conventions, phonetic rules, and style guidelines for each culture.

**Supported cultures:** `fantasy`, `modern`, `scifi`
**Supported languages:** `en`, `de`, `fr` (9 culture files total)

Culture resolution follows the standard cascade:
1. Project override: `{project}/.narrare/prompts/generation/{culture}/{lang}/culture.md`
2. Bundled default: `prompts/_bundled/generation/{culture}/{lang}/culture.md`
3. Fallback: EN version if the requested language isn't available

`PromptRegistry.resolve_culture()` handles the EN fallback automatically.

### Generation Intent Routing

The prompt system now supports generation intents:

| Intent | Category | Purpose |
|--------|----------|---------|
| `GENERATE` | `IntentCategory.GENERATION` | General-purpose generation |
| `NAME_GENERATE` | `IntentCategory.GENERATION` | Character/place name generation |
| `TITLE_GENERATE` | `IntentCategory.GENERATION` | Title suggestion generation |

Generation prompts are stored in `prompts/_bundled/generation/{lang}/` and follow
the same cascade resolution as other prompt categories.

### Preference Auto-Injection

`PromptComposer` automatically injects user preferences into prompts via
the `PromptContext` fields:
- `user_preferences` — Extracted style preferences from memory
- `avoidance_patterns` — Patterns the user has rejected
- `style_constraints` — Explicit style rules from settings

These are injected into the `{{user_preferences}}` block of system prompts,
allowing the AI to adapt to each writer's style without manual configuration.

### Prompt Management API

**Service:** `apps/api/narrare/prompts/service.py` — `PromptManagementService`
**Router:** `apps/api/narrare/prompts/router.py` — 7 endpoints:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/prompts` | List all prompts with source indicators |
| GET | `/prompts/{prompt_id}` | Get prompt content + metadata |
| PUT | `/prompts/{prompt_id}` | Save/update a prompt override |
| DELETE | `/prompts/{prompt_id}` | Reset to default (remove override) |
| GET | `/prompts/{prompt_id}/updates` | Check if bundled version has changed |
| GET | `/prompts/{prompt_id}/diff` | Side-by-side diff comparison |
| GET | `/prompts/variables` | List all available variables with descriptions |

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
- `2026-05-15` — Added generation intents, culture injection, preference auto-injection, prompt management API, variable metadata registry
