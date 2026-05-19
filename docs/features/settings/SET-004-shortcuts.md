---
id: SET-004
title: "Keyboard Shortcuts"
status: planned
area: settings
mvp: false

ui_tooltip: "View and customize keyboard shortcuts."
ui_help_short: |
  Work faster with keyboard shortcuts for every action in Narrare.
  Master shortcuts for the editor, dashboard, and navigation.
ui_help_long: |
  This guide covers all keyboard shortcuts for the editor, dashboard, and navigation. Master these to dramatically speed up your writing workflow. You can view all shortcuts, resolve conflicts, and customize them in Settings.
ui_available_in: ["editor", "dashboard"]

service: packages/web/src/lib/shortcuts.ts
contract: ""
router: ""
prompt: ""
requires: []
---

# [SET-004] — Keyboard Shortcuts

## What it does

Provides a comprehensive, customizable system of keyboard shortcuts covering text editing, AI writing tool triggers, chapter navigation, and global UI views (Dashboard, Editor, KB, Settings).

## Why it exists

Writing is a flow state. Forcing a writer to move their hands from the keyboard to the mouse to trigger an AI suggestion, navigate to another chapter, or open the Knowledge Base breaks that flow. Keyboard shortcuts keep writers focused and productive.

## How it works (User perspective)

1. The writer uses standard commands (e.g., `Cmd/Ctrl + S` to save) or specialized ones (e.g., `Cmd/Ctrl + Shift + R` to rewrite a selection).
2. The Command Palette (`Cmd/Ctrl + K`) allows fuzzy-searching of all actions.
3. The writer can navigate to Settings → Keyboard to view all available shortcuts, resolve conflicts, and create custom keybindings for specific actions.

## How it works (Technical)

**Entry point:** Frontend global event listeners and `CommandPalette` component.
**Service:** UI-driven shortcut management stored in local settings.
**Streaming:** no

Keybindings are resolved locally in the frontend client. Certain OS or Browser constraints dictate default bindings on macOS vs Windows/Linux.

## Constraints & Edge Cases

- Browsers can intercept certain shortcuts in the WebUI.
- Shortcut conflicts (System vs App vs Browser) are flagged in the UI for resolution.

## Related Features

- [SET-001](../settings/SET-001-user-settings.md) — Main user settings page where shortcuts are configured.
- [WRITE-001](../writing/WRITE-001-editor.md) — The editor where most shortcuts are applied.

## Status & History

- `2026-05-19` — Added to registry
