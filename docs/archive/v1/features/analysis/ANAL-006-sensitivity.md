---
id: ANAL-006
title: "Sensitivity Review"
status: planned
area: analysis
mvp: false

ui_tooltip: "Identify stereotypes, harmful tropes, and representation issues."
ui_help_short: |
  Write more inclusive fiction. Sensitivity Review flags stereotypes,
  harmful tropes, cultural appropriation, and representation issues — helping
  you catch problems before readers do.
ui_help_long: |
  ## Sensitivity Review

  AI-powered analysis for inclusive, respectful fiction. Identify problematic
  representations before they reach readers.

  **Issue categories:**

  **Stereotypes** 👥
  - Reductive characterizations
  - One-dimensional portrayals
  - Tokenistic representation
  - Reinforcing clichés

  **Harmful Tropes** 🚩
  - Marginalizing narrative patterns
  - Problematic plot devices
  - Damaging character arcs
  - Historical misrepresentations

  **Cultural Appropriation** 🌍
  - Misuse of cultural elements
  - Sacred traditions treated casually
  - Cultural practices commodified
  - Deep cultural context ignored

  **Representation Issues** 📊
  - Tokenism (single representative character)
  - Exclusion of marginalized groups
  - Sidelining of diverse voices
  - Queer-baiting or fridging

  **Language Concerns** 💬
  - Slurs and derogatory terms
  - Insensitive phrasing
  - Offensive terminology
  - Microaggressions in dialogue

  **Historical Inaccuracies** 📜
  - Misrepresentation of cultures/events
  - Anachronistic attitudes
  - Erasure of marginalized perspectives
  - Colonialist narratives unchallenged

  **Severity levels:**
  - **Critical**: Slurs, hate speech, dehumanizing language
  - **High**: Harmful stereotypes, toxic tropes
  - **Medium**: Problematic patterns, missed opportunities
  - **Low**: Minor insensitivities, phrasing improvements

  **How it works:**
  1. Select chapter or entire novel
  2. Click "Sensitivity Review" in Analysis panel
  3. AI analyzes content (15-60 seconds)
  4. Issues flagged by severity and category
  5. For each issue:
     - Quote from text
     - Explanation of why it's problematic
     - Context considerations (if applicable)
     - Suggested revision
  6. Review and address issues

  **Important notes:**
  - AI is not a substitute for human sensitivity readers
  - Context matters — some issues may be intentional/necessary
  - Historical accuracy vs. modern sensibilities — judgment call
  - Use as one tool among many

  **Best practices:**
  - Use during drafting, not just before publication
  - Focus on high-impact changes first
  - Combine with human sensitivity readers
  - Consider context before "fixing" issues

  Writing inclusive fiction isn't about censorship — it's about writing
  stories that respect all readers and avoid harm.
ui_available_in: [analysis]

service: analysis/sensitivity_service.py
contract: analysis/contracts.py#SensitivityProtocol
router: analysis/router.py
prompt: core/prompts/_bundled/analysis/en/sensitivity
requires: [INFRA-001]
---

# ANAL-006 — Sensitivity Review

## What it does

AI-powered identification of stereotypes, harmful tropes, cultural appropriation,
representation issues, and problematic language. Provides severity ratings and
revision suggestions. Not a replacement for human sensitivity readers.

## Why it exists

Unintentionally harmful representations damage readers and reputations. Writers
may lack lived experience of communities they're writing about. AI analysis
catches issues early, while human sensitivity readers provide deeper context.

## How it works (User perspective)

1. Select chapters to review
2. Click "Sensitivity Review" in Analysis panel
3. Analysis runs (15-60 seconds depending on length)
4. Issues appear grouped by severity:
   - 🔴 Critical: Hate speech, slurs
   - 🟠 High: Harmful stereotypes, toxic tropes
   - 🟡 Medium: Problematic patterns
   - 🔵 Low: Minor improvements
5. For each issue:
   - See quoted text with location
   - Read explanation of why it's problematic
   - Consider context notes (if applicable)
   - Review suggested revision
6. Address issues or document intentional choices

AI is a first pass, not final authority. Combine with human sensitivity readers
for thorough review.

## How it works (Technical)

**Entry point:** `analysis/router.py` → `POST /api/v1/analysis/sensitivity`
**Service:** `SensitivityService.review()` in `analysis/sensitivity_service.py`
**Contract:** `SensitivityProtocol` in `analysis/contracts.py`
**LLM Intent:** `LLMIntent.ANALYSE`

**Issue detection:**
```python
class SensitivityIssue:
    category: IssueCategory  # stereotype, trope, appropriation, etc.
    severity: "critical" | "high" | "medium" | "low"
    quote: str  # Problematic text
    location: str  # Chapter/line reference
    explanation: str  # Why this is problematic
    context_notes: str | None  # If historical accuracy, etc.
    suggestion: str  # How to fix
```

**Analysis categories:**
- **Stereotypes**: Gender, racial, cultural, religious, disability
- **Tropes**: Magical negro, tomboy, fridging, queer-baiting, etc.
- **Appropriation**: Cultural elements, sacred traditions
- **Representation**: Tokenism, exclusion, sidelining
- **Language**: Slurs, microaggressions, offensive terms
- **Historical**: Misrepresentation, erasure, colonialism

**Detection approach:**
- Pattern matching against known harmful tropes
- Character role analysis (tokenism, marginalization)
- Cultural element usage (appropriation detection)
- Language scanning (slurs, problematic terms)
- Context consideration (historical setting, character POV)

## Constraints & Edge Cases

- May flag intentional character flaws as stereotypes
- Historical accuracy vs. modern sensitivity tension
- Cannot detect all cultural nuances
- May miss context-dependent issues
- False positives possible — human review essential
- LLM training data biases affect detection
- Not a substitute for lived experience

## Related Features

- [ANAL-001](ANAL-001-beta-reader.md) — Reader perspective
- [KB-001](../kb/KB-001-entity-management.md) — Character development
- [WRITE-006](../writing/WRITE-006-co-author.md) — Implementing fixes

## Status & History

- `project-init` — Added to registry as planned feature
