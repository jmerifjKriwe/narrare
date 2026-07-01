---
id: SETUP-001
title: "Setup Wizard"
status: implemented
area: setup
mvp: true

ui_tooltip: "Configure your Narrare installation in five steps."
ui_help_short: |
  The Setup Wizard guides you through creating your first writing project.
  You choose a name, configure your novel's details, pick starter content,
  and connect your preferred AI provider — all before you write a single word.
ui_help_long: |
  ## Setup Wizard

  When you open Narrare for the first time, the Setup Wizard walks you through
  everything you need to get started.

  **Step 1 — Location**
  Choose a name for your project directory, your writing language (German,
  English, or French), and how often Narrare should automatically save your work.

  **Step 2 — Your Novel**
  Give your novel a title, set the author name, choose a genre and story
  structure, and write a logline — a single sentence that captures what
  your story is about.

  **Step 3 — Starter Content**
  Start with a blank project, import an existing directory, or load one of
  three demo projects to explore Narrare with real content already in place.

  **Step 4 — AI Provider**
  Connect Narrare to your preferred AI provider (Anthropic, OpenAI, Google,
  Groq, Ollama, OpenRouter, or Z.AI). Your API key is stored only on your
  machine — never on Narrare's servers.

  **Step 5 — Confirm**
  Review your configuration before Narrare creates your project.

  You can change all of these settings later in the Settings panel.
ui_available_in: [setup]

service: setup/service.py
contract: setup/contracts.py#SetupServiceProtocol
router: setup/router.py
prompt: ~
requires: [INFRA-001, SET-001, SET-002]
---

# SETUP-001 — Setup Wizard

## What it does

A 5-step guided flow that creates a new Narrare project: configures project
location and language, captures novel metadata, loads optional starter content,
validates and stores the AI provider configuration, and redirects to the
dashboard or editor on completion.

## Why it exists

First-run experience is the moment users decide whether to continue or abandon
a tool. Narrare has several configuration requirements (project path, language,
AI provider) that must be set before any feature works. The wizard makes this
setup feel intentional and guided rather than confrontational.

## How it works (User perspective)

1. User opens Narrare for the first time (or navigates to `/wizard`)
2. Progress indicator shows 5 steps, current step highlighted
3. **Step 1 — Location:**
   - Project name (text field, required, validated as valid directory name)
   - Language (dropdown: Deutsch / English / Français)
   - Autosave interval (slider: 0s = off, up to 3600s; default 30s)
   - "Next" enabled when project name is valid
4. **Step 2 — Novel:**
   - Title (required)
   - Author name
   - Genre (dropdown, extensible list)
   - Logline (textarea, optional but encouraged)
   - Story structure (dropdown: Drei-Akt / Fünf-Akt / Heldenreise — extensible)
   - Grundton / Tone (dropdown: Dramatisch / Humorvoll / Spannungsvoll — extensible)
5. **Step 3 — Starter Content:**
   - Four option cards: Blank / Demo Fantasy / Demo SciFi / Demo Deutsch / Import
   - Each card shows: title, description, chapter count, word count, character count
   - Selecting "Import" reveals a directory path field
   - Only one card selectable at a time
6. **Step 4 — AI Provider:**
   - Provider cards (Anthropic / OpenAI / Google / Groq / Ollama / OpenRouter / Z.AI)
   - On provider select: API key field appears (except Ollama: URL field)
   - For Z.AI: additional endpoint selector (General API or Coding API) to support
     different subscription plans
   - "Load models" button: fetches available models for this provider + key
   - Primary model dropdown: populated dynamically from API response
   - Validation: test call made before allowing "Next"
7. **Step 5 — Confirm:**
   - Summary of all choices
   - CLI command preview (for terminal users)
   - "Create Project" button
   - On success: redirect to `/dashboard` (blank) or `/novel/{id}/editor` (demo)
8. Back navigation allowed on all steps; state preserved

## How it works (Technical)

**Frontend state:** Zustand `setupStore` — persists across step navigation,
cleared on completion.

**Backend flow:**
- Each step has a validation endpoint: `POST /api/v1/setup/validate/step-{n}`
- Step 4 provider validation: `POST /api/v1/setup/validate/provider` — makes
  a real minimal API call to the provider to verify key + model access
- Step 4 model loading: `GET /api/v1/setup/providers/{provider}/models` —
  calls provider API, returns model list, cached in Redis for 24h
- Z.AI endpoint: Step 4 includes a `zai_endpoint` field ("general" or "coding")
  that selects between `https://api.z.ai/api/paas/v4` and
  `https://api.z.ai/api/coding/paas/v4`
- Completion: `POST /api/v1/setup/complete` — creates novel, chapters (if demo),
  writes settings, returns `{novel_id, redirect_to}`

**Demo content loading:**
Demo projects are bundled Markdown files in `scripts/demo_data/`.
`SetupService.load_demo_content()` reads the Markdown, parses frontmatter,
creates DB records. KB stubs are created as empty entities with names only.

**Provider extensibility:**
The provider list is driven by `packages/core/narrare_core/llm/_providers/registry.py`. Adding a
new provider to the registry automatically makes it available in the wizard.
No wizard code changes needed for new providers.

**Story structure / tone extensibility:**
Both lists are defined in packages/core/narrare_core/schemas/novels.py as
enums with a display name map. Adding a new value requires only a schema change
and an i18n string — no wizard logic changes.

**Routing:**
- `/wizard` → setup wizard (accessible for new novel creation from dashboard)
- Dashboard "New Novel" button navigates to `/wizard`
- After completion → `/dashboard` (blank starter) or `/novel/{id}/editor` (demo starter)

## Constraints & Edge Cases

- Project name is validated as a valid filesystem directory name (no slashes,
  no reserved names, no existing directory conflict)
- If AI provider validation fails: the actual provider error message is surfaced
  to the user (e.g., "Insufficient balance" from Z.AI), not a generic Narrare error
- If demo content loading fails partway through: full rollback — no partial novel
- Import option (Step 3): basic implementation at MVP — just accepts a path,
  validates it exists; full import analysis is SETUP-003 (not in MVP)
- Ollama: no API key field; base URL field with default `http://localhost:11434`;
  connectivity check instead of key validation
- All field labels, placeholder text, error messages, and option descriptions
  are i18n strings (de/en/fr)
- Wizard state is not persisted server-side — if user closes browser mid-wizard,
  they start over (acceptable for MVP)

## Related Features

- [SETUP-002](SETUP-002-demo-content.md) — the demo projects loaded in Step 3
- [SETUP-003](SETUP-003-import.md) — full import analysis (planned, not MVP)
- [SETUP-004](SETUP-004-provider-config.md) — provider config (also used in Settings)
- [SET-001](../settings/SET-001-user-settings.md) — settings created by wizard
- [SET-002](../settings/SET-002-project-settings.md) — project settings created by wizard

## Status & History

- `project-init` — Added to registry, specified for MVP
