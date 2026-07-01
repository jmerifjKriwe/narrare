---
id: INFRA-010
title: "Prompting Locally"
status: stable
area: infra
mvp: false

ui_tooltip: "Override and customize system prompts for specific projects."
ui_help_short: |
  Customize how the AI assists you by overriding system prompts in your own project.
  Allows fine-grained control over AI behavior without modifying the core app.
ui_help_long: |
  Narrare uses a sophisticated prompt cascading system that allows you to tailor the AI's behavior, style, and analysis depth for each individual novel or character without changing the core application. Overrides can be defined at the project or global user level.
ui_available_in: ["editor", "cli", "api"]

service: packages/core/narrare_core/prompts/management.py
contract: packages/core/prompts/contracts.py#PromptManager
router: apps/api/narrare/prompts/router.py
prompt: ""
requires: []
---

# [INFRA-010] — Prompting Locally

## What it does

Allows users to override Narrare's built-in system prompts at the project level. By placing customized Markdown prompt files in `.narrare/prompts/`, writers can radically alter how the AI generates text, analyzes dialogue, or formats output.

## Why it exists

Different novels require different AI tones, guidelines, and constraints. A hardcoded set of prompts limits power users who want deep control over their writing partner. Prompting locally empowers users to customize AI behavior without needing to fork the software.

## How it works (User perspective)

1. The writer creates a `.narrare/prompts/` directory in their project root.
2. The writer creates a file matching the bundled prompt path (e.g., analysis/beta_reader/system.md).
3. The writer writes their custom system prompt instructions.
4. Narrare automatically detects the override and uses it for all future beta reader requests in that project.

## How it works (Technical)

**Entry point:** `packages/core/narrare_core/prompts/management.py`
**Service:** `PromptManager.get_prompt()`
**Contract:** `PromptManagerProtocol`
**Streaming:** no

The PromptManager uses a cascade resolution order across all 5 levels:
1. DB Template (user database prompt templates — highest priority)
2. Project Level (`.narrare/prompts/` — the workspace root's `.narrare/` directory)
3. Global Level (user config — `user_config_dir/prompts/`)
4. Bundled Level (defaults — `core/prompts/_bundled/`)
5. Bundled EN Fallback (English defaults when no localized prompt exists)

The cascade resolution is now fully active across all 5 levels (DB template → project file → user-global → bundled → bundled EN fallback).

## Constraints & Edge Cases

- Malformed or extremely poor custom prompts can break AI feature outputs.
- Prompt overrides are isolated per project and don't affect other projects.

## Related Features

- [PROMPT-001](../prompts/PROMPT-001-file-overrides.md) — Overrides definition
- [WRITE-013](../writing/WRITE-013-workflows.md) — Writing Workflows heavily utilizing these prompts

## Status & History

- `2026-05-19` — Added to registry
- `2026-05-26` — Cascade activated via workspace root DI wiring. PromptRegistry and MetaPromptLoader now receive project_root=BASE_DIR. ManagementService fallback aligned with cascade path (bugfix: ~/.narrare/ → user_config_dir/prompts/). Status: planned → stable.
