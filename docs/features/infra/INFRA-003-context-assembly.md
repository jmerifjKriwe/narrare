---
id: INFRA-003
title: "Context Assembly Pipeline"
status: in-progress
area: infra
mvp: true

ui_tooltip: "Intelligent gathering of relevant chapters, KB entries, and context for AI."
ui_help_short: |
  Before the AI writes or analyzes, Narrare automatically gathers relevant context
  from your recent chapters, Knowledge Base, and project settings. This ensures
  the AI understands your story world and characters.
ui_help_long: |
  ## Context Assembly

  When Narrare's AI helps you write, it needs to understand your story. The
  Context Assembly Pipeline automatically gathers all relevant information and
  packages it for the AI.

  **What the pipeline gathers:**

  **1. Immediate Context**
  - Your current chapter content (what you've written so far)
  - Chapter frontmatter (POV character, location, timeline position)

  **2. Recent History**
  - Last 3-5 chapters with relevance scoring
  - Recent character appearances and plot developments

  **3. Knowledge Base**
  - Character profiles for characters in this scene
  - Location descriptions
  - Relevant worldbuilding facts

  **4. Proactive Suggestions**
  - KB entries the AI thinks might be relevant
  - Based on pattern recognition and embeddings

  **5. Pinned Items**
  - KB entries you've manually marked as important
  - Never overridden by automatic selection

  **User controls:**
  - Pin important KB entries for key scenes
  - Dismiss irrelevant suggestions
  - Adjust context scope per chapter (narrow for focus, wide for connections)
  - Review context before AI generation

  The pipeline applies token limits intelligently — more important context gets
  priority, less relevant content is trimmed first.
ui_available_in: [editor]

service: core/writing/context_assembler.py (writing specialization), core/context/assembler.py (general)
contract: core/writing/contracts.py#ContextAssemblerProtocol
router: ~
prompt: ~
requires: [INFRA-001, INFRA-002, KB-001]
---

# INFRA-003 — Context Assembly Pipeline

## What it does

Intelligent context gathering system that assembles relevant chapters, Knowledge
Base entries, and project metadata into a structured prompt context for AI
operations. Uses 5-tier prioritization with token budget management.

## Why it exists

Without context assembly, the AI would write in a vacuum — it wouldn't know
your characters, your world, or what happened in previous chapters. Manual
context selection is tedious and error-prone. The pipeline ensures the AI always
has the right information without requiring user effort.

## How it works (User perspective)

1. You open a chapter or trigger an AI feature
2. Narrare automatically gathers context from 5 sources
3. Relevant KB entries appear in the context panel
4. You can pin important items or dismiss suggestions
5. AI uses this context when generating text
6. Context updates automatically as you write

Most users don't need to think about it — it just works. Power users can
fine-tune context for complex scenes.

## How it works (Technical)

**Entry point:** `core/context/assembler.py` (general), `core/writing/context_assembler.py` (writing specialization)
**Primary class:** `ContextAssembler` (general), `WritingContextAssembler` (writing)
**Input:** `PromptContext` with chapter_id, mode, language
**Output:** Structured context with ranked KB entries and recent chapters

**5 Context tiers (general):**
1. **Immediate Context**: Current chapter content + frontmatter
2. **Recent History**: Last 3-5 chapters, ranked by recency and relevance
3. **Knowledge Base**: Character/location/faction profiles, ranked by similarity
4. **Proactive Suggestions**: AI-recommended entries via embedding search
5. **Pinned Items**: User-pinned entries (always included)

**Assembly process:**
1. Parse chapter frontmatter for entity references
2. Fetch referenced KB entries
3. Calculate similarity scores for remaining KB entries
4. Rank by: 50% relevance, 30% usage frequency, 20% recency
5. Apply token budget: prioritize high-ranked items
6. Format as structured context for prompt variables

**Token budgeting (general):**
- Each intent has a token budget for context
- Immediate context gets 30%
- KB entries get 40% (proportional to rank)
- Recent history gets 30%
- Pinned items bypass budgeting

### Writing Specialization

The writing pipeline uses `WritingContextAssembler` (`core/writing/context_assembler.py`) with a specialized 5-tier ranking tuned for creative writing:

**Tier allocation (token budget enforced by `TokenBudgetManager` in `budget.py`):**

| Tier | Budget | Description |
|------|--------|-------------|
| Immediate | 30% | Current chapter content + frontmatter |
| Recent | 20% | Last 3-5 chapters with relevance scoring |
| KB Referenced | 25% | KB entries explicitly referenced in chapter/frontmatter |
| KB Suggested | 15% | AI-recommended entries via embedding similarity |
| Pinned | 10% | User-pinned entries (bypasses overflow) |

**Token budget enforcement:**
- `TokenBudgetManager` allocates tokens per tier based on model context window
- Overflow handling: lower-priority tiers are trimmed first
- Pinned items always included (10% reserved), even if other tiers overflow
- Budget recalculated per generation request based on resolved model config

**KB entity relevance ranking:**
- 50% similarity — embedding-based cosine similarity to chapter content
- 30% frequency — how often the entity appears in recent chapters
- 20% recency — when the entity was last referenced in the manuscript

**Shared between context tiers:** The writing assembler reuses the general context tier structure but applies domain-specific ranking weights optimized for narrative consistency.

## Constraints & Edge Cases

- Maximum context size varies by model's token limit
- KB entries with low similarity scores may be excluded
- Very long chapters reduce context available for KB
- Empty KB results in only chapter history context
- Pinned items count against total budget (can crowd out other context)

## Related Features

- [KB-005](../kb/KB-005-kb-suggest.md) — Proactive suggestions use same embedding search
- [KB-001](../kb/KB-001-entity-management.md) — KB entries are primary context source
- [INFRA-002](INFRA-002-prompt-system.md) — Context provides prompt variables
- [WRITE-002](../writing/WRITE-002-new-chapter.md) — Writing consumes assembled context

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-17` — Writing specialization implemented. `WritingContextAssembler` with 5-tier ranking (30/20/25/15/10 split), `TokenBudgetManager` for tier allocation with overflow handling, KB entity relevance ranking (50% similarity, 30% frequency, 20% recency). Core data models in `context_models.py` (`KBEntity`, `RecentChapter`).
