# Feature Registry — Index

> **The canonical list of all Narrare features.**
> Each feature has its own file in `docs/features/`.
> This index is the overview — load individual feature files only when needed.
>
> Feature files serve double duty:
> - Developer reference (what, how, constraints)
> - UI help text source (tooltip, help panel, onboarding)
>
> Location: `docs/features/INDEX.md`
> Maintained by: Architecture Agent + project owner

---

## Status Legend

| Symbol | Status | Meaning |
|--------|--------|---------|
| ✅ | stable | Fully implemented, tested, documented |
| 🔨 | in-progress | Being implemented in current cycle |
| 📋 | planned | Specified, not yet started |
| 💡 | idea | Not yet specified — needs Architecture session |
| ⛔ | deprecated | Removed or replaced |

---

## Feature Areas

### Core Infrastructure
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [INFRA-001](infra/INFRA-001-llm-gateway.md) | LLM Gateway | ✅ | ✅ |
| [INFRA-002](infra/INFRA-002-prompt-system.md) | Unified Prompt System | ✅ | ✅ |
| [INFRA-003](infra/INFRA-003-context-assembly.md) | Context Assembly Pipeline | ✅ | ✅ |
| [INFRA-004](infra/INFRA-004-embedding-store.md) | Embedding Store | ✅ | ❌ |
| [INFRA-005](infra/INFRA-005-memory-layer.md) | Memory Layer (mem0) | ✅ | ✅ |
| [INFRA-010](infra/INFRA-010-prompting-locally.md) | Prompting Locally | ✅ | ❌ |

### Setup & Onboarding
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [SETUP-001](setup/SETUP-001-setup-wizard.md) | Setup Wizard (5-step) | ✅ | ✅ |
| [SETUP-002](setup/SETUP-002-demo-content.md) | Demo Projects | ✅ | ✅ |
| [SETUP-003](setup/SETUP-003-import.md) | Project Import | 📋 | ❌ |
| [SETUP-004](setup/SETUP-004-provider-config.md) | AI Provider Configuration | ✅ | ✅ |

### Writing
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [WRITE-001](writing/WRITE-001-editor.md) | Writing Editor | ✅ | ✅ |
| [WRITE-002](writing/WRITE-002-new-chapter.md) | AI: New Chapter Generation | ✅ | ✅ |
| [WRITE-003](writing/WRITE-003-extend.md) | AI: Extend Chapter | ✅ | ❌ |
| [WRITE-004](writing/WRITE-004-rewrite.md) | AI: Rewrite Selection | ✅ | ❌ |
| [WRITE-005](writing/WRITE-005-interactive-session.md) | Interactive Writing Session | ✅ | ✅ |
| [WRITE-006](writing/WRITE-006-co-author.md) | Co-Author Mode | 📋 | ❌ |
| [WRITE-007](writing/WRITE-007-inline-suggestions.md) | Inline AI Suggestions | ✅ | ❌ |
| [WRITE-008](writing/WRITE-008-multi-draft.md) | Multi-Draft Generation | 📋 | ❌ |
| [WRITE-009](writing/WRITE-009-unblock.md) | Writer's Block Tools | 📋 | ❌ |
| [WRITE-010](writing/WRITE-010-voice-checker.md) | Voice Consistency Checker | 📋 | ❌ |
| [WRITE-011](writing/WRITE-011-volume-management.md) | Volume Management | ✅ | ✅ |
| [WRITE-012](writing/WRITE-012-chapter-summary.md) | Chapter Summary | ✅ | ❌ |
| [WRITE-014](writing/WRITE-014-context-inspector.md) | Context Inspector | ✅ | ❌ |

### Knowledge Base
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [KB-001](kb/KB-001-entity-management.md) | KB Entity CRUD | ✅ | ✅ |
| [KB-002](kb/KB-002-kb-session.md) | Assisted KB Creation (AI-guided creation) | ✅ | ❌ |
| [KB-003](kb/KB-003-kb-improve.md) | AI: Improve KB Entry | ✅ | ❌ |
| [KB-004](kb/KB-004-kb-consistency.md) | AI: KB Consistency Check | ✅ | ❌ |
| [KB-005](kb/KB-005-kb-suggest.md) | Proactive KB Suggestions | ✅ | ✅ |
| [KB-006](kb/KB-006-worldbuilding.md) | Worldbuilding Assistant | ✅ | ❌ |
| [KB-007](kb/KB-007-extraction.md) | Entity Extraction from Chapters | ✅ | ❌ |
| [KB-008](kb/KB-008-knowledge-graph.md) | Knowledge Graph | ✅ | ❌ |
| [WIKI-001](kb/WIKI-001-llm-wiki.md) | LLM Wiki — Precomputed Context Layer | 📋 | ❌ |

### Analysis
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [ANAL-001](analysis/ANAL-001-beta-reader.md) | Beta Reader Simulation | ✅ | ❌ |
| [ANAL-002](analysis/ANAL-002-sentiment.md) | Sentiment Analysis | ✅ | ❌ |
| [ANAL-003](analysis/ANAL-003-readability.md) | Readability Analysis | 📋 | ❌ |
| [ANAL-004](analysis/ANAL-004-pov.md) | POV Analysis | 📋 | ❌ |
| [ANAL-005](analysis/ANAL-005-coreference.md) | Coreference Analysis | 📋 | ❌ |
| [ANAL-006](analysis/ANAL-006-sensitivity.md) | Sensitivity Review | 📋 | ❌ |
| [ANAL-007](analysis/ANAL-007-voice-author.md) | Author Voice Profiling | 📋 | ❌ |
| [ANAL-008](analysis/ANAL-008-voice-character.md) | Character Voice Profiling | 📋 | ❌ |
| [ANAL-009](analysis/ANAL-009-voice-drift.md) | Voice Drift Detection | 📋 | ❌ |
| [ANAL-010](analysis/ANAL-010-literary-suite.md) | Literary Analysis Suite | 📋 | ❌ |
| [ANAL-011](analysis/ANAL-011-plot-analysis.md) | Plot Analysis | 📋 | ❌ |

### Planning
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [PLAN-001](planning/PLAN-001-scene-planning.md) | Scene Planning | 📋 | ❌ |
| [PLAN-002](planning/PLAN-002-gap-analysis.md) | Narrative Gap Analysis | 📋 | ❌ |
| [PLAN-003](planning/PLAN-003-structure.md) | Story Structure Visualization | ✅ | ✅ |
| [PLAN-004](planning/PLAN-004-timeline.md) | Timeline Management | 📋 | ❌ |
| [PLAN-005](planning/PLAN-005-storyboard.md) | Storyboard View | ✅ | ✅ |

> **Note:** PLAN-003 (Structure) and PLAN-005 (Storyboard) were implemented together as a merged feature. PLAN-003's structure adapters power PLAN-005's stage layout. PLAN-004 has a partial integration point (`timeline_position` field) — full timeline management remains planned future work.

### AI Assist (Standalone Operations)
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [ASSIST-001](ai_assist/ASSIST-001-plot-check.md) | Plot Consistency Check | 📋 | ❌ |
| [ASSIST-002](ai_assist/ASSIST-002-title-suggest.md) | Title Suggestions | 📋 | ❌ |
| [ASSIST-003](ai_assist/ASSIST-003-chat.md) | Story Chat Assistant | 📋 | ❌ |

### Generation
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [GEN-001](generation/GEN-001-name-generator.md) | Character/Place Name Generator | ✅ | ✅ |
| [GEN-002](generation/GEN-002-research.md) | Research Assistant | 📋 | ❌ |

### Consistency
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [CONS-001](consistency/CONS-001-checker.md) | Consistency Checker | ✅ | ❌ |
| [CONS-002](consistency/CONS-002-rules.md) | Custom Consistency Rules | 📋 | ❌ |

### Learning & Adaptation
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [LEARN-001](learning/LEARN-001-feedback-loop.md) | Feedback & Learning Loop | ✅ | ✅ |
| [LEARN-002](learning/LEARN-002-style-adaptation.md) | Style Adaptation | 📋 | ❌ |

### Prompt Customization
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [PROMPT-001](prompts/PROMPT-001-file-overrides.md) | File-based Prompt Overrides | ✅ | ✅ |
| [PROMPT-002](prompts/PROMPT-002-db-templates.md) | User DB Prompt Templates | ✅ | ✅ |

### Import / Export
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [IO-001](io/IO-001-export.md) | Manuscript Export | 📋 | ❌ |
| [IO-002](io/IO-002-import.md) | Project Import & Analysis | 📋 | ❌ |
| [IO-003](io/IO-003-sync.md) | External Sync | 📋 | ❌ |

### Settings & Configuration
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [SET-001](settings/SET-001-user-settings.md) | User Settings | ✅ | ✅ |
| [SET-002](settings/SET-002-project-settings.md) | Project Settings | ✅ | ✅ |
| [SET-003](settings/SET-003-model-config.md) | Per-task Model Configuration | ✅ | ✅ |
| [SET-005](settings/SET-005-configurable-token-limits.md) | Configurable Token Limits | ✅ | ❌ |

### Analytics & Cost
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [STATS-001](analytics/STATS-001-writing-stats.md) | Writing Statistics | 📋 | ❌ |
| [STATS-002](analytics/STATS-002-cost-tracking.md) | AI Cost Tracking | 📋 | ❌ |

---

## Feature File Schema

Every feature file follows this structure:

```markdown
# [ID] — [Feature Name]

[Frontmatter — see schema below]

## What it does
[1-3 sentences. Precise. No jargon. This becomes the UI help text.]

## Why it exists
[The user problem this solves. Connects to PROJECT_VISION.md.]

## How it works (User perspective)
[Step-by-step from the user's point of view. No implementation details.]

## How it works (Technical)
[Implementation details. Which services, contracts, agent, prompt.]

## Constraints & Edge Cases
[What it cannot do. What happens when things fail.]

## Related Features
[IDs of features that interact with this one.]

## Status & History
[When added, any significant changes.]
```

### Frontmatter Schema

```yaml
---
id: WRITE-002
title: "AI: New Chapter Generation"
status: planned          # planned | in-progress | stable | deprecated
area: writing            # writing | kb | analysis | planning | setup | etc.
mvp: false               # included in first running version?

# UI text — consumed by frontend help system
ui_tooltip: "Generate a complete new chapter draft using your KB and story context."
ui_help_short: |
  Ask the AI to write a complete new chapter. Narrare automatically
  loads your relevant characters, locations, and story context — you
  just describe what should happen.
ui_help_long: |
  [Full help text for the help panel — can be multiple paragraphs,
   can reference other features. Markdown supported.]
ui_available_in: [editor, chapter-list]  # where the help icon appears

# Developer reference
service: writing/draft_service.py
contract: writing/contracts.py#DraftServiceProtocol
router: writing/router_drafts.py
prompt: core/prompts/_bundled/writing/en/new_chapter/system.md
requires: [INFRA-001, INFRA-002, INFRA-003, KB-001]
---
```

---

## Adding a New Feature

1. Assign the next ID in the appropriate area
2. Copy `_TEMPLATE.md` from this directory
3. Fill in all frontmatter fields
4. Write all sections — especially `ui_help_short` (required for UI)
5. Add to this index
6. If MVP=true: add to `MVP_PLAN.md` implementation list
7. Bring to Architecture Agent for review before implementation starts

---

> Last updated: 2026-05-29 — WRITE-007 (Inline AI Suggestions) fully implemented across all layers. Feature → stable.
> Features are specified before they are implemented — never after
