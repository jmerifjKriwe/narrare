---
id: KB-005
title: "Proactive KB Suggestions"
status: planned
area: kb
mvp: false

ui_tooltip: "AI suggests relevant KB entries as you write each chapter."
ui_help_short: |
  When you open a chapter, Narrare automatically suggests Knowledge Base
  entries that are relevant to the scene — characters who appear, locations
  mentioned, and related context. One click adds them to your working context.
ui_help_long: |
  ## Proactive KB Suggestions

  Narrare intelligently suggests which Knowledge Base entries might be relevant
  to your current chapter, so you don't have to search manually.

  **How it works:**

  1. You open a chapter for editing
  2. AI analyzes chapter content and frontmatter
  3. Suggestions appear in the context panel:
     - Characters mentioned or likely to appear
     - Locations referenced in the scene
     - Related entities from your Knowledge Base
  4. Click any suggestion to add it to your active context
  5. Dismiss irrelevant suggestions — AI learns your preferences

  **What influences suggestions:**

  **Explicit references**
  - Character names mentioned in text
  - Locations named in the scene
  - Entities in chapter frontmatter (POV character, location)

  **Implicit relevance**
  - Semantic similarity (chapter about combat → suggest fighters)
  - Recent usage (entities from recent chapters)
  - Pattern recognition (you always use these entities together)

  **Learning from feedback:**
  - Entries you accept are suggested more often
  - Entries you dismiss appear less frequently
  - Preferences tracked per project

  **Benefits:**
  - No manual searching before writing
  - Discover connections you might have missed
  - Keep context relevant without clutter
  - Faster workflow — suggestions are one-click to add

  Suggestions update automatically as you write. Open the context panel to see
  what's been suggested and what's currently active.
ui_available_in: [editor]

service: kb/suggest_service.py
contract: kb/contracts.py#KBSuggestProtocol
router: kb/router.py
prompt: ~
requires: [KB-001, INFRA-003, INFRA-004]
---

# KB-005 — Proactive KB Suggestions

## What it does

Automatic suggestion of relevant KB entries when opening chapters. Uses
semantic search, pattern recognition, and explicit reference extraction to
predict which entities the user needs for the current scene.

## Why it exists

Manual context selection is tedious. Writers forget to load relevant characters
or locations before writing. By the time they realize they need context, they've
lost their flow. Proactive suggestions surface relevant context before the
first keystroke.

## How it works (User perspective)

1. Open any chapter for editing
2. Context panel shows "Suggestions" section with 5-10 entries
3. Suggestions are ranked by relevance:
   - 🟢 High confidence: explicitly referenced
   - 🟡 Medium confidence: semantically related
   - 🔵 Low confidence: pattern-based
4. Click + to add suggestion to active context
5. Click × to dismiss (teaches AI your preferences)

As you write, suggestions update. New entities you mention appear as suggestions.
Dismissed entries won't be suggested again for this chapter.

## How it works (Technical)

**Entry point:** `kb/router.py` → `GET /api/v1/kb/suggestions/{chapter_id}`
**Service:** `KBSuggestService.get_suggestions()` in `kb/suggest_service.py`
**Contract:** `KBSuggestProtocol` in `kb/contracts.py`
**Triggered:** Chapter open, content change (debounced 5s)

**Three-stage pipeline:**

**1. Content Analysis**
- Extract entity names from chapter text and frontmatter
- Detect themes and topics (battle, romance, mystery)
- Parse frontmatter: POV character, location, timeline

**2. KB Search**
- Embedding search: chapter content → similar KB entries
- Name matching: extracted names → KB entity names
- Graph traversal: related entities to already-matched entries

**3. Learning & Prioritization**
Score = 50% relevance + 30% usage frequency + 20% recency
- Explicit references boost score
- Previously accepted entries get slight boost
- Dismissed entries penalized for this chapter

**Suggestion format:**
```python
class KBEntrySuggestion:
    entry_id: UUID
    entry_type: EntityType
    name: str
    relevance_score: float  # 0-1
    reason: str  # "mentioned in text", "similar to X", "recently used"
```

## Constraints & Edge Cases

- Maximum 20 suggestions per chapter (to avoid overwhelming)
- Requires embeddings to be generated (INFRA-004)
- Very short chapters may have few or no suggestions
- Name matching is fuzzy — may suggest similarly-named entities
- Learning requires multiple sessions to become accurate
- Empty KB results in no suggestions (expected)

## Related Features

- [INFRA-003](../infra/INFRA-003-context-assembly.md) — Consumes suggestions for context
- [INFRA-004](../infra/INFRA-004-embedding-store.md) — Provides semantic search
- [KB-001](KB-001-entity-management.md) — Source of suggested entries
- [LEARN-001](../learning/LEARN-001-feedback-loop.md) — Learning from feedback

## Status & History

- `project-init` — Added to registry as planned feature
