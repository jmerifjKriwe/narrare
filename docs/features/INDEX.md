# Feature Registry — v1 product history

> **Historical corpus (v1 era).** These records describe the pre-v2 application and
> are kept as the product history of the old system. The architecture authority is
> the [v2 spec](../superpowers/specs/2026-10-21-narrare-v2-architecture-design.md);
> the standing rules are [`docs/_shared/CONSTRAINTS.md`](../_shared/CONSTRAINTS.md).
> Nothing in this directory binds the v2 tree.
>
> **What it is still for.** The v2 build ports v1 behaviour one capability at a
> time, and the feature corpus is the input for that, not the scope (spec §11, D4):
> every registered feature inside a core area is triaged once — doc status, code
> evidence, verdict. These tables are the complete inventory, each row pointing at
> the file that describes the feature. A port takes the files it builds on as its
> basis and records their IDs in the port ledger of
> [`docs/superpowers/plans/2026-10-21-v2-build.md`](../superpowers/plans/2026-10-21-v2-build.md);
> an ID with no ledger entry is one that no port has taken up yet.
>
> **What the files are.** Each carries v1 frontmatter (status, area, MVP, the
> `ui_*` help texts, and v1 code paths such as `writing/draft_service.py`). The code
> paths and every ADR or process link point into git history: the cutover
> (`48e7d7d4`) deleted the v1 tree and `d989511a` the v1 design record.
> Per-feature implementation history lives in each file's own
> "Status & History" section; this index does not repeat it.

## Status Legend

The status column is the v1 document status — a claim, not evidence (spec §11).

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
| [INFRA-006](infra/INFRA-006-a2a-integration.md) | A2A Integration | 📋 | ❌ |
| [INFRA-007](infra/INFRA-007-background-tasks.md) | Background Tasks | ✅ | ❌ |
| [INFRA-008](infra/INFRA-008-mcp-integration.md) | MCP Integration | 📋 | ❌ |
| [INFRA-009](infra/INFRA-009-proactive-context.md) | Proactive Context Loading *(merged into KB-005; deprecated as a standalone feature)* | ⛔ | ❌ |
| [INFRA-010](infra/INFRA-010-prompting-locally.md) | Prompting Locally | ✅ | ❌ |
| [INFRA-011](infra/INFRA-011-ai-feature-stabilization.md) | AI Feature Stabilization Program | ✅ | ❌ |
| [INFRA-012](infra/INFRA-012-prompt-governance-hardening.md) | Prompt Governance Hardening | ✅ | ❌ |
| [INFRA-013](infra/INFRA-013-ai-invocation-adoption-contract.md) | AI Invocation Adoption Contract | ✅ | ❌ |

### Setup & Onboarding
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [SETUP-001](setup/SETUP-001-setup-wizard.md) | Setup Wizard (5-step) | ✅ | ✅ |
| [SETUP-002](setup/SETUP-002-demo-content.md) | Demo Projects | ✅ | ✅ |
| [SETUP-003](setup/SETUP-003-import.md) | Project Import | ✅ | ❌ |
| [SETUP-004](setup/SETUP-004-provider-config.md) | AI Provider Configuration | ✅ | ✅ |
| [ONBOARD-001](onboarding-user-guide.md) | Onboarding & AI-Einführung | ✅ | ❌ |

### Writing
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [WRITE-001](writing/WRITE-001-editor.md) | Writing Editor | ✅ | ✅ |
| [WRITE-002](writing/WRITE-002-new-chapter.md) | AI: New Chapter Generation | ✅ | ✅ |
| [WRITE-003](writing/WRITE-003-extend.md) | AI: Extend Chapter | ✅ | ❌ |
| [WRITE-004](writing/WRITE-004-rewrite.md) | AI: Rewrite Selection | ✅ | ❌ |
| [WRITE-005](writing/WRITE-005-interactive-session.md) | Interactive Writing Session | ✅ | ✅ |
| [WRITE-006](writing/WRITE-006-co-author.md) | Co-Author Mode | ✅ | ❌ |
| [WRITE-007](writing/WRITE-007-inline-suggestions.md) | Inline AI Suggestions | ✅ | ❌ |
| [WRITE-008](writing/WRITE-008-multi-draft.md) | Multi-Draft Generation | 📋 | ❌ |
| [WRITE-009](writing/WRITE-009-unblock.md) | Writer's Unblock Tools | ✅ | ❌ |
| [WRITE-010](writing/WRITE-010-voice-checker.md) | Voice Consistency Checker | ✅ | ❌ |
| [WRITE-011](writing/WRITE-011-volume-management.md) | Volume Management | ✅ | ✅ |
| [WRITE-012](writing/WRITE-012-chapter-summary.md) | Chapter Summary | ✅ | ❌ |
| [WRITE-013](writing/WRITE-013-workflows.md) | Writing Workflows | 📋 | ❌ |
| [WRITE-014](writing/WRITE-014-context-inspector.md) | Context Inspector | ✅ | ❌ |

### Series
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [SERIES-001](series/SERIES-001-foundation.md) | Series Foundation | ✅ | ❌ |
| [SERIES-002](series/SERIES-002-generation-context.md) | Series Generation Context | ✅ | ❌ |
| [SERIES-003](series/SERIES-003-voice-hierarchy.md) | Series Voice Hierarchy | ✅ | ❌ |
| [SERIES-004](series/SERIES-004-cross-novel-drift.md) | Series Cross-Novel Drift | ✅ | ❌ |

### Chat
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [CHAT-001](chat/CHAT-001-free-form-chat.md) | Free-Form Chat | ✅ | ❌ |

### Notes
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [NOTES-001](notes/NOTES-001-scratchpad.md) | Scratchpad | ✅ | ❌ |

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
| [KB-009](kb/KB-009-kb-merge.md) | KB Entity Merge / Deduplication | ✅ | ❌ |
| [KB-010](kb/KB-010-editor-graph.md) | Editor-Integrated Knowledge Graph | 💡 | ❌ |
| [WIKI-001](kb/WIKI-001-llm-wiki.md) | LLM Wiki — Precomputed Context Layer | ✅ | ❌ |

### Analysis
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [ANAL-001](analysis/ANAL-001-beta-reader.md) | Beta Reader Simulation | ✅ | ❌ |
| [ANAL-002](analysis/ANAL-002-sentiment.md) | Sentiment Analysis | ✅ | ❌ |
| [ANAL-003](analysis/ANAL-003-readability.md) | Readability Analysis | ✅ | ❌ |
| [ANAL-004](analysis/ANAL-004-pov.md) | POV Analysis | ✅ | ❌ |
| [ANAL-005](analysis/ANAL-005-coreference.md) | Coreference Analysis | ✅ | ❌ |
| [ANAL-006](analysis/ANAL-006-sensitivity.md) | Sensitivity Review | 📋 | ❌ |
| [ANAL-007](analysis/ANAL-007-voice-author.md) | Author Voice Profiling | ✅ | ❌ |
| [ANAL-008](analysis/ANAL-008-voice-character.md) | Character Voice Profiling | ✅ | ❌ |
| [ANAL-009](analysis/ANAL-009-voice-drift.md) | Voice Drift Detection | ✅ | ❌ |
| [ANAL-010](analysis/ANAL-010-literary-suite.md) | Literary Analysis Suite | 📋 | ❌ |
| [ANAL-011](analysis/ANAL-011-plot-analysis.md) | Plot Analysis | 📋 | ❌ |

### Planning
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [PLAN-001](planning/PLAN-001-scene-planning.md) | Scene Planning | ✅ | ❌ |
| [PLAN-002](planning/PLAN-002-gap-analysis.md) | Narrative Gap Analysis | 📋 | ❌ |
| [PLAN-003](planning/PLAN-003-structure.md) | Story Structure Visualization | ✅ | ✅ |
| [PLAN-004](planning/PLAN-004-timeline.md) | Timeline Management | ✅ | ❌ |
| [PLAN-005](planning/PLAN-005-storyboard.md) | Storyboard View | ✅ | ✅ |
| [PLAN-006](planning/PLAN-006-character-arc.md) | Character Arc Analysis | ✅ | ❌ |

### AI Assist (Standalone Operations)
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [ASSIST-001](ai_assist/ASSIST-001-plot-check.md) | Plot Consistency Check | 📋 | ❌ |
| [ASSIST-002](ai_assist/ASSIST-002-title-suggest.md) | Title Suggestions | 📋 | ❌ |
| ~~ASSIST-003~~ | ~~Story Chat Assistant~~ *(superseded by CHAT-001)* | ⛔ | ❌ |
| [ASSIST-004](ai_assist/ASSIST-004-dialogue-coach.md) | Dialogue Coach | ✅ | ❌ |

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
| [LEARN-002](learning/LEARN-002-style-adaptation.md) | Adaptivity Dashboard | ✅ | ❌ |

### Prompt Customization
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [PROMPT-001](prompts/PROMPT-001-file-overrides.md) | File-based Prompt Overrides | ✅ | ✅ |
| [PROMPT-002](prompts/PROMPT-002-db-templates.md) | User DB Prompt Templates | ✅ | ✅ |
| [PROMPT-003](prompt-customization-ux.md) | Prompt Customization UX | ✅ | ❌ |

### Import / Export
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [IO-001](io/IO-001-export.md) | Manuscript Export | ✅ | ❌ |
| [IO-002](io/IO-002-import.md) | Corpus Analysis Pass | 📋 | ❌ |
| [IO-003](io/IO-003-sync.md) | External Sync | 📋 | ❌ |

### Internationalization & UI Copy
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [I-Copy-001](i18n/I-Copy-001-formality-register.md) | User-Selectable UI Formality (du / Sie) | ✅ | ❌ |

### Settings & Configuration
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [SET-001](settings/SET-001-user-settings.md) | User Settings | ✅ | ✅ |
| [SET-002](settings/SET-002-project-settings.md) | Project Settings | ✅ | ✅ |
| [SET-003](settings/SET-003-model-config.md) | Per-task Model Configuration | ✅ | ✅ |
| [SET-004](settings/SET-004-shortcuts.md) | Keyboard Shortcuts | 📋 | ❌ |
| [SET-005](settings/SET-005-configurable-token-limits.md) | Configurable Token Limits | ✅ | ❌ |
| [KEYBOARD-001](keyboard-consistency.md) | Tastatur-Konsistenz | ✅ | ❌ |

### Analytics & Cost
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [STATS-001](analytics/STATS-001-writing-stats.md) | Writing Statistics | ✅ | ❌ |
| [STATS-002](analytics/STATS-002-cost-tracking.md) | AI Cost Tracking | ✅ | ❌ |

### Adapter / Integration
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| ADAPTER-001 | MCP (Model Context Protocol) Adapter | 💡 | ❌ |
| ADAPTER-002 | A2A (Agent-to-Agent) Adapter | 💡 | ❌ |

---

## Supplementary Documentation

Directories and files here that are not standalone features:

| Location | Type |
|----------|------|
| `docs/features/remediation/` | CR-item remediation specifications |
| `docs/features/ai-ux/` | CR-07 UX follow-up specifications (CR-AUFG-07-18 … -24) |
| `docs/features/planning/PLAN-004-architecture.md` | Architecture supplement for PLAN-004 (Timeline) |
| `docs/features/auth/auth-flake-fix.md` | Auth flake fix note |

The process that maintained this index — ID assignment, the file template, the
architecture review gate — ended with the v1 cutover; git history keeps it.
