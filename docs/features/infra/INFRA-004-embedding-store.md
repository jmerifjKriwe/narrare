---
id: INFRA-004
title: "Embedding Store"
status: implemented
area: infra
mvp: false

ui_tooltip: "Semantic search for your Knowledge Base using AI embeddings."
ui_help_short: |
  Narrare uses AI embeddings to understand the meaning of your KB entries,
  chapters, and notes. This enables smart features like "find similar characters"
  and "suggest relevant KB entries" based on semantic similarity, not just
  keywords.
ui_help_long: |
  ## Embedding Store

  The Embedding Store powers Narrare's semantic search capabilities. It converts
  your text into mathematical vectors that capture meaning — allowing the AI to
  find connections that keyword search would miss.

  **What embeddings enable:**

  **Semantic KB Search**
  - Find characters similar to ones you've created
  - Discover locations that fit your story's mood
  - Suggest relevant worldbuilding entries for current scene

  **Context Assembly**
  - Proactive KB suggestions based on chapter content
  - Automatic detection of which entities are relevant
  - Smart ranking by similarity, not just recency

  **Analysis Features**
  - Find similar passages across your novel
  - Detect thematic connections
  - Identify potential consistency issues

  **How it works:**
  1. You create or edit content (chapters, KB entries, notes)
  2. Background task generates embedding vector
  3. Vector stored in pgvector database
  4. Search uses cosine similarity to find nearest matches

  **Background generation:**
  Embeddings are created automatically by background tasks. You can continue
  writing while they process. Large projects may take a few minutes to fully
  index after import.

  **Configurable:**
  Choose your embedding model in Settings. Defaults work well for most languages.
ui_available_in: [settings]

service: core/embeddings/store.py
contract: ~
router: ~
prompt: ~
requires: [INFRA-001]
---

# INFRA-004 — Embedding Store

## What it does

Vector database abstraction layer for storing and retrieving semantic embeddings
of KB entries, chapters, and notes. Powers similarity search, proactive context
suggestions, and semantic analysis features.

## Why it exists

Keyword search is insufficient for creative writing. "A brave warrior" and
"A courageous fighter" have no words in common but mean the same thing. Embeddings
capture semantic meaning, enabling Narrare to suggest relevant content even when
words don't match.

## How it works (User perspective)

1. You write or edit content in Narrare
2. Background task automatically creates embedding (vector representation)
3. When you use semantic features, Narrare searches by meaning, not keywords
4. Results ranked by similarity (how close in meaning, not text matching)

Most of this happens invisibly. You'll notice it in:
- KB suggestions that "just know" what's relevant
- "Similar entries" when creating new KB items
- Smart context assembly for writing

## How it works (Technical)

**Entry point:** `core/embeddings/store.py`
**Primary class:** `EmbeddingStore`
**Database:** PostgreSQL with pgvector extension
**Models:** Configurable (defaults to text-embedding-3-small via OpenAI or similar)

**Pipeline:**
1. **Generation**: Text → embedding model → vector (float array)
2. **Storage**: `(id, vector, metadata)` in pgvector table
3. **Search**: Query vector → cosine similarity → ranked results

**Embeddable content:**
- KB entries (characters, locations, factions, etc.)
- Chapters (for similarity search across novel)
- Notes and research
- Project metadata

**Background tasks:**
- `EmbeddingGenerationTask`: Queued on content change
- Batch processing for efficiency
- Priority: KB entries > chapters > notes
- Retry on failure with exponential backoff

**Search parameters:**
- `query`: Text to search for (embedded first)
- `limit`: Max results (default 10)
- `threshold`: Minimum similarity score (default 0.7)
- `filter`: Metadata filters (entity type, tags, etc.)

## Constraints & Edge Cases

- Embedding quality depends on model — some languages less supported
- Embeddings become stale if content changes — requires regeneration
- Large projects may have slow initial indexing
- pgvector required in PostgreSQL — migration prerequisite
- Vector dimension must match model (changing model requires re-index)
- Short texts (< 10 words) may have poor quality embeddings

## Related Features

- [KB-005](../kb/KB-005-kb-suggest.md) — Proactive suggestions use embedding search
- [INFRA-003](INFRA-003-context-assembly.md) — Context assembly uses embedding ranking
- [KB-007](../kb/KB-007-extraction.md) — Fact extraction benefits from semantic search
- [STATS-001](../analytics/STATS-001-writing-stats.md) — Background tasks manage embedding generation

## Status & History

- `project-init` — Added to registry as planned feature
