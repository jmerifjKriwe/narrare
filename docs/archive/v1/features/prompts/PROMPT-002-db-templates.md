---
id: PROMPT-002
title: "User DB Prompt Templates"
status: implemented
area: prompts
mvp: false

ui_tooltip: "Save and manage prompt overrides through the Settings UI."
ui_help_short: |
  Customize AI prompts directly in the Settings UI. DB templates have the
  highest priority and override both file-based and bundled prompts.
ui_help_long: |
  ## User DB Prompt Templates

  DB templates are the highest-priority layer in the prompt cascade. When you
  edit a prompt in Settings → AI Prompts and save it, the override is stored
  in the database and takes precedence over all other prompt sources.

  **How it works:**

  1. Open Settings → AI Prompts
  2. Browse prompts grouped by category
  3. Click any prompt to open the editor
  4. See available variables in the sidebar
  5. Edit the prompt content
  6. Save — your override is immediately active

  **Source indicators:**
  Each prompt shows its current source:
  - **Bundled** — Default from Narrare
  - **File** — Override from `.narrare/prompts/`
  - **DB** — Override saved via this feature (highest priority)

  **Update badges:**
  When Narrare updates a bundled prompt, prompts with overrides show an update
  badge. Use the diff view to compare your version with the new default, then
  decide whether to merge or keep your override.

  **Reset:**
  Delete a DB template to fall back to file-based or bundled prompts.

  **When to use DB templates:**
  - Quick edits without touching files
  - Hosted Narrare instances (no file system access)
  - Per-user customization on shared projects
  - Experimenting before committing to a file override
ui_available_in: [settings]

service: apps/api/narrare/prompts/service.py
contract: apps/api/narrare/prompts/contracts.py
router: apps/api/narrare/prompts/router.py
prompt: ~
requires: [INFRA-002, PROMPT-001]
---

# PROMPT-002 — User DB Prompt Templates

## What it does

Database-backed prompt override system with the highest priority in the cascade.
Users can create, edit, compare, and reset prompt overrides through the Settings UI
without touching the file system.

## Why it exists

File-based overrides require file system access and technical comfort. DB templates
make prompt customization accessible to all users through the UI, especially in
hosted or multi-user environments where file system access isn't available.

## How it works (User perspective)

1. Open Settings → AI Prompts
2. Browse prompts grouped by category (writing, generation, analysis, etc.)
3. Source indicators show where each prompt comes from
4. Click to edit — editor opens with variables sidebar
5. Save changes — stored in database, immediately active
6. Compare with bundled version via side-by-side diff
7. Reset to default when needed (deletes DB override, falls back to file/bundled)

## How it works (Technical)

**Service:** `apps/api/narrare/prompts/service.py` — `PromptManagementService`
**Contract:** `apps/api/narrare/prompts/contracts.py` — `PromptManagementProtocol`
**Schemas:** `apps/api/narrare/prompts/schemas.py` — Request/response models
**Router:** `apps/api/narrare/prompts/router.py`

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/prompts` | List all prompts with source indicators and metadata |
| `GET` | `/prompts/{prompt_id}` | Get prompt content + source + metadata |
| `PUT` | `/prompts/{prompt_id}` | Save/update a DB template override |
| `DELETE` | `/prompts/{prompt_id}` | Reset — removes DB override, falls back to cascade |
| `GET` | `/prompts/{prompt_id}/updates` | Check if bundled version has changed since override |
| `GET` | `/prompts/{prompt_id}/diff` | Side-by-side diff: override vs. current bundled |
| `GET` | `/prompts/variables` | List all available `{{variables}}` with descriptions |

### Cascade Integration

DB templates sit at the top of the resolution cascade:

```
DB template (this feature) → File override (PROMPT-001) → Bundled default
```

When `PromptManagementService.save()` is called:
1. Content is validated (valid Markdown, known variables)
2. Template stored in DB with user_id, prompt_id, content, and version metadata
3. Next prompt resolution picks up the DB template via cascade

When `PromptManagementService.reset()` is called:
1. DB template row is deleted
2. Resolution falls back to file override or bundled default

### Update Detection

When a Narrare update changes a bundled prompt:
1. The bundled prompt's version increments
2. DB templates track `override_of_version` (the bundled version they were based on)
3. `GET /prompts/{id}/updates` compares versions and returns update status
4. Frontend shows an update badge on affected prompts
5. User can view diff and decide whether to merge

### Schema Details

```python
class PromptOverride(BaseModel):
    prompt_id: str          # Unique identifier (category/lang/mode)
    content: str            # Override content (Markdown)
    override_of_version: str | None  # Bundled version this was based on
    source: Literal["bundled", "file", "db"]  # Current effective source
    updated_at: datetime
```

### Variable Registry

`packages/core/narrare_core/prompts/variable_metadata.py` provides a registry of all available
`{{variables}}` with human-readable descriptions. This powers the variables
sidebar in the editor UI, showing users what they can insert.

## Constraints & Edge Cases

- DB templates are per-user — different users can have different overrides for the same prompt
- Content validation rejects invalid Markdown or unknown variables (with warnings)
- Saving a DB template when a file override exists: DB template wins (higher priority)
- Deleting a DB template when a file override exists: falls back to file override, not bundled
- Update detection is informational — no forced migration
- Variable registry must be kept in sync with `packages/core/narrare_core/prompts/variable_engine.py`

## Related Features

- [INFRA-002](../infra/INFRA-002-prompt-system.md) — Parent prompt system
- [PROMPT-001](PROMPT-001-file-overrides.md) — File-based overrides (lower priority in cascade)
- [SET-002](../settings/SET-002-project-settings.md) — Settings UI

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-15` — API implemented with 7 endpoints, variable metadata registry, update detection, diff comparison, frontend PromptSettings/PromptEditor/PromptDiff components
