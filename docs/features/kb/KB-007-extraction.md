---
id: KB-007
title: "Entity Extraction from Chapters"
status: implemented
area: kb
mvp: false

ui_tooltip: "Extract facts and entities from your chapters into the Knowledge Base."
ui_help_short: |
  Automatically extract characters, locations, facts, and relationships from
  your written chapters. Narrare identifies what's been established and
  offers to create or update KB entries — saving manual data entry.
ui_help_long: |
  ## Entity Extraction from Chapters

  As you write, you establish facts about your world — character details,
  location descriptions, relationships, events. Entity Extraction reads your
  chapters and automatically pulls this information into your Knowledge Base.

  **What gets extracted:**

  **Explicit facts**
  - Character names and descriptions
  - Location names and details
  - Stated relationships ("A is B's brother")
  - Timeline markers and dates

  **Implicit facts**
  - Character traits shown through action
  - Location features described through scenes
  - Relationships implied through dialogue
  - Temporal information ("three days later")

  **How it works:**
  1. Finish writing a chapter
  2. Click "Extract to KB" or run on auto-schedule
  3. AI reads chapter and identifies:
     - New entities not in KB
     - New facts about existing entities
     - Relationships between entities
  4. Review extraction results:
     - Approve new KB entries
     - Merge facts into existing entries
     - Reject incorrect extractions
  5. KB updated with approved changes

  **Confidence scoring:**
  - 🟢 High confidence: Explicit statements ("Elena is 24 years old")
  - 🟡 Medium confidence: Implied facts (inferred from context)
  - 🔵 Low confidence: Speculative (requires verification)

  **Benefits:**
  - KB builds itself as you write
  - Catch inconsistencies early (extraction conflicts with KB)
  - No manual entry for established facts
  - Discover what you've implicitly defined

  Extraction works best after chapters are complete and edited.
ui_available_in: [editor, kb]

service: kb/extraction_service.py
contract: kb/contracts.py#ExtractionProtocol
router: kb/router.py
prompt: core/prompts/_bundled/kb/en/extract
requires: [KB-001, INFRA-001]
---

# KB-007 — Entity Extraction from Chapters

## What it does

Automated extraction of entities, facts, and relationships from chapter text.
Identifies new KB entries to create and existing entries to update. Confidence
scoring helps users verify accuracy before merging.

## Why it exists

Manual KB entry is tedious. Writers establish facts naturally while writing
— character ages, location details, relationships — then forget to add them
to the KB. Extraction captures this information automatically, keeping KB
synchronized with the story.

## How it works (User perspective)

1. Write or edit a chapter as normal
2. When done, click "Extract to KB" in the editor toolbar
3. Extraction runs (10-30 seconds depending on chapter size)
4. Results panel shows:
   - **New entities found** (characters, locations, etc.)
   - **New facts about existing entities**
   - **Relationships discovered**
   - **Conflicts** (extraction contradicts KB)
5. Review each item with confidence score
6. Check items to approve, uncheck to reject
7. Click "Apply" — KB updated

Can also run automatically on chapter save (configurable in Settings).

## How it works (Technical)

**Entry point:** `kb/router.py` → `POST /api/v1/kb/extract/{chapter_id}`
**Service:** `ExtractionService.extract()` in `kb/extraction_service.py`
**Contract:** `ExtractionProtocol` in `kb/contracts.py`
**LLM Intent:** `LLMIntent.KB_EXTRACT`

**Three-stage extraction:**

**1. Rule-based extraction (high confidence)**
- Pull facts from chapter frontmatter
- Extract explicit statements (X is Y's Z)
- Identify named entities with NER
- Extract temporal expressions (dates, times, durations)

**2. AI-assisted extraction (medium confidence)**
- Analyze prose for implicit facts
- Infer traits from behavior/description
- Identify implied relationships
- Extract worldbuilding details

**3. Deduplication and scoring**
- Remove duplicate extractions
- Match to existing KB entities (name similarity, embedding similarity)
- Assign confidence scores based on source and certainty
- Flag conflicts with existing KB facts

**Extraction result format:**
```python
class ExtractionResult:
    type: "new_entity" | "update_entity" | "relationship" | "conflict"
    entity_type: EntityType | None
    name: str
    confidence: float  # 0-1
    source_text: str  # quote from chapter
    proposed_content: str | None  # for new entities
    target_entity_id: UUID | None  # for updates
```

**Conflict detection:**
- New fact contradicts existing KB fact
- Same entity with incompatible details
- Relationship asymmetry (A→B but not B←A)

## Constraints & Edge Cases

- Chapter must be at least 500 words for meaningful extraction
- Very long chapters (>10k words) may be split for processing
- Ambiguous names may match wrong entities (user verification required)
- Extractions are AI-based — may misinterpret subtext, irony, or lies
- Fictional dialogue containing false statements treated as true
- Requires LLM availability — no offline mode

## Related Features

- [KB-001](KB-001-entity-management.md) — Target for extracted data
- [KB-004](KB-004-kb-consistency.md) — Conflict detection
- [INFRA-004](../infra/INFRA-004-embedding-store.md) — Entity matching via embeddings
- [WRITE-002](../writing/WRITE-002-new-chapter.md) — Chapter content source

## Architecture Decisions (2026-05-24)

### ExtractionAgent (separate from KBAgent)

KB-007 uses a dedicated ExtractionAgent — different task, different input, different
output from the KBAgent used in KB-002. The KBAgent works with templates and Q&A;
the ExtractionAgent works with chapter text and structured output.

### Review-Flow: Simple endorse/reject panel

No session model needed for KB-007. The extraction runs as a single request
(10-30s), results are presented in a review panel, and the user endorses or
rejects each item. Simple REST endpoint, no SSE, no session persistence needed.

Endpoint: `POST /api/v1/kb/extract/{chapter_id}` → `ExtractionResult[]`
Sub-endpoint: `POST /api/v1/kb/extract/apply` → saves endorsed items via KB-001

### Embedding Store dependency (INFRA-004)

Dedup and matching use embedding similarity. The `ExtractionResult.confidence`
score incorporates embedding distance between extracted and existing entries.

### Rule-based + AI two-stage extraction

Stage 1: Rule-based extraction from frontmatter and explicit statements (high confidence).
Stage 2: AI-assisted extraction for implicit facts and relationships (medium confidence).
Stage 3: Deduplication against existing KB entries via embedding similarity + name matching.

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-24` — Designed. ExtractionAgent separate from KBAgent. Simple review panel. Full embedding dependency.
- 2026-05-25 — Implemented. ExtractionService + ExtractionApplyService (backend), ExtractionPanel review UI (frontend), 31 i18n keys, editor toolbar integration.
