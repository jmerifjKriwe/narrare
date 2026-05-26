---
id: ANAL-001
title: "Beta Reader Simulation"
status: stable
area: analysis
mvp: false

ui_tooltip: "AI simulates a beta reader's feedback on your chapters."
ui_help_short: |
  Get comprehensive feedback on your chapters as if from a beta reader. The AI
  analyzes plot, characters, pacing, and prose — highlighting what works,
  what doesn't, and what might confuse readers.
ui_help_long: |
  ## Beta Reader Simulation

  Get beta reader feedback without waiting for humans. The AI reads your
  chapter and provides comprehensive feedback from a reader's perspective.

  **What gets analyzed:**

  **Plot and Structure** 📖
  - Clear goals and conflicts
  - Pacing and momentum
  - Questions and curiosity gaps
  - Satisfying progressions or cliffhangers

  **Characters** 👥
  - Believability and consistency
  - Motivation clarity
  - Emotional impact
  - Dialogue naturalness

  **Prose and Style** ✍️
  - Clarity and flow
  - Show vs tell balance
  - Description effectiveness
  - Voice consistency

  **Reader Experience** 📚
  - Engagement level
  - Confusion points
  - Emotional resonance
  - Page-turner quality

  **How it works:**
  1. Select one or multiple chapters
  2. Click "Beta Reader" in Analysis panel
  3. AI reads and analyzes (15-60 seconds per chapter)
  4. Feedback appears organized by category:
     - Strengths (what works)
     - Issues (what doesn't work)
     - Questions (what readers will ask)
     - Suggestions (how to improve)
  5. Click any item for detailed explanation
  6. Export feedback as report for reference

  **Feedback types:**
  - **Critical**: Issues that will frustrate readers
  - **Moderate**: Problems some readers will notice
  - **Minor**: Small improvements worth considering

  **Best practices:**
  - Run on complete chapters, not fragments
  - Use after first draft, not during writing
  - Compare feedback across multiple chapters
  - Combine with human beta readers for best results

  AI feedback is comprehensive but not infallible. Use it as one perspective
  among many, not as final authority.
ui_available_in: [editor, analysis]

service: analysis/beta_reader_service.py
contract: analysis/contracts.py#BetaReaderProtocol
router: analysis/router.py
prompt: core/prompts/_bundled/analysis/en/beta_reader
requires: [INFRA-001, KB-001]
---

# ANAL-001 — Beta Reader Simulation

## What it does

AI-powered comprehensive chapter analysis from a reader's perspective. Evaluates
plot, characters, pacing, prose, and reader experience. Provides categorized
feedback with severity ratings and actionable suggestions.

## Why it exists

Beta readers provide invaluable feedback but are scarce and slow. Writers need
reader perspectives during revision, not just before publication. AI simulation
provides immediate, comprehensive feedback to guide improvements.

## How it works (User perspective)

1. Select chapter(s) to analyze
2. Click "Beta Reader" in Analysis panel
3. Choose analysis focus (plot, characters, prose, or all)
4. AI analyzes chapter (15-60 seconds)
5. Feedback appears in categories:
   - Strengths: What works well
   - Issues: Problems readers will encounter
   - Questions: Unanswered curiosities
   - Suggestions: How to improve
6. Click any item for detailed explanation
7. Export feedback as PDF or Markdown

Feedback is organized by severity (Critical/Moderate/Minor) to prioritize
revisions.

## How it works (Technical)

**Entry point:** `analysis/router.py` → `POST /api/v1/analysis/beta-reader`
**Service:** `BetaReaderService.analyze()` in `analysis/beta_reader_service.py`
**Contract:** `BetaReaderProtocol` in `analysis/contracts.py`
**LLM Intent:** `LLMIntent.BETA_READ`

**Analysis categories:**
```python
class BetaReaderFeedback:
    strengths: list[str]
    weaknesses: list[str]
    questions: list[str]  # Reader will wonder...
    suggestions: list[str]
    severity: "critical" | "moderate" | "minor"
    category: "plot" | "character" | "prose" | "pacing"
    location: str | None  # Chapter/section reference
```

**Analysis process:**
1. **Read chapter**: Extract full text and structure
2. **Analyze by category**:
   - Plot: Goals, conflicts, pacing, resolution
   - Characters: Believability, motivation, consistency
   - Prose: Clarity, flow, show/tell, voice
   - Experience: Engagement, confusion, emotion
3. **Assign severity**: Based on reader impact
4. **Generate suggestions**: Actionable improvements
5. **Format output**: Organized, readable feedback

**Context used:**
- Chapter text and frontmatter
- Previous chapters (for context)
- KB entries (characters, locations)
- Genre expectations (if specified)

## Constraints & Edge Cases

- Minimum 1000 words for meaningful feedback
- Maximum 10,000 words per analysis (token limits)
- Feedback quality depends on chapter completeness
- May miss subtle literary devices or symbolism
- Genre assumptions may not match author's intent
- Cannot replace human emotional response
- LLM availability required

## Related Features

- [ANAL-010](ANAL-010-literary-suite.md) — Literary analysis
- [ANAL-011](ANAL-011-plot-analysis.md) — Plot-specific analysis
- [WRITE-006](../writing/WRITE-006-co-author.md) — Implementing suggestions

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-26` — Fully implemented (commit 0b2fb6a): BetaReaderAgent (two-phase), analysis/ module, BetaReaderPanel, ScoreRadar (Recharts), 57 tests, i18n 3 locales
