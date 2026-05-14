---
id: SET-002
title: "Project Settings"
status: in-progress
area: settings
mvp: true

ui_tooltip: "Override AI model and token limits for this project."
ui_help_short: |
  Set project-specific AI model overrides and token limits that take precedence
  over your user-level defaults. Use a different model for a genre-specific project
  without changing your global settings.
ui_help_long: |
  Project Settings let you override AI behavior for a specific novel or project.
  If your default model works for most projects but you want Claude for a literary
  novel and GPT-4o for a technical thriller, project-level overrides make that
  possible without changing your global defaults.

  You can override models per category (writing, analysis, kb, etc.) and per
  individual intent, and set project-specific token limits. The settings page
  shows where each override comes from — "from project", "from user", or "default" —
  so you always know which configuration is active.
ui_available_in: [project-settings]

service: settings/project_service.py
contract: settings/contracts.py#ProjectSettingsRepositoryProtocol
router: settings/router.py
prompt: ~
requires: [SET-001, INFRA-001]
---

# SET-002 — Project Settings

> **Status:** 🔨 In Progress
> **Last updated:** 2026-05-14

## What it does

Project Settings let writers override AI model selection and token limits for a specific project, taking precedence over their user-level defaults. This enables genre-specific or project-specific AI tuning without affecting other projects.

## Why it exists

Different writing projects benefit from different AI behavior. A literary novel may need Claude's nuanced prose, while a technical thriller benefits from GPT-4o's structured reasoning. Without project-level overrides, writers would need to change their global settings every time they switch projects.

## How it works (User perspective)

1. The writer opens a project and navigates to **Project Settings → AI**
2. They see their effective settings with source indicators: "from project", "from user", "default"
3. They override a category — e.g., set "writing" to use a different model for this project
4. They optionally set project-level token limits
5. All AI features within this project now use the project overrides

## How it works (Technical)

**Entry point:** `settings/router.py` → `/settings/ai/novels/{novel_id}`
**Service:** `ProjectAiSettingsService` — project-level overrides, effective settings resolution with source metadata
**Contract:** `ProjectAiSettingsRepositoryProtocol` in `settings/contracts.py`
**Database:** JSONB columns on `project_settings` — `category_overrides`, `intent_overrides`, `token_limit_overrides`
**REST API:**
- `GET /settings/ai/novels/{novel_id}` — get project AI settings with source metadata
- `PATCH /settings/ai/novels/{novel_id}` — update project AI overrides

**Cascade:** Project-level intent → Project-level category → User-level intent → User-level category → User default → Error

## Constraints & Edge Cases

- Project overrides cascade over user settings — if both exist, project wins
- Source metadata is returned in the response for transparency (which level each setting comes from)
- Project overrides can reference any of the user's active providers
- If a referenced provider is deactivated, the override becomes invalid and the system falls through to the next cascade level

## Related Features

- [SET-001](SET-001-user-settings.md) — User-level defaults that project settings override
- [SET-003](SET-003-model-config.md) — The model routing cascade
- [INFRA-001](../infra/INFRA-001-llm-gateway.md) — The gateway that receives resolved config

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-14` — Updated: AI category/intent/token limit overrides, source metadata, service layer
