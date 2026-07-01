---
id: KB-003
title: "AI: Improve KB Entry"
status: stable
area: kb
mvp: false

ui_tooltip: "AI analyzes and suggests improvements for your KB entries."
ui_help_short: |
  Select a Knowledge Base entry and ask the AI to improve it. Narrare suggests
  additions, reorganizes content, identifies gaps, and enhances descriptions
  while preserving your core ideas.
ui_help_long: |
  ## AI: Improve KB Entry

  The AI can analyze your existing Knowledge Base entries and suggest targeted
  improvements.

  **What the AI checks for:**

  **Completeness**
  - Missing standard fields (voice for characters, appearance, etc.)
  - Gaps in backstory or motivation
  - Undefined relationships that could be added

  **Structure**
  - Content organization and flow
  - Consistency of formatting
  - Redundant or conflicting information

  **Depth**
  - Opportunities to add detail
  - Areas that feel vague or generic
  - Connections to other entities you might have missed

  **How it works:**
  1. Open any KB entry
  2. Click "Improve with AI"
  3. AI analyzes entry and shows suggestions:
     - Add these fields
     - Consider these connections
     - These areas could use more detail
  4. Choose which suggestions to apply
  5. AI updates entry with your selections

  **Types of improvements:**
  - **Expand**: Add detail to sparse sections
  - **Connect**: Link to related entities
  - **Reorganize**: Restructure for clarity
  - **Enhance**: Improve descriptions and voice

  You're always in control — review each suggestion before applying.
ui_available_in: [kb]

service: kb/improve_service.py
contract: kb/improve_contracts.py#KBImproveProtocol
router: kb/router_improve.py
prompt: core/prompts/_bundled/kb/en/improve/system.md
requires: [KB-001, KB-002, CORE-LLM, CORE-PROMPTS]
---

# KB-003 — AI: Improve KB Entry

## What it does

AI-powered analysis and improvement of existing KB entries. Identifies gaps,
suggests additions, reorganizes content, and enhances descriptions while
preserving user's core ideas and intent.

## Why it exists

KB entries created in haste are often sparse. Writers know their characters
but don't enjoy filling forms. The Improve feature helps flesh out entries
without requiring manual effort — AI suggests what's missing and what could
be better.

## How it works (User perspective)

1. Open any KB entry in the Knowledge Base
2. Click "Improve with AI" button
3. AI analyzes entry (3-10 seconds)
4. Suggestions appear categorized:
   - Missing fields to add
   - Connections to make
   - Areas to expand
   - Structure improvements
5. Check suggestions you want to apply
6. Click "Apply" — entry updated
7. Review and edit if needed

You can run Improve multiple times as your story evolves.

## How it works (Technical)

**Service:** `KBImproveService.analyze()` + `KBImproveService.apply()` in `apps/api/narrare/kb/improve_service.py`
**Contract:** `KBImproveProtocol` in `apps/api/narrare/kb/improve_contracts.py`
**Router:** `POST /novels/{novel_id}/kb/entities/{entry_id}/improve` + `/improve/apply` in `apps/api/narrare/kb/router_improve.py`
**Agent:** `KBImproveAgent` in `packages/core/narrare_core/agents/kb_improve_agent.py`
**Frontend:** `KBImprovePanel` + "Improve with AI" button in `KBEntryDetail`

**Analysis process:**
1. Fetch entry with all relationships
2. Analyze structure: completeness, organization, consistency
3. Compare against entity type template (required vs optional fields)
4. Search for unlinked related entities (by name, tags, content)
5. Generate suggestions with confidence scores
6. Return structured suggestions for user review

**Suggestion format:**
```python
class ImprovementSuggestion:
    type: "add_field" | "connect" | "expand" | "reorganize"
    target: str  # field name or entity id
    description: str
    proposed_content: str | None
    confidence: float  # 0-1
```

**User controls:**
- Select/deselect individual suggestions
- "Apply All" vs "Apply Selected"
- Preview changes before applying
- Undo available (entry versioned)

## Constraints & Edge Cases

- Requires LLM availability — no offline mode
- Analysis quality depends on entry size (very short entries = fewer suggestions)
- Won't suggest removal of content (only additions/changes)
- May suggest connections to entities you intentionally omitted
- Improvements are based on templates — may not fit all story types
- Large KBs (1000+ entries) may have slower relationship search

## Related Features

- [KB-001](KB-001-entity-management.md) — Base KB CRUD
- [KB-002](KB-002-kb-session.md) — Alternative: guided interview for improvement
- [CONS-001](../consistency/CONS-001-checker.md) — Consistency checking
- [INFRA-004](../infra/INFRA-004-embedding-store.md) — Semantic search for related entities

## Status & History

- `project-init` — Added to registry as planned feature
