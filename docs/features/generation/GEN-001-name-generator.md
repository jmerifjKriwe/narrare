---
id: GEN-001
title: "Character/Place Name Generator"
status: planned
area: generation
mvp: false

ui_tooltip: "Generate context-aware names for characters, locations, and objects."
ui_help_short: |
  Generate context-aware names that fit your story's world. Choose from
  cultural templates, avoid duplicates from your Knowledge Base, and get
  pronunciation guides for fantasy names.
ui_help_long: |
  ## Name Generator

  Generate names that fit your story's world and avoid duplicates.

  **Supported Types**
  - **Characters**: First names, surnames, full names
  - **Locations**: Cities, regions, landmarks
  - **Objects**: Artifacts, weapons, vehicles
  - **Factions**: Organization names
  - **Creatures**: Animals, monsters, species

  **Cultural Context**
  - **Fantasy**: Elvish, Dwarvish, Orcish patterns
  - **Sci-Fi**: Technological, alien, corporate naming
  - **Historical**: Period-appropriate cultural names
  - **Modern**: Contemporary naming conventions
  - **Custom**: Define your own cultural patterns

  **Features**
  - **Deduplication**: Checks against existing KB entries
  - **Pronunciation guides**: For fantasy names
  - **Meaning suggestions**: Etymology for realism
  - **Batch generation**: Generate 10-50 at once
  - **Gender options**: Masculine, feminine, neutral
  - **Name lengths**: Short, medium, long options

  **How it works:**
  1. Open from KB panel or Editor
  2. Select type (character, location, etc.)
  3. Choose culture/style
  4. Set options (count, gender, length)
  5. Click "Generate Names"
  6. Results appear with:
     - Name text
     - Pronunciation (if fantasy)
     - Meaning/origin (if available)
     - Duplicate check status
  7. Click to use directly or save to list

  **Best practices:**
  - Define cultures before generating names
  - Generate in batches for options
  - Check pronunciation for fantasy names
  - Use consistent naming patterns per culture
  - Save favorites to KB for reference

  Available in KB panel, Editor, or via CLI:
  `narrare generation names --type character --culture elvish --count 10`
ui_available_in: [kb, editor, cli]

service: generation/name_service.py
contract: generation/contracts.py#NameGeneratorProtocol
router: generation/router.py
prompt: core/prompts/_bundled/generation/en/names
requires: [INFRA-001, KB-001]
---

# GEN-001 — Name Generator

## What it does

Intelligent name generation system with cultural context awareness. Generates names for characters, locations, objects, factions, and creatures while checking for duplicates against existing Knowledge Base entries.

## Why it exists

Naming is hard. Generic names feel flat, invented names lack consistency, and duplicate names create confusion. Writers need culturally appropriate, pronounceable names that fit their worldbuilding and don't conflict with existing entities.

## How it works (User perspective)

1. Open Name Generator from:
   - KB panel (when creating entities)
   - Editor sidebar (when writing)
   - CLI for batch generation
2. Select name type:
   - Character (first, surname, full)
   - Location (city, region, landmark)
   - Object (artifact, weapon, vehicle)
   - Faction, creature
3. Choose culture/style:
   - Fantasy: Elvish, Dwarvish, Orcish
   - Sci-Fi: Technological, alien, corporate
   - Historical: Medieval, Roman, Japanese
   - Modern: Contemporary
   - Custom: User-defined patterns
4. Set options:
   - Count (1-50)
   - Gender (masculine, feminine, neutral)
   - Length (short, medium, long)
5. Click "Generate Names"
6. Review results:
   - Name text
   - Pronunciation guide (fantasy names)
   - Meaning/origin (if available)
   - ✅/❌ duplicate check
7. Click to use or save to favorites

## How it works (Technical)

**Entry point:** `generation/router.py` → `POST /api/v1/generation/names`
**Service:** `NameGeneratorService.generate()` in `generation/name_service.py`
**Contract:** `NameGeneratorProtocol` in `generation/contracts.py`
**LLM Intent:** `LLMIntent.GENERATE`

**Name generation:**
```python
class GeneratedName:
    name: str
    pronunciation: str | None  # For fantasy names
    meaning: str | None  # Etymology if available
    type: NameType
    culture: str
    is_duplicate: bool  # Checked against KB
    confidence: float  # 0-1 quality score
```

**Generation pipeline:**
1. Template selection based on culture/type
2. Pattern-based generation (syllables, roots)
3. Cultural filtering (consistent with worldbuilding)
4. KB deduplication check
5. Pronunciation generation (for fantasy)
6. Quality scoring and ranking

**Cultural patterns:**
- Fantasy: Phonetic rules for constructed languages
- Historical: Actual name databases from periods
- Sci-Fi: Technological/linguistic patterns
- Custom: User-defined syllable rules

## Constraints & Edge Cases

- Cultural patterns are stereotypes (may not fit all needs)
- Pronunciation guides are approximations
- Fantasy names may be unprounceable
- Historical accuracy limited to database
- Sci-fi naming subjective and trend-dependent
- Duplicate check requires populated KB
- Custom cultures require manual pattern definition

## Related Features

- [KB-001](../kb/KB-001-entity-management.md) — Entity management
- [KB-006](../kb/KB-006-worldbuilding.md) — Culture definitions
- [WRITE-001](../writing/WRITE-001-editor.md) — In-editor generation
- [ASSIST-002](../ai_assist/ASSIST-002-title-suggest.md) — Title suggestions

## Status & History

- `project-init` — Added to registry as planned feature
