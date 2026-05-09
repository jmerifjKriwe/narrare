---
id: WRITE-006
title: "Co-Author Mode"
status: planned
area: writing
mvp: false

ui_tooltip: "AI suggests revisions with diff view and selective acceptance."
ui_help_short: |
  Select any passage and open Co-Author Mode. The AI suggests improvements
  with a diff view showing exactly what changed. Accept changes individually
  or all at once. Like track changes, but powered by AI.
ui_help_long: |
  ## Co-Author Mode

  Co-Author Mode gives you an AI writing partner that suggests specific
  improvements to your text. You see exactly what changed and decide what to
  accept.

  **How it works:**

  1. Select a passage in your chapter (sentence to several pages)
  2. Click "Co-Author" in toolbar
  3. AI analyzes and suggests improvements:
     - Stronger verbs
     - Better dialogue
     - More showing, less telling
     - Improved flow and pacing
     - Enhanced voice consistency
  4. Review changes in diff view:
     - Red text = removed
     - Green text = added
     - Click each change to accept or reject
  5. Click "Accept All" or "Accept Selected"
  6. Your text updates with chosen changes

  **Improvement types:**

  **Word choice** 📝
  - Stronger verbs (replace weak ones)
  - More precise nouns
  - Remove redundancies

  **Sentence level** 📄
  - Vary sentence structure
  - Fix awkward phrasing
  - Improve rhythm

  **Dialogue** 💬
  - More natural speech
  - Better character voice
  - Remove on-the-nose lines

  **Description** 🖼️
  - Add sensory details
  - Show instead of tell
  - Create vivid imagery

  **Why use Co-Author:**
  - See exactly what AI suggests (no blind rewrites)
  - Learn from AI suggestions
  - Maintain full control
  - Combine AI strengths with your vision

  **Best practices:**
  - Use on second drafts, not first
  - Review each change thoughtfully
  - Don't accept blindly — AI makes mistakes
  - Combine with Rejection Learning to teach AI your preferences

  Co-Author learns from your choices over time. Acceptances and rejections
  shape future suggestions to match your style.
ui_available_in: [editor]

service: writing/co_author_service.py
contract: writing/contracts.py#CoAuthorProtocol
router: writing/router.py
prompt: core/prompts/_bundled/writing/en/co_author
requires: [INFRA-001, INFRA-002, LEARN-001]
---

# WRITE-006 — Co-Author Mode

## What it does

AI-powered revision suggestions with granular acceptance controls. Generates
diff-style changes showing additions and deletions. User accepts/rejects
individual changes or all at once. Feeds Rejection Learning for personalization.

## Why it exists

Traditional AI rewriting is all-or-nothing. Writers want control — see what
changed, decide what to keep. Co-Author provides track-changes-style revision
with AI suggestions, maintaining author sovereignty.

## How it works (User perspective)

1. Select any passage (sentence to several pages)
2. Click "Co-Author" in toolbar
3. Panel opens with AI suggestions in diff view:
   - Red strikethrough = AI removed this
   - Green underline = AI added this
4. Review each change:
   - Click checkmark to accept
   - Click X to reject
   - Hover to see AI's reasoning
5. Click "Accept All" or "Accept Selected"
6. Your text updates with chosen changes

Changes are applied immediately. Undo available to revert.

## How it works (Technical)

**Entry point:** `writing/router.py` → `POST /api/v1/writing/co-author`
**Service:** `CoAuthorService.suggest()` in `writing/co_author_service.py`
**Contract:** `CoAuthorProtocol` in `writing/contracts.py`
**LLM Intent:** `LLMIntent.CO_AUTHOR`

**Request:**
```python
class CoAuthorRequest:
    selection_text: str
    chapter_id: UUID
    focus: list[CoAuthorFocus]  # word_choice, dialogue, description, etc.
    character_id: UUID | None  # for voice consistency
```

**Response:**
```python
class CoAuthorSuggestion:
    original: str
    revised: str
    diff: list[DiffChange]  # {removed, added, position}
    reasoning: str  # why AI made this change
    confidence: float  # 0-1
```

**Diff generation:**
- Uses difflib.SequenceMatcher for change detection
- Each change labeled with type and reasoning
- Changes grouped by sentence for easier review

**Acceptance processing:**
- Accepted changes applied to text
- Rejected changes discarded
- Acceptance/rejection fed to Rejection Learning (LEARN-001)
- Future suggestions influenced by past choices

**Version tracking:**
- Original text preserved until "Accept" clicked
- Undo reverts to pre-Co-Author state
- No intermediate saves (one revision operation)

## Constraints & Edge Cases

- Selection minimum 50 words, maximum 5000 words
- Diff accuracy decreases for very radical rewrites
- AI may suggest changes you disagree with (review important)
- Character voice requires KB entry (ANAL-008)
- Learning requires 20+ interactions for meaningful personalization
- Very long selections may take 30+ seconds to process

## Related Features

- [WRITE-004](WRITE-004-rewrite.md) — One-shot rewriting
- [LEARN-001](../learning/LEARN-001-feedback-loop.md) — Learning from feedback
- [ANAL-008](../analysis/ANAL-008-voice-character.md) — Voice analysis
- [WRITE-005](WRITE-005-interactive-session.md) — Alternative collaborative interface

## Status & History

- `project-init` — Added to registry as planned feature
