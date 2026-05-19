---
id: ASSIST-004
title: "Dialogue Coach"
status: planned
area: ai_assist
mvp: false

ui_tooltip: "Analyze and improve dialogue for subtext, flow, and character voice."
ui_help_short: |
  AI helps make dialogue more natural and character-authentic.
  Dialogue Coach analyzes your dialogue for common problems and provides improved rewrites.
ui_help_long: |
  Dialogue Coach analyzes your dialogue for common problems -- subtext violations, info-dumping, redundancy, and character voice inconsistencies -- and provides both analysis and improved rewrites.
  It helps you write dialogue that sounds natural, reveals character, and moves the story forward.
ui_available_in: ["editor", "cli", "mcp", "api"]

service: packages/core/ai_assist/dialogue_coach.py
contract: packages/core/ai_assist/contracts.py#DialogueCoach
router: apps/api/routers/ai_assist/dialogue.py
prompt: core/prompts/_bundled/ai_assist/en/dialogue_coach/system.md
requires: []
---

# [ASSIST-004] — Dialogue Coach

## What it does

Analyzes dialogue for common issues like on-the-nose dialogue, info-dumping, redundancy, and character voice inconsistencies. It provides specific feedback and generates improved rewrites.

## Why it exists

Writing natural, engaging, and character-authentic dialogue is difficult. Characters often sound the same or deliver clunky exposition. Dialogue Coach acts as an AI editor specialized in conversations, identifying these flaws and showing how to fix them.

## How it works (User perspective)

1. The writer selects a passage of dialogue.
2. The writer clicks Dialogue Coach and selects either "Analyze" or "Improve".
3. Narrare evaluates subtext, exposition, redundancy, and character fidelity.
4. The writer reviews the analysis report or compares the original dialogue with an improved AI rewrite.
5. The writer can accept changes, apply them individually, or dismiss them.

## How it works (Technical)

**Entry point:** `apps/api/routers/ai_assist/dialogue.py` → `POST /api/v1/writing/dialogue-coach/...`
**Service:** `DialogueCoach.analyze()` / `DialogueCoach.improve()`
**Contract:** `DialogueCoachProtocol`
**LLM Intent:** `LLMIntent.DIALOGUE_COACH`
**Prompt:** `core/prompts/_bundled/ai_assist/en/dialogue_coach/system.md`
**Streaming:** yes

Checks dialogue against established KB entries for the participating characters to ensure fidelity.

## Constraints & Edge Cases

- Best used on 2-4 speaking characters. Too many characters reduce fidelity accuracy.
- Requires characters to be assigned or inferred correctly to check voice fidelity.
- Monologues or internal thoughts are not supported well (use Voice Checker instead).

## Related Features

- [WRITE-010](../writing/WRITE-010-voice-checker.md) — Voice Checker (similar but focused purely on voice consistency)
- [KB-001](../kb/KB-001-entity-management.md) — Characters used for voice fidelity checks

## Status & History

- `2026-05-19` — Added to registry
