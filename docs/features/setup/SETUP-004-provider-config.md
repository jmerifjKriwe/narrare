---
id: SETUP-004
title: "AI Provider Configuration"
status: stable
area: setup
mvp: true

ui_tooltip: "Connect Narrare to your preferred AI provider."
ui_help_short: |
  Configure the AI provider and model settings Narrare uses for writing help.
ui_help_long: |
  Choose which local or remote AI provider Narrare should use, then enter the
  required credentials and model details. The setup flow validates the basics so
  you can start writing with confidence.

  Provider settings stay local to your Narrare installation and feed the model
  routing cascade used by AI-assisted features.
ui_available_in: []

service: setup/provider_service.py
contract: ~
router: ~
prompt: ~
requires: []
---

# SETUP-004 — AI Provider Configuration

> **Status:** ✅ Stable — implemented as part of the Setup Wizard and settings flow.

## What it does

AI Provider Configuration lets writers connect Narrare to the model provider
they want to use. It captures the provider choice, credentials, and model
defaults used by later AI-assisted writing, analysis, and KB features.

## Why it exists

Narrare is local-first and provider-flexible. Writers need a guided way to tell
the app which AI backend to use without editing environment files or changing
code.

## How it works (User perspective)

1. Open the Setup Wizard or settings screen.
2. Select the AI provider and enter the required credentials/model identifiers.
3. Save the configuration.
4. Narrare uses the saved settings when AI features resolve their model via the
   normal model-routing cascade.

## How it works (Technical)

Provider configuration is part of the setup/settings layer and feeds the shared
model-resolution path. AI calls still go through `core/llm/gateway.py`; feature
services do not import provider SDKs directly. This feature has no prompt of its
own.

## Constraints & Edge Cases

- Invalid or missing credentials prevent AI features from completing, but the
  writing workspace remains usable.
- Provider-specific model names are validated as configuration, not hardcoded in
  routers or services.
- Changing providers affects future AI calls; it does not rewrite existing text
  or stored KB entries.

## Related Features

- [INFRA-001](../infra/INFRA-001-llm-gateway.md) — LLM Gateway
- [SET-003](../settings/SET-003-model-config.md) — Per-task model configuration
- SETUP-004 — this setup feature

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-06-03` — Documentation completed and status aligned with the implemented setup/settings flow.
