---
id: GEN-001
title: "Character/Place Name Generator"
status: in-progress
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

service: apps/api/narrare/generation/name_service.py
contract: apps/api/narrare/generation/contracts.py
router: apps/api/narrare/generation/router.py
prompt: core/prompts/_bundled/generation/
requires: [INFRA-001, INFRA-002, KB-001]
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

**API module (`apps/api/narrare/generation/`):**
- `contracts.py` — `NameGeneratorProtocol` definition
- `schemas.py` — Request/response Pydantic models
- `name_service.py` — `NameGeneratorService.generate()` — orchestrates name generation
- `router.py` — REST endpoint

**Core dependencies:**
- `LLMIntent.NAME_GENERATE` — Intent routed through LLM Gateway
- `PromptComposer` — Builds generation prompt with culture injection
- `PromptRegistry.resolve_culture()` — Resolves culture definition with EN fallback

**API Endpoint:**
- `POST /generation/names` — Generate names with type, culture, count, gender options

**Generation pipeline:**
1. Receive request with `name_type`, `culture`, `count`, `gender`, `length` options
2. `PromptComposer` builds prompt using `NAME_GENERATE` intent
3. Culture definition injected via `{{culture_guidelines}}` placeholder
4. LLM Gateway generates names using the composed prompt
5. Response parsed into `GeneratedName` objects

**Cultural patterns:**
Culture definitions are stored as prompt files in `core/prompts/_bundled/generation/`:
- `fantasy/{en,de,fr}/` — Phonetics, syllable patterns, naming traditions
- `modern/{en,de,fr}/` — Contemporary naming conventions
- `scifi/{en,de,fr}/` — Technological/linguistic patterns

Total: 3 name generation prompts (en/de/fr) + 9 culture definitions (3 cultures × 3 languages)

**Culture resolution:**
`PromptRegistry.resolve_culture()` follows the standard cascade with EN fallback:
1. Requested language for the culture
2. EN fallback if requested language unavailable

**Generated name structure:**
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

**Frontend (`packages/web/`):**
- `components/generation/NameGenerator.tsx` — Form with type, culture, count, gender selectors
- `components/generation/NameResults.tsx` — Results grid with pronunciation, meaning, duplicate badges
- `generationApi` — API client method for name generation

**i18n:**
- Generation-related UI strings extracted to all 3 locales (en, de, fr)

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
- `2026-05-15` — Core implementation: NAME_GENERATE intent, culture injection (fantasy/modern/scifi × 3 langs), API endpoint (POST /generation/names), frontend NameGenerator/NameResults components, i18n keys. KB dedup check is a placeholder.
