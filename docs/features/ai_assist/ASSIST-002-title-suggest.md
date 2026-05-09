---
id: ASSIST-002
title: "Title Suggestions"
status: planned
area: ai_assist
mvp: false

ui_tooltip: "Generate compelling titles for your novel, chapters, or scenes."
ui_help_short: |
  Generate context-aware title suggestions for your novel, chapters, or scenes.
  AI analyzes themes, tone, and content to create memorable, marketable titles
  that fit your story.
ui_help_long: |
  ## Title Suggestions

  Generate compelling titles that capture your story's essence.

  **What gets analyzed:**
  - Themes and motifs
  - Genre conventions
  - Character names and roles
  - Setting and atmosphere
  - Key events and imagery

  **Title types:**
  - **Novel titles**: Main book titles
  - **Chapter titles**: Individual chapter names
  - **Scene titles**: Descriptive scene headers
  - **Series titles**: Multi-book series names

  **Suggestion categories:**
  - **Thematic**: Based on core themes
  - **Character**: Focused on protagonist or key character
  - **Imagery**: Evocative visual or symbolic titles
  - **Genre**: Following genre conventions
  - **Abstract**: Open to interpretation
  - **Direct**: Clear and descriptive

  **How it works:**
  1. Select scope (novel, chapter, scene)
  2. Choose title type and category
  3. Set count (1-10 suggestions)
  4. AI generates suggestions with:
     - Title text
     - Rationale (why this title works)
     - Marketability score
     - Genre fit assessment
  5. Save favorites to project notes

  **Best practices:**
  - Generate multiple batches for variety
  - Combine elements from different suggestions
  - Check for existing works with same title
  - Test readability and memorability
  - Consider series consistency for multi-book works

  Available in Editor panel or via CLI:
  `narrare titles suggest --novel <id> --type chapter --count 5`
ui_available_in: [editor, cli]

service: ai_assist/title_service.py
contract: ai_assist/contracts.py#TitleSuggestProtocol
router: ai_assist/router.py
prompt: core/prompts/_bundled/ai_assist/en/titles
requires: [INFRA-001, INFRA-002]
---

# ASSIST-002 — Title Suggestions

## What it does

Generate context-aware title suggestions for novels, chapters, and scenes. Analyzes themes, tone, genre conventions, and content to create memorable, marketable titles.

## Why it exists

Titles are hard. They need to be memorable, marketable, and meaningful — all while capturing the essence of your story. Writers often get stuck brainstorming titles or default to generic options. Title suggestions provide inspiration starting points based on actual story content.

## How it works (User perspective)

1. Select scope in Editor panel:
   - **Novel**: Main book title
   - **Chapter**: Specific chapter title
   - **Scene**: Scene header title
2. Choose suggestion category:
   - Thematic, Character, Imagery, Genre, Abstract, Direct
3. Set number of suggestions (1-10)
4. Click "Generate Titles"
5. AI generates suggestions (5-15 seconds)
6. Each suggestion includes:
   - Title text
   - Rationale (why it works)
   - Marketability score (0-1)
   - Genre fit assessment
7. Click heart icon to save favorites
8. Copy to use directly

## How it works (Technical)

**Entry point:** `ai_assist/router.py` → `POST /api/v1/ai_assist/titles/suggest`
**Service:** `TitleSuggestService.generate()` in `ai_assist/title_service.py`
**Contract:** `TitleSuggestProtocol` in `ai_assist/contracts.py`
**LLM Intent:** `LLMIntent.ASSIST`

**Suggestion generation:**
```python
class TitleSuggestion:
    title: str
    rationale: str  # Why this title works
    marketability: float  # 0-1 score
    genre_fit: str  # Genre assessment
    category: TitleCategory  # thematic, character, etc.
```

**Analysis pipeline:**
1. Extract key themes from content (embedding clustering)
2. Identify genre from content analysis
3. Extract character names and roles
4. Identify key imagery and symbols
5. Generate titles based on category template
6. Score for marketability (memorability, length, uniqueness)

**Marketability scoring:**
- Length: 1-5 words optimal
- Memorability: Unique but pronounceable
- Uniqueness: Check against common titles
- Genre fit: Match genre conventions

## Constraints & Edge Cases

- Requires existing content for analysis (novel/chapter must exist)
- Cannot guarantee title uniqueness (manual search required)
- Marketability scores are estimates
- Genre detection may be wrong for cross-genre works
- Some categories may not fit all story types
- LLM availability required
- Titles are suggestions, not final recommendations

## Related Features

- [WRITE-001](../writing/WRITE-001-editor.md) — Chapter content
- [ANAL-011](../analysis/ANAL-011-plot-analysis.md) — Theme extraction
- [KB-001](../kb/KB-001-entity-management.md) — Character names
- [GEN-001](../generation/GEN-001-name-generator.md) — Name generation

## Status & History

- `project-init` — Added to registry as planned feature
