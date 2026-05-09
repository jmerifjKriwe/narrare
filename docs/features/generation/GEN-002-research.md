---
id: GEN-002
title: "Research Assistant"
status: planned
area: generation
mvp: false

ui_tooltip: "Search the web, verify facts, and explore cultural context."
ui_help_short: |
  Integrated research tools for fact verification, historical accuracy,
  and cultural context. Search the web, validate claims against sources,
  and save research to your Knowledge Base without leaving your writing.
ui_help_long: |
  ## Research Assistant

  Research without leaving your writing environment.

  **Web Search**
  - General web searching for information
  - Result summaries with source links
  - Search history for reference
  - CLI and web interface access

  **Fact Verification**
  - Claim validation against multiple sources
  - Confidence scoring for fact accuracy
  - Contradiction identification
  - Source citation and links

  **Historical Research**
  - Period-specific information gathering
  - Anachronism detection
  - Historical accuracy checking
  - Contextual historical details

  **Cultural Research**
  - Cultural practices and traditions
  - Sensitivity and representation guidance
  - Authentic portrayal assistance
  - Cross-cultural comparison tools

  **Research Management**
  - Save sources to Knowledge Base
  - Organize research by category
  - Search within saved research
  - Export research findings

  **How it works:**
  1. Open Research panel from Editor or KB
  2. Choose research type:
     - **Web Search**: General information
     - **Fact Check**: Verify specific claim
     - **Historical**: Period-specific research
     - **Cultural**: Cultural context exploration
  3. Enter query or claim to verify
  4. Results appear with:
     - Summarized findings
     - Source links and citations
     - Confidence scores
     - Suggestions for incorporating
  5. Save relevant findings to KB
  6. Access saved research from any chapter

  **Best practices:**
  - Verify critical facts through multiple sources
  - Save important research to Knowledge Base
  - Use cultural research for authentic representation
  - Combine with sensitivity reader for review
  - Check historical accuracy before final edits

  Available in Editor panel, KB, or via CLI:
  `narrare research search --query "medieval armor types"`
  `narrare research verify --claim "Plate armor was common in 12th century"`
ui_available_in: [editor, kb, cli]

service: research/service.py
contract: research/contracts.py#ResearchServiceProtocol
router: research/router.py
prompt: core/prompts/_bundled/research/en/search
requires: [INFRA-001, KB-001]
---

# GEN-002 — Research Assistant

## What it does

Integrated research capabilities for web search, fact verification, historical research, and cultural context exploration. Enables writers to research without leaving their writing environment and save findings to their Knowledge Base.

## Why it exists

Writers need to research constantly: historical facts, cultural practices, technical details, geographic information. Context switching between writing and research breaks flow. Research assistant brings research into the writing environment with fact verification and knowledge base integration.

## How it works (User perspective)

1. Open Research panel from:
   - Editor sidebar (while writing)
   - KB panel (while worldbuilding)
   - CLI for batch research
2. Choose research type:
   - **Web Search**: General information gathering
   - **Fact Check**: Verify specific claim
   - **Historical**: Period-specific research
   - **Cultural**: Cultural context exploration
3. Enter query or claim
4. AI searches and synthesizes (10-30 seconds):
   - Retrieves relevant sources
   - Summarizes key findings
   - Checks for contradictions
   - Assesses confidence
5. Review results:
   - Summarized findings
   - Source links and citations
   - Confidence score (0-1)
   - Incorporation suggestions
6. Save to KB or use directly

## How it works (Technical)

**Entry point:** `research/router.py` → `POST /api/v1/research/search`
**Service:** `ResearchService.search()` in `research/service.py`
**Contract:** `ResearchServiceProtocol` in `research/contracts.py`
**LLM Intent:** `LLMIntent.RESEARCH`

**Research result:**
```python
class ResearchResult:
    query: str
    summary: str  # Synthesized findings
    sources: list[Source]  # URLs, titles, snippets
    confidence: float  # 0-1
    contradictions: list[str]  # Conflicting info found
    suggestions: list[str]  # How to incorporate
```

**Fact verification:**
1. Parse claim into verifiable components
2. Search for supporting/refuting sources
3. Compare multiple sources for agreement
4. Calculate confidence based on source consensus
5. Identify contradictions between sources
6. Provide citations for verification

**Historical research:**
- Period-anchored search queries
- Anachronism detection
- Contextual detail extraction
- Source reliability assessment

**Cultural research:**
- Cultural practice documentation
- Sensitivity flagging
- Authentic representation guidance
- Cross-cultural comparisons

## Constraints & Edge Cases

- Requires internet connection for web search
- Source quality varies (web is unfiltered)
- Historical records may be incomplete
- Cultural practices vary within cultures
- Fact verification limited to available sources
- May miss recent events or discoveries
- Synthesis may introduce minor inaccuracies
- Cannot replace expert consultation

## Related Features

- [KB-001](../kb/KB-001-entity-management.md) — Research storage
- [ANAL-006](../analysis/ANAL-006-sensitivity.md) — Sensitivity analysis
- [ASSIST-001](../ai_assist/ASSIST-001-plot-check.md) — Plot consistency
- [WRITE-001](../writing/WRITE-001-editor.md) — In-editor research

## Status & History

- `project-init` — Added to registry as planned feature
